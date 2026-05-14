"""异步 SQLAlchemy 引擎和会话工厂（供业务 CRUD 使用）

原有同步引擎（db/connection.py）保持不变，LangGraph 节点继续使用同步引擎。
本模块仅供 FastAPI 路由和 auth/crud 模块使用。
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from config import get_settings


@lru_cache()
def get_async_engine():
    settings = get_settings()
    # 将 postgresql:// 替换为 postgresql+asyncpg://
    url = settings.pg_connection_string.replace(
        "postgresql://", "postgresql+asyncpg://"
    ).split("?")[0]  # asyncpg 不支持 options 参数，连接后再设置 search_path
    return create_async_engine(
        url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )


AsyncSessionLocal = async_sessionmaker(
    bind=get_async_engine(),
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncSession:
    """FastAPI Depends 异步会话生成器"""
    async with AsyncSessionLocal() as session:
        yield session
