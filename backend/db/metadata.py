"""
PostgreSQL 元数据提取模块
从数据库中提取表结构、字段信息和注释
"""

from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config import get_settings


@dataclass
class ColumnMetadata:
    """字段元数据"""
    name: str                          # 字段名
    data_type: str                     # 数据类型
    original_name: Optional[str] = None # 原始字段名（来源文件中的列名）
    comment: Optional[str] = None      # 字段注释
    is_nullable: bool = True           # 是否可为空
    is_primary_key: bool = False       # 是否为主键
    id: Optional[str] = None          # meta.logical_columns.id（若存在）


@dataclass
class TableMetadata:
    """表元数据"""
    name: str                                      # 表名
    schema: str = "public"                         # Schema 名
    comment: Optional[str] = None                  # 表注释
    display_name: Optional[str] = None             # 中文显示名（meta.logical_tables.display_name）
    id: Optional[str] = None                       # meta.logical_tables.id（若存在）
    columns: List[ColumnMetadata] = field(default_factory=list)  # 字段列表

    @property
    def full_name(self) -> str:
        """返回完整表名 (schema.table)"""
        return f"{self.schema}.{self.name}"


def get_all_tables_metadata(engine: Engine) -> List[TableMetadata]:
    """
    从 PostgreSQL 数据库提取所有表的元数据
    包括表名、表注释、字段名、字段类型、字段注释等
    
    Args:
        engine: SQLAlchemy 数据库引擎
        
    Returns:
        List[TableMetadata]: 表元数据列表
    """
    settings = get_settings()
    schema = settings.pg_schema
    
    # 使用 pg_catalog 获取注释，LEFT JOIN meta.logical_tables / logical_columns 补充 id 和 display_name
    query = text("""
SELECT
    t.table_name,
    t.table_schema,
    obj_description(
        (quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass,
        'pg_class'
    ) AS table_comment,
    mt.id          AS logical_table_id,
    mt.display_name AS display_name,
    c.column_name,
    c.data_type,
    c.is_nullable,
    c.ordinal_position,
    col_description(
        (quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass,
        c.ordinal_position
    ) AS column_comment,
    CASE
        WHEN pk.column_name IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS is_primary_key,
    mc.id AS logical_col_id,
    mc.original_name AS original_name
FROM information_schema.tables t
JOIN information_schema.columns c
    ON t.table_schema = c.table_schema
    AND t.table_name = c.table_name
LEFT JOIN meta.logical_tables mt
    ON mt.physical_schema = t.table_schema
    AND mt.physical_name = t.table_name
LEFT JOIN meta.logical_columns mc
    ON mc.table_id = mt.id
    AND mc.physical_name = c.column_name
    AND mc.is_active = true
LEFT JOIN (
    SELECT
        kcu.table_schema,
        kcu.table_name,
        kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'PRIMARY KEY'
) pk
    ON c.table_schema = pk.table_schema
    AND c.table_name = pk.table_name
    AND c.column_name = pk.column_name
WHERE t.table_schema = :schema
  AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name, c.ordinal_position;
    """)
    
    tables_dict = {}
    
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": schema})
        
        for row in result:
            table_name = row.table_name

            if table_name not in tables_dict:
                tables_dict[table_name] = TableMetadata(
                    name=table_name,
                    schema=row.table_schema,
                    comment=row.table_comment,
                    display_name=row.display_name,
                    id=row.logical_table_id,
                    columns=[],
                )

            column = ColumnMetadata(
                name=row.column_name,
                data_type=row.data_type,
                original_name=row.original_name,
                comment=row.column_comment,
                is_nullable=(row.is_nullable == "YES"),
                is_primary_key=row.is_primary_key,
                id=row.logical_col_id,
            )
            tables_dict[table_name].columns.append(column)
    
    return list(tables_dict.values())


def format_table_as_document(table: TableMetadata) -> str:
    """
    将表元数据格式化为文档字符串
    用于向量化存储和检索
    
    Args:
        table: 表元数据对象
        
    Returns:
        str: 格式化后的文档字符串
        
    Example:
        英文表名: users
        表注释: 用户基础信息表
        字段列表:
        - id (integer) [PK]: 用户唯一标识
        - username (varchar): 用户名
        - created_at (timestamp): 创建时间
    """
    lines = [f"英文表名: {table.name}"]
    
    if table.comment:
        lines.append(f"表注释: {table.comment}")
    else:
        lines.append("表注释: 无")
    
    lines.append("字段列表:")
    
    for col in table.columns:
        # 构建字段描述
        pk_marker = " [PK]" if col.is_primary_key else ""
        nullable_marker = " [可空]" if col.is_nullable and not col.is_primary_key else ""
        
        col_desc = f"- {col.name} ({col.data_type}){pk_marker}{nullable_marker}"
        
        if col.comment:
            col_desc += f": {col.comment}"
        
        lines.append(col_desc)
    
    return "\n".join(lines)


def get_table_names(engine: Engine) -> List[str]:
    """
    获取数据库中所有表名
    
    Args:
        engine: SQLAlchemy 数据库引擎
        
    Returns:
        List[str]: 表名列表
    """
    settings = get_settings()
    
    query = text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = :schema 
            AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": settings.pg_schema})
        return [row.table_name for row in result]

