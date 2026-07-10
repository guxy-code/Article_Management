"""
标注存储模块 - 基于 SQLite
负责持久化管理 PDF 标注（高亮、笔记）。
"""

import os
import sqlite3
import uuid
import json
from datetime import datetime
from typing import Optional


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions.db")


class AnnotationStore:
    """SQLite 标注持久化存储"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS annotations (
                id TEXT PRIMARY KEY,
                paper_title TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'system',
                page INTEGER NOT NULL,
                text TEXT NOT NULL,
                note TEXT DEFAULT '',
                color TEXT DEFAULT 'yellow',
                type TEXT DEFAULT 'highlight',
                rects TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_annotations_paper
                ON annotations(paper_title);
        """)
        # 迁移：补充 type 列
        try:
            conn.execute("ALTER TABLE annotations ADD COLUMN type TEXT DEFAULT 'highlight'")
            conn.commit()
        except Exception:
            pass
        # 迁移：补充 user_id 列
        try:
            conn.execute("ALTER TABLE annotations ADD COLUMN user_id TEXT NOT NULL DEFAULT 'system'")
            conn.commit()
        except Exception:
            pass
        # 迁移完成后再创建依赖 user_id 的索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_annotations_user ON annotations(user_id, paper_title)")
        conn.commit()
        conn.close()

    def create(self, paper_title: str, page: int, text: str, note: str, color: str, rects: list, type: str = "highlight", user_id: str = "system") -> dict:
        """创建标注"""
        conn = self._get_conn()
        annotation_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn.execute(
            """INSERT INTO annotations (id, paper_title, user_id, page, text, note, color, type, rects, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (annotation_id, paper_title, user_id, page, text, note, color, type, json.dumps(rects), now),
        )
        conn.commit()
        conn.close()

        return {
            "id": annotation_id,
            "paper_title": paper_title,
            "page": page,
            "text": text,
            "note": note,
            "color": color,
            "type": type,
            "rects": rects,
            "created_at": now,
        }

    def list_by_paper(self, paper_title: str, user_id: str = "system") -> list:
        """获取某篇论文当前用户的所有标注"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM annotations WHERE paper_title = ? AND user_id = ? ORDER BY page, created_at",
            (paper_title, user_id),
        ).fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def update(self, annotation_id: str, note: Optional[str] = None, color: Optional[str] = None, user_id: Optional[str] = None) -> bool:
        """更新标注（笔记或颜色），可选验证归属"""
        conn = self._get_conn()
        fields = []
        values = []

        if note is not None:
            fields.append("note = ?")
            values.append(note)
        if color is not None:
            fields.append("color = ?")
            values.append(color)

        if not fields:
            return False

        if user_id:
            values.extend([annotation_id, user_id])
            conn.execute(
                f"UPDATE annotations SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                values,
            )
        else:
            values.append(annotation_id)
            conn.execute(
                f"UPDATE annotations SET {', '.join(fields)} WHERE id = ?",
                values,
            )
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return affected > 0

    def delete(self, annotation_id: str, user_id: Optional[str] = None) -> bool:
        """删除标注，可选验证归属"""
        conn = self._get_conn()
        if user_id:
            cursor = conn.execute(
                "DELETE FROM annotations WHERE id = ? AND user_id = ?",
                (annotation_id, user_id),
            )
        else:
            cursor = conn.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def delete_by_paper(self, paper_title: str, user_id: str = "system") -> int:
        """删除某篇论文当前用户的所有标注，返回删除条数"""
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM annotations WHERE paper_title = ? AND user_id = ?",
            (paper_title, user_id),
        )
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        return deleted

    def _row_to_dict(self, row) -> dict:
        try:
            annotation_type = row["type"] or "highlight"
        except (IndexError, KeyError):
            annotation_type = "highlight"
        return {
            "id": row["id"],
            "paper_title": row["paper_title"],
            "page": row["page"],
            "text": row["text"],
            "note": row["note"],
            "color": row["color"],
            "type": annotation_type,
            "rects": json.loads(row["rects"]),
            "created_at": row["created_at"],
        }
