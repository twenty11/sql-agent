"""
PostgreSQL 数据库连接管理模块
"""

from contextlib import contextmanager
import threading
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection

from config import get_settings


_engine: Engine | None = None
_engine_lock = threading.Lock()


def get_engine() -> Engine:
    """
    获取进程级 SQLAlchemy 数据库引擎。

    同步查询链路、上传任务和向量同步会频繁调用本函数。Engine 必须复用，
    否则每次调用都会创建新的连接池，导致多人并发时快速耗尽 PostgreSQL 连接。
    
    Returns:
        Engine: SQLAlchemy 数据库引擎实例
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                settings = get_settings()
                _engine = create_engine(
                    settings.pg_connection_string,
                    pool_pre_ping=True,  # 连接池健康检查
                    pool_size=5,
                    max_overflow=10,
                )
    return _engine


def dispose_engine() -> None:
    """释放进程级同步数据库引擎及其连接池。"""
    global _engine
    with _engine_lock:
        if _engine is None:
            return
        _engine.dispose()
        _engine = None


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

