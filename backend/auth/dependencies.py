"""FastAPI dependencies for authentication and role checks."""

import threading
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt_handler import decode_access_token
from config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)

_redis_client: Optional[aioredis.Redis] = None
_redis_lock = threading.Lock()


def get_redis() -> aioredis.Redis:
    """Return a process-level async Redis client."""
    global _redis_client
    if _redis_client is None:
        with _redis_lock:
            if _redis_client is None:
                settings = get_settings()
                _redis_client = aioredis.from_url(
                    settings.redis_url, decode_responses=True
                )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection pool during application shutdown."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except AttributeError:
            await _redis_client.close()
        finally:
            _redis_client = None


class UserContext:
    """Current authenticated user context."""

    def __init__(
        self,
        user_id: str,
        roles: list[str],
        token_payload: Optional[dict] = None,
    ):
        self.user_id = user_id
        self.roles = roles
        self.token_payload = token_payload or {}

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> UserContext:
    """Authenticate regular API requests from the Authorization header."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _get_user_context_from_token(credentials.credentials)


async def get_current_user_from_header_or_query(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    token: Optional[str] = Query(default=None),
) -> UserContext:
    """
    Authenticate SSE requests.

    Native browser EventSource cannot send custom Authorization headers, so
    /api/query passes the access token as a query parameter.
    """
    token_value = credentials.credentials if credentials else token
    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _get_user_context_from_token(token_value)


async def _get_user_context_from_token(token: str) -> UserContext:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti", "")
    redis = get_redis()
    if await redis.exists(f"jwt:blacklist:{jti}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    return UserContext(
        user_id=payload["sub"],
        roles=payload.get("roles", []),
        token_payload=payload,
    )


def require_admin(user: UserContext = Depends(get_current_user)) -> UserContext:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required",
        )
    return user
