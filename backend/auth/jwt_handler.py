"""JWT Token 生成与验证"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _settings():
    return get_settings()


def create_access_token(user_id: str, roles: list[str]) -> str:
    """生成短期 Access Token（30 分钟）"""
    s = _settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_expire_minutes),
        "jti": secrets.token_hex(16),
        "type": "access",
    }
    return jwt.encode(payload, s.jwt_secret_key, algorithm=s.jwt_algorithm)


def create_refresh_token() -> tuple[str, str]:
    """
    生成不透明 Refresh Token。
    返回 (raw_token, token_hash)，raw_token 给客户端，hash 存 DB。
    """
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def decode_access_token(token: str) -> Optional[dict]:
    """解码 Access Token，失败返回 None"""
    try:
        s = _settings()
        payload = jwt.decode(token, s.jwt_secret_key, algorithms=[s.jwt_algorithm])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()
