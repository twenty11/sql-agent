"""
PostgreSQL 数据库连接管理模块
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection

from config import get_settings


def get_engine() -> Engine:
    """
    创建并返回 SQLAlchemy 数据库引擎
    
    Returns:
        Engine: SQLAlchemy 数据库引擎实例
    """
    settings = get_settings()
    engine = create_engine(
        settings.pg_connection_string,
        pool_pre_ping=True,  # 连接池健康检查
        pool_size=5,
        max_overflow=10,
    )
    return engine


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    """
    获取数据库连接的上下文管理器
    
    Yields:
        Connection: SQLAlchemy 数据库连接
        
    Example:
        with get_connection() as conn:
            result = conn.execute(text("SELECT 1"))
    """
    engine = get_engine()
    with engine.connect() as connection:
        yield connection


def test_connection() -> bool:
    """
    测试数据库连接是否正常
    
    Returns:
        bool: 连接成功返回 True，否则返回 False
    """
    try:
        with get_connection() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"数据库连接测试失败: {e}")
        return False

