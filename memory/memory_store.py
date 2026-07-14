"""
记忆存储模块 - 双存储架构
- ChromaDB (memories collection, cosine 距离)：记忆知识点的向量表示
- SQLite (memory_items + user_profiles 表)：记忆元数据 + 用户画像缓存

核心能力：
1. add_memory        写入 + 查重合并（cosine distance < MERGE_THRESHOLD 则合并）
2. search_memories   向量检索 + 复合排序 + 访问计数更新
3. get_top_topics    topics 频率统计（供推荐引擎）
4. 画像缓存读写、基础 CRUD

约束：SQLite memory_items.id 与 ChromaDB document id 使用同一个 UUID。
"""

import os
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document


# ---- 配置（可通过环境变量覆盖）----
DB_PATH = os.getenv("DB_PATH") or os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "sessions.db"
)
MEMORY_PERSIST_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "chroma_db"
)
# cosine distance < MERGE_THRESHOLD → 合并（同一知识点的不同表述）
MERGE_THRESHOLD = float(os.getenv("MEMORY_MERGE_THRESHOLD", "0.15"))


class MemoryStore:
    """记忆库存储：ChromaDB 向量 + SQLite 元数据"""

    def __init__(
        self,
        db_path: str = DB_PATH,
        persist_dir: str = MEMORY_PERSIST_DIR,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        self.db_path = db_path
        self.persist_dir = persist_dir

        # embedding 配置（与 vector_store 一致，可用独立 embedding provider）
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY"))
        self.base_url = base_url or os.getenv(
            "EMBEDDING_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )
        self.embedding_model = embedding_model or os.getenv(
            "EMBEDDING_MODEL", "text-embedding-3-large"
        )

        self.embeddings = OpenAIEmbeddings(
            model=self.embedding_model,
            api_key=self.api_key,
            base_url=self.base_url,
        )

        # ChromaDB memories collection：显式指定 cosine 距离
        self._vectorstore = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            collection_name="memories",
            collection_metadata={"hnsw:space": "cosine"},
        )

        self._init_db()

    # ================= SQLite 初始化 =================

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                knowledge TEXT NOT NULL,
                topics TEXT NOT NULL DEFAULT '[]',
                source_papers TEXT DEFAULT '[]',
                source_session TEXT,
                prev_memory_id TEXT,
                importance REAL DEFAULT 0.5,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                times_used INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_memory_user
                ON memory_items(user_id, importance DESC);

            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                profile_text TEXT NOT NULL,
                interaction_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    # ================= 写入 + 查重合并 =================

    def add_memory(
        self,
        knowledge: str,
        user_id: str,
        topics: Optional[list[str]] = None,
        source_papers: Optional[list[str]] = None,
        source_session: Optional[str] = None,
        prev_memory_id: Optional[str] = None,
    ) -> str:
        """
        写入一条记忆。写入前先查重：
        - 若与现有记忆 cosine distance < MERGE_THRESHOLD → 合并到那条，返回其 id
        - 否则新增，返回新 id

        追问回溯：若 prev_memory_id 存在，给前一条记忆 importance +0.3。
        """
        topics = topics or []
        source_papers = source_papers or []

        # 追问回溯：前一条记忆被追问了
        if prev_memory_id:
            self._boost_importance(prev_memory_id, boost=0.3)

        # 查重：检索最相似的 Top-1（限定同用户）
        try:
            similar = self._vectorstore.similarity_search_with_score(
                knowledge, k=1, filter={"user_id": user_id}
            )
        except Exception:
            similar = []

        if similar:
            existing_doc, distance = similar[0]
            if distance < MERGE_THRESHOLD:
                existing_id = existing_doc.metadata.get("memory_id")
                if existing_id:
                    self._merge_memory(existing_id, knowledge, topics, source_papers)
                    return existing_id

        # 新增
        memory_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        importance = 0.5  # 基础分（access_count 从 0 开始，加权为 0）

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO memory_items
               (id, user_id, knowledge, topics, source_papers, source_session,
                prev_memory_id, importance, status, created_at, last_accessed,
                access_count, times_used)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, 0, 0)""",
            (
                memory_id, user_id, knowledge,
                json.dumps(topics, ensure_ascii=False),
                json.dumps(source_papers, ensure_ascii=False),
                source_session, prev_memory_id, importance, now, now,
            ),
        )
        conn.commit()
        conn.close()

        # 写入 ChromaDB（同一个 ID）
        self._vectorstore.add_documents(
            [Document(
                page_content=knowledge,
                metadata={"user_id": user_id, "memory_id": memory_id},
            )],
            ids=[memory_id],
        )

        return memory_id

    def _merge_memory(self, memory_id: str, new_knowledge: str,
                      new_topics: list[str], new_source_papers: list[str]):
        """合并：保留更详细的 knowledge，合并 topics/source_papers，importance +0.05"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT knowledge, topics, source_papers, importance FROM memory_items WHERE id = ?",
            (memory_id,),
        ).fetchone()
        if not row:
            conn.close()
            return

        # 保留更长（更详细）的 knowledge
        merged_knowledge = new_knowledge if len(new_knowledge) > len(row["knowledge"]) else row["knowledge"]

        # 合并 topics / source_papers（去重）
        old_topics = json.loads(row["topics"] or "[]")
        old_papers = json.loads(row["source_papers"] or "[]")
        merged_topics = list(dict.fromkeys(old_topics + new_topics))
        merged_papers = list(dict.fromkeys(old_papers + new_source_papers))

        new_importance = min(row["importance"] + 0.05, 1.0)

        conn.execute(
            """UPDATE memory_items
               SET knowledge = ?, topics = ?, source_papers = ?, importance = ?
               WHERE id = ?""",
            (
                merged_knowledge,
                json.dumps(merged_topics, ensure_ascii=False),
                json.dumps(merged_papers, ensure_ascii=False),
                new_importance, memory_id,
            ),
        )
        conn.commit()
        conn.close()

        # 若 knowledge 变了，更新 ChromaDB 向量
        if merged_knowledge != row["knowledge"]:
            try:
                self._vectorstore.update_document(
                    memory_id,
                    Document(page_content=merged_knowledge,
                             metadata={"memory_id": memory_id}),
                )
            except Exception:
                pass

    def _boost_importance(self, memory_id: str, boost: float):
        """给某条记忆的 importance 增加 boost（上限 1.0）"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT importance FROM memory_items WHERE id = ?", (memory_id,)
        ).fetchone()
        if row:
            new_importance = min(row["importance"] + boost, 1.0)
            conn.execute(
                "UPDATE memory_items SET importance = ? WHERE id = ?",
                (new_importance, memory_id),
            )
            conn.commit()
        conn.close()

    # ================= 检索 + 复合排序 =================

    def search_memories(self, query: str, user_id: str, k: int = 3) -> list[dict]:
        """
        向量检索 + 复合排序，返回 Top-K 记忆。
        复合分数 = similarity*0.7 + importance*0.2 + min(access_count/10, 0.1)
        命中后更新 access_count / last_accessed，并强化 importance +0.05。
        """
        # 多取一些候选再重排
        try:
            results = self._vectorstore.similarity_search_with_score(
                query, k=k * 3, filter={"user_id": user_id}
            )
        except Exception:
            return []

        if not results:
            return []

        # 取候选记忆的元数据
        candidates = []
        for doc, distance in results:
            memory_id = doc.metadata.get("memory_id")
            if not memory_id:
                continue
            meta = self._get_memory_row(memory_id)
            if not meta or meta["status"] != "active":
                continue
            similarity = 1.0 - distance  # cosine distance → similarity
            importance = meta["importance"]
            access_count = meta["access_count"]
            final_score = (
                similarity * 0.7
                + importance * 0.2
                + min(access_count / 10, 0.1)
            )
            candidates.append((final_score, memory_id, meta))

        candidates.sort(key=lambda x: x[0], reverse=True)
        top = candidates[:k]

        # 更新访问统计 + 强化
        now = datetime.now().isoformat()
        conn = self._get_conn()
        for _, memory_id, _ in top:
            conn.execute(
                """UPDATE memory_items
                   SET access_count = access_count + 1,
                       last_accessed = ?,
                       importance = MIN(importance + 0.05, 1.0)
                   WHERE id = ?""",
                (now, memory_id),
            )
        conn.commit()
        conn.close()

        return [self._row_to_dict(meta) for _, _, meta in top]

    # ================= topics 频率统计 =================

    def get_top_topics(self, user_id: str, limit: int = 5) -> list[str]:
        """从所有活跃记忆的 topics 字段展开统计频率，返回 Top-N"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT topics FROM memory_items WHERE user_id = ? AND status = 'active'",
            (user_id,),
        ).fetchall()
        conn.close()

        freq: dict[str, int] = {}
        for r in rows:
            try:
                topics = json.loads(r["topics"] or "[]")
            except (json.JSONDecodeError, TypeError):
                topics = []
            for t in topics:
                freq[t] = freq.get(t, 0) + 1

        ranked = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
        return [t for t, _ in ranked[:limit]]

    # ================= 基础 CRUD =================

    def get_memory_count(self, user_id: str) -> int:
        """统计某用户的活跃记忆条数"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM memory_items WHERE user_id = ? AND status = 'active'",
            (user_id,),
        ).fetchone()
        conn.close()
        return row["c"] if row else 0

    def list_memories(self, user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        """列出记忆，按 importance 降序，支持分页"""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM memory_items
               WHERE user_id = ? AND status = 'active'
               ORDER BY importance DESC, created_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def delete_memory(self, memory_id: str, user_id: str) -> bool:
        """删除一条记忆（同时删 SQLite + ChromaDB），校验归属"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id FROM memory_items WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        ).fetchone()
        if not row:
            conn.close()
            return False
        conn.execute("DELETE FROM memory_items WHERE id = ?", (memory_id,))
        conn.commit()
        conn.close()

        try:
            self._vectorstore.delete(ids=[memory_id])
        except Exception:
            pass
        return True

    def mark_memory_used(self, memory_id: str):
        """记忆被 AI 回答引用时 times_used +1（效果追踪）"""
        conn = self._get_conn()
        conn.execute(
            "UPDATE memory_items SET times_used = times_used + 1 WHERE id = ?",
            (memory_id,),
        )
        conn.commit()
        conn.close()

    def get_last_memory_in_session(self, session_id: str) -> Optional[str]:
        """获取某会话中最近创建的记忆 ID（用于 prev_memory_id 认知轨迹链）"""
        if not session_id:
            return None
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id FROM memory_items WHERE source_session = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        conn.close()
        return row["id"] if row else None

    # ================= 画像缓存 =================

    def get_cached_profile(self, user_id: str) -> Optional[dict]:
        """读取缓存的用户画像，不存在返回 None"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def save_profile(self, user_id: str, profile_text: str, interaction_count: int):
        """写入/更新用户画像缓存"""
        now = datetime.now().isoformat()
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT user_id FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE user_profiles
                   SET profile_text = ?, interaction_count = ?, updated_at = ?
                   WHERE user_id = ?""",
                (profile_text, interaction_count, now, user_id),
            )
        else:
            conn.execute(
                """INSERT INTO user_profiles
                   (user_id, profile_text, interaction_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, profile_text, interaction_count, now, now),
            )
        conn.commit()
        conn.close()

    # ================= 辅助方法 =================

    def _get_memory_row(self, memory_id: str) -> Optional[sqlite3.Row]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM memory_items WHERE id = ?", (memory_id,)
        ).fetchone()
        conn.close()
        return row

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """SQLite Row → dict，topics/source_papers 反序列化为 list"""
        d = dict(row)
        for field in ("topics", "source_papers"):
            if field in d:
                try:
                    d[field] = json.loads(d[field] or "[]")
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        return d
