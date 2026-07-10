"""
用户存储模块 - 基于 SQLite
负责用户账号的注册、登录验证、信息查询。
密码使用 bcrypt 哈希，不存明文。
"""

import os
import sqlite3
import uuid
import hashlib
from datetime import datetime
from typing import Optional

import bcrypt


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions.db")


def _pre_hash(password: str) -> bytes:
    """SHA-256 预哈希，将任意长度密码转为固定 64 字节，规避 bcrypt 72 字节限制"""
    return hashlib.sha256(password.encode("utf-8")).digest()


class UserStore:
    """用户账号持久化存储"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        """创建 users 表（如果不存在）"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                email         TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_username
                ON users(username);
        """)
        conn.commit()
        conn.close()

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
    ) -> dict:
        """
        注册新用户。

        Args:
            username: 用户名（唯一）
            password: 明文密码（将被 bcrypt 哈希后存储）
            email: 邮箱（可选，唯一）

        Returns:
            用户信息 dict（不含密码哈希）

        Raises:
            ValueError: 用户名或邮箱已存在
        """
        user_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        password_hash = bcrypt.hashpw(_pre_hash(password), bcrypt.gensalt()).decode("utf-8")

        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO users (id, username, email, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username.strip(), email, password_hash, now),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.close()
            if "username" in str(e):
                raise ValueError(f"用户名 '{username}' 已被注册")
            elif "email" in str(e):
                raise ValueError(f"邮箱 '{email}' 已被注册")
            raise ValueError("注册失败，请检查输入")
        finally:
            conn.close()

        return {
            "id": user_id,
            "username": username.strip(),
            "email": email,
            "created_at": now,
        }

    def get_user_by_username(self, username: str) -> Optional[dict]:
        """根据用户名查询用户（含密码哈希，用于登录验证）"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """根据 ID 查询用户（不含密码哈希）"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证明文密码与哈希是否匹配"""
        return bcrypt.checkpw(_pre_hash(plain_password), hashed_password.encode("utf-8"))

    def update_password(self, user_id: str, new_password: str) -> bool:
        """修改用户密码"""
        password_hash = bcrypt.hashpw(_pre_hash(new_password), bcrypt.gensalt()).decode("utf-8")
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    def update_user_info(self, user_id: str, username: Optional[str] = None, email: Optional[str] = None) -> dict:
        """
        更新用户名和/或邮箱。

        Returns:
            更新后的用户信息 dict

        Raises:
            ValueError: 用户名或邮箱已被占用
        """
        conn = self._get_conn()
        fields = []
        values = []
        if username is not None:
            fields.append("username = ?")
            values.append(username.strip())
        if email is not None:
            fields.append("email = ?")
            values.append(email.strip() if email else None)
        if not fields:
            conn.close()
            return self.get_user_by_id(user_id)
        values.append(user_id)
        try:
            conn.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.close()
            if "username" in str(e):
                raise ValueError("用户名已被占用")
            elif "email" in str(e):
                raise ValueError("邮箱已被占用")
            raise ValueError("更新失败，请检查输入")
        finally:
            conn.close()
        return self.get_user_by_id(user_id)
