"""
数据库模块
包含 PostgreSQL 连接管理和元数据提取功能
"""

from .connection import get_engine, get_connection
from .metadata import (
    ColumnMetadata,
    TableMetadata,
    get_all_tables_metadata,
    format_table_as_document
)

__all__ = [
    "get_engine",
    "get_connection",
    "ColumnMetadata",
    "TableMetadata",
    "get_all_tables_metadata",
    "format_table_as_document",
]
