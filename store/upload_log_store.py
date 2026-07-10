"""
上传日志存储模块 - 基于 SQLite
记录论文上传历史，用于 Dashboard 的上传活动统计。
"""

import os
import uuid
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions.db")


class UploadLogStore:
    """SQLite 上传日志持久化存储"""

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
            CREATE TABLE IF NOT EXISTS upload_logs (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                user_id     TEXT NOT NULL DEFAULT 'system',
                upload_date TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_upload_logs_user_date "
            "ON upload_logs(user_id, upload_date)"
        )
        conn.commit()
        conn.close()

    def log(self, title: str, user_id: str = "system"):
        """记录一次上传"""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO upload_logs (id, title, user_id, upload_date) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), title, user_id, datetime.now().strftime("%Y-%m-%d")),
        )
        conn.commit()
        conn.close()

    def get_recent_7days(self, user_id: str) -> list[dict]:
        """获取当前用户最近 7 天每天上传论文数量"""
        conn = self._get_conn()
        today = datetime.now().date()
        days = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM upload_logs WHERE user_id = ? AND upload_date = ?",
                (user_id, date_str),
            ).fetchone()
            days.append({"date": date_str, "label": d.strftime("%m/%d"), "count": row["count"]})
        conn.close()
        return days

    def migrate_from_json(self, json_path: str):
        """从旧版 JSON 文件迁移数据到 SQLite（仅执行一次）"""
        if not os.path.exists(json_path):
            return
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        if not logs:
            return
        conn = self._get_conn()
        for entry in logs:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO upload_logs (id, title, user_id, upload_date) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()),
                     entry.get("title", ""),
                     entry.get("user_id", "system"),
                     entry.get("date", "")),
                )
            except Exception:
                pass
        conn.commit()
        conn.close()
