"""
JWT 处理模块
负责 Access Token 的生成与验证。
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, status


# 从环境变量读取配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "papermind-dev-secret-change-in-production")
ALGORITHM = "HS256"
EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "168"))  # 默认 7 天


def create_access_token(user_id: str, username: str) -> str:
    """
    生成 JWT Access Token。

    Args:
        user_id: 用户 UUID
        username: 用户名（存入 payload 方便前端直接解析）

    Returns:
        JWT token 字符串
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    验证并解码 JWT Token。

    Args:
        token: JWT token 字符串

    Returns:
        payload dict，包含 sub (user_id)、username、exp

    Raises:
        HTTPException 401: token 无效或已过期
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证失败，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception
