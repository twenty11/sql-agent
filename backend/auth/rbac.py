"""RBAC 表级权限服务

核心逻辑：
1. 查询用户可访问的表名列表（DB → Redis 缓存 5 分钟）
2. 根据白名单过滤 retrieved_schemas（在 generate_sql 前注入）
"""

import json
import re
from typing import Optional

import redis.asyncio as aioredis

from config import get_settings


_CACHE_TTL = 300  # 5 分钟


def _cache_key(user_id: str) -> str:
    return f"rbac:{user_id}:tables"


async def invalidate_user_cache(user_id: str, redis: aioredis.Redis) -> None:
    """使单个用户的表权限缓存失效。"""
    await redis.delete(_cache_key(user_id))


async def invalidate_users_cache(user_ids: list[str], redis: aioredis.Redis) -> None:
    """批量失效多个用户的表权限缓存（角色权限变更时调用）。"""
    if not user_ids:
        return
    keys = [_cache_key(uid) for uid in user_ids]
    await redis.delete(*keys)


async def get_user_allowed_tables(user_id: str, redis: aioredis.Redis, db) -> Optional[list[str]]:
    """
    返回用户有权限查询的表名白名单。

    语义：
      - 返回 None   → admin 角色，无限制
      - 返回 list  → 显式白名单；空列表 `[]` 表示拒绝所有表

    先查 Redis 缓存（存 JSON null 表示 admin），未命中则查 DB 并写入缓存。
    """
    cache_key = _cache_key(user_id)
    cached = await redis.get(cache_key)
    if cached is not None:
        val = json.loads(cached)
        return None if val is None else val

    from db.crud.roles import get_allowed_tables_for_user
    tables = await get_allowed_tables_for_user(db, user_id)

    await redis.setex(cache_key, _CACHE_TTL, json.dumps(tables))
    return tables


def filter_schemas_by_permission(
    schemas: list[str],
    allowed_tables: Optional[list[str]],
) -> list[str]:
    """
    根据允许的表名白名单过滤 retrieved_schemas。

    allowed_tables=None 表示不限制（admin），直接返回原始列表；
    allowed_tables=[] 表示不允许任何表，返回空列表。
    """
    if allowed_tables is None:
        return schemas

    allowed_set = {t.lower() for t in allowed_tables}
    filtered = []
    for schema in schemas:
        # 从 schema 文档中提取表名（格式: "英文表名: xxx"）
        match = re.search(r'英文表名:\s*(\w+)', schema)
        if match:
            table_name = match.group(1).lower()
            if table_name in allowed_set:
                filtered.append(schema)
    return filtered


def extract_tables_from_sql(sql: str) -> list[str]:
    """从 SQL 中提取所有引用的表名（用于 AST 级权限校验）"""
    import sqlparse
    from sqlparse.sql import IdentifierList, Identifier, Where
    from sqlparse.tokens import Keyword, DML

    tables = []
    parsed = sqlparse.parse(sql)
    if not parsed:
        return tables

    stmt = parsed[0]
    from_seen = False

    for token in stmt.flatten():
        if token.ttype is DML and token.value.upper() == "SELECT":
            from_seen = False
        if token.ttype is Keyword and token.value.upper() in ("FROM", "JOIN"):
            from_seen = True
            continue
        if from_seen and token.ttype is None:
            tables.append(token.value.strip('"').strip("'").lower())
            from_seen = False
        elif from_seen and token.ttype not in (Keyword,):
            from_seen = False

    # 备用简单正则提取
    if not tables:
        pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        tables = [m.lower() for m in re.findall(pattern, sql, re.IGNORECASE)]

    return list(set(tables))
