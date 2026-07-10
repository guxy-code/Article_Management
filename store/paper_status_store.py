"""
论文阅读状态存储模块 - 基于 SQLite
管理论文的阅读状态（unread / reading / read），支持多用户隔离。
"""

import os
import uuid
import sqlite3
from datetime import datetime
from typing import Optional


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions.db")


class PaperStatusStore:
    """SQLite 论文阅读状态持久化存储"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_status (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                paper_title TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'unread',
                updated_at  TEXT NOT NULL,
                UNIQUE(user_id, paper_title)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_paper_status_user "
            "ON paper_status(user_id)"
        )
        conn.commit()
        conn.close()

    def get_all(self, user_id: str) -> dict[str, str]:
        """获取当前用户所有论文的阅读状态，返回 {title: status}"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT paper_title, status FROM paper_status WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        conn.close()
        return {row["paper_title"]: row["status"] for row in rows}

    def upsert(self, paper_title: str, status: str, user_id: str = "system"):
        """插入或更新论文阅读状态"""
        conn = self._get_conn()
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO paper_status (id, user_id, paper_title, status, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, paper_title)
            DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
            """,
            (str(uuid.uuid4()), user_id, paper_title, status, now),
        )
        conn.commit()
        conn.close()

    def delete_by_paper(self, paper_title: str, user_id: str = "system"):
        """删除某篇论文的阅读状态记录"""
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM paper_status WHERE paper_title = ? AND user_id = ?",
            (paper_title, user_id),
        )
        conn.commit()
        conn.close()
