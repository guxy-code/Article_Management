"""
会话存储模块 - 基于 SQLite
负责持久化管理所有对话会话及消息。
"""

import os
import sqlite3
import uuid
from datetime import datetime
from typing import Optional


DB_PATH = os.getenv("DB_PATH") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions.db")


class SessionStore:
    """SQLite 会话持久化存储"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT DEFAULT 'New Chat',
                summary TEXT DEFAULT '',
                user_id TEXT NOT NULL DEFAULT 'system',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session 
                ON messages(session_id, created_at);
        """)
        # 迁移：已有 sessions 表若无 user_id 列则补上
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT NOT NULL DEFAULT 'system'")
            conn.commit()
        except Exception:
            pass  # 列已存在
        # 迁移完成后再创建依赖 user_id 的索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, updated_at)")
        conn.commit()
        conn.close()

    def create_session(self, user_id: str = "system") -> dict:
        """创建新会话，返回会话信息"""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO sessions (id, title, summary, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, "New Chat", "", user_id, now, now),
        )
        conn.commit()
        conn.close()
        return {"id": session_id, "title": "New Chat", "summary": "", "created_at": now, "updated_at": now}

    def list_sessions(self, user_id: str = "system") -> list[dict]:
        """列出该用户的所有会话，按更新时间倒序"""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT s.id, s.title, s.updated_at, s.created_at,
                   COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            WHERE s.user_id = ?
            GROUP BY s.id
            ORDER BY s.updated_at DESC
        """, (user_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str, user_id: Optional[str] = None) -> Optional[dict]:
        """获取会话详情，可选验证归属"""
        conn = self._get_conn()
        if user_id:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def delete_session(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """删除会话及其所有消息，可选验证归属"""
        conn = self._get_conn()
        if user_id:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            )
        else:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    def add_message(self, session_id: str, role: str, content: str, sources: str = "[]") -> dict:
        """添加一条消息到会话"""
        import json

        msg_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = self._get_conn()
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, role, content, sources, now),
        )
        # 更新会话的 updated_at
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )
        conn.commit()
        conn.close()
        return {"id": msg_id, "session_id": session_id, "role": role, "content": content, "sources": sources, "created_at": now}

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> list[dict]:
        """获取会话的所有消息，按时间正序"""
        conn = self._get_conn()
        if limit:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_recent_messages(self, session_id: str, n: int = 4) -> list[dict]:
        """获取最近 n 条消息（用于 query 改写等轻量场景）"""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM (
                SELECT * FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?
            ) ORDER BY created_at ASC""",
            (session_id, n),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_summary(self, session_id: str, summary: str):
        """更新会话摘要"""
        conn = self._get_conn()
        conn.execute(
            "UPDATE sessions SET summary = ? WHERE id = ?", (summary, session_id)
        )
        conn.commit()
        conn.close()

    def update_title(self, session_id: str, title: str):
        """更新会话标题"""
        conn = self._get_conn()
        conn.execute(
            "UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)
        )
        conn.commit()
        conn.close()
