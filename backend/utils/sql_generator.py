"""
SQL生成模块 - 根据JSON配置生成PostgreSQL数据库可导入的SQL文件
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import pandas as pd

from utils.data_loader import read_data_file
from utils.json_schema_generator import load_schema_from_json, load_all_schemas
from config import get_settings

settings = get_settings()
DB_SCHEMA = settings.pg_schema
DEFAULT_SQL_DIR = Path(__file__).parent / "output/sql"

def escape_sql_string(value: Any) -> str:
    """
    转义SQL字符串中的特殊字符

    Args:
        value: 原始值

    Returns:
        转义后的字符串
    """
    if pd.isna(value) or value is None:
        return "NULL"

    # 转换为字符串
    str_value = str(value)

    # 转义单引号（必须首先转义，否则会影响其他转义）
    str_value = str_value.replace("'", "''")

    # 转义反斜杠（如果需要）
    str_value = str_value.replace("\\", "\\\\")

    return f"'{str_value}'"


def generate_drop_table_sql(table_name: str, schema: str = DB_SCHEMA) -> str:
    """生成DROP TABLE语句"""
    full_table_name = f"{schema}.{table_name}" if schema != "public" else table_name
    return f"DROP TABLE IF EXISTS {full_table_name};"


def generate_create_table_sql(schema_config: Dict[str, Any], db_schema: str = DB_SCHEMA) -> str:
    """
    生成CREATE TABLE语句
    
    Args:
        schema_config: JSON配置字典
        db_schema: 数据库schema名
        
    Returns:
        CREATE TABLE SQL语句
    """
    table_name = schema_config["table_name"]
    columns = schema_config["columns"]
    
    full_table_name = f"{db_schema}.{table_name}" if db_schema != "public" else table_name
    
    # 构建列定义
    column_defs = []
    for col in columns:
        col_name = col["column_name"]
        col_type = col.get("data_type", "TEXT")
        column_defs.append(f"    {col_name} {col_type}")
    
    columns_sql = ",\n".join(column_defs)
    
    return f"CREATE TABLE {full_table_name} (\n{columns_sql}\n);"


def generate_comment_sql(schema_config: Dict[str, Any], db_schema: str = DB_SCHEMA) -> str:
    """
    生成COMMENT语句（表注释和字段注释）
    
    Args:
        schema_config: JSON配置字典
        db_schema: 数据库schema名
        
    Returns:
        COMMENT SQL语句
    """
    table_name = schema_config["table_name"]
    table_comment = schema_config["table_comment"]
    columns = schema_config["columns"]
    
    full_table_name = f"{db_schema}.{table_name}" if db_schema != "public" else table_name
    
    lines = []
    
    # 表注释
    escaped_table_comment = table_comment.replace("'", "''")
    lines.append(f"COMMENT ON TABLE {full_table_name} IS '{escaped_table_comment}';")
    
    # 字段注释
    for col in columns:
        col_name = col["column_name"]
        col_comment = col["column_comment"].replace("'", "''")
        lines.append(f"COMMENT ON COLUMN {full_table_name}.{col_name} IS '{col_comment}';")
    
    return "\n".join(lines)


def generate_insert_sql(
    schema_config: Dict[str, Any],
    df: pd.DataFrame,
    db_schema: str = DB_SCHEMA,
    batch_size: int = 100
) -> str:
    """
    生成INSERT语句
    
    Args:
        schema_config: JSON配置字典
        df: 源数据DataFrame
        db_schema: 数据库schema名
        batch_size: 每批INSERT的行数
        
    Returns:
        INSERT SQL语句
    """
    table_name = schema_config["table_name"]
    columns = schema_config["columns"]
    
    full_table_name = f"{db_schema}.{table_name}" if db_schema != "public" else table_name
    
    # 构建原始字段名到新字段名的映射
    column_mapping = {col["original_name"]: col["column_name"] for col in columns}
    
    # 新字段名列表（按配置顺序）
    new_column_names = [col["column_name"] for col in columns]
    original_column_names = [col["original_name"] for col in columns]
    
    columns_str = ", ".join(new_column_names)
    
    # 生成INSERT语句
    insert_statements = []
    
    for i in range(0, len(df), batch_size):
        batch_df = df.iloc[i:i + batch_size]
        values_list = []
        
        for _, row in batch_df.iterrows():
            row_values = []
            for orig_col in original_column_names:
                if orig_col in row.index:
                    row_values.append(escape_sql_string(row[orig_col]))
                else:
                    row_values.append("NULL")
            values_list.append(f"({', '.join(row_values)})")
        
        values_str = ",\n".join(values_list)
        insert_statements.append(
            f"INSERT INTO {full_table_name} ({columns_str}) VALUES\n{values_str};"
        )
    
    return "\n\n".join(insert_statements)


def generate_full_sql(
    schema_config: Dict[str, Any],
    db_schema: str = DB_SCHEMA,
    include_data: bool = True
) -> str:
    """
    生成完整的SQL文件内容
    
    Args:
        schema_config: JSON配置字典
        db_schema: 数据库schema名
        include_data: 是否包含INSERT语句
        
    Returns:
        完整的SQL内容
    """
    table_name = schema_config["table_name"]
    table_comment = schema_config["table_comment"]
    source_file = schema_config["source_file"]
    
    sql_parts = []
    
    # 文件头注释
    sql_parts.append(f"-- ============================================")
    sql_parts.append(f"-- 表名: {table_name}")
    sql_parts.append(f"-- 描述: {table_comment}")
    sql_parts.append(f"-- 源文件: {source_file}")
    sql_parts.append(f"-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sql_parts.append(f"-- ============================================")
    sql_parts.append("")
    
    # DROP TABLE
    sql_parts.append("-- 删除已存在的表")
    sql_parts.append(generate_drop_table_sql(table_name, db_schema))
    sql_parts.append("")
    
    # CREATE TABLE
    sql_parts.append("-- 创建表结构")
    sql_parts.append(generate_create_table_sql(schema_config, db_schema))
    sql_parts.append("")
    
    # COMMENT
    sql_parts.append("-- 添加表和字段注释")
    sql_parts.append(generate_comment_sql(schema_config, db_schema))
    sql_parts.append("")
    
    # INSERT DATA
    if include_data:
        # 从源文件读取数据
        try:
            df = read_data_file(source_file)
            sql_parts.append("-- 插入数据")
            sql_parts.append(generate_insert_sql(schema_config, df, db_schema))
        except Exception as e:
            sql_parts.append(f"-- 警告: 无法读取源数据文件，跳过INSERT语句")
            sql_parts.append(f"-- 错误信息: {e}")
    
    return "\n".join(sql_parts)


def save_sql_to_file(
    sql_content: str,
    table_name: str,
    output_dir: Optional[str | Path] = None
) -> Path:
    """
    将SQL内容保存到文件
    
    Args:
        sql_content: SQL内容
        table_name: 表名（用作文件名）
        output_dir: 输出目录
        
    Returns:
        保存的文件路径
    """
    if output_dir is None:
        output_dir = DEFAULT_SQL_DIR
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"{table_name}.sql"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(sql_content)
    
    return output_path


def generate_sql_from_schema_file(
    schema_path: str | Path,
    output_dir: Optional[str | Path] = None,
    include_data: bool = True
) -> Path:
    """
    从单个JSON配置文件生成SQL文件
    
    Args:
        schema_path: JSON配置文件路径
        output_dir: SQL输出目录
        include_data: 是否包含数据
        
    Returns:
        生成的SQL文件路径
    """
    schema_config = load_schema_from_json(schema_path)
    sql_content = generate_full_sql(schema_config, include_data=include_data)
    return save_sql_to_file(sql_content, schema_config["table_name"], output_dir)


def generate_all_sql_files(
    schema_dir: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
    include_data: bool = True
) -> List[Path]:
    """
    从所有JSON配置文件生成SQL文件
    
    Args:
        schema_dir: JSON配置文件目录
        output_dir: SQL输出目录
        include_data: 是否包含数据
        
    Returns:
        生成的SQL文件路径列表
    """
    schemas = load_all_schemas(schema_dir)
    
    if not schemas:
        print("未找到任何JSON配置文件")
        return []
    
    results = []
    total = len(schemas)
    
    for i, schema_config in enumerate(schemas, 1):
        table_name = schema_config["table_name"]
        # print(f"[{i}/{total}] 正在生成SQL: {table_name}...")
        
        try:
            sql_content = generate_full_sql(schema_config, include_data=include_data)
            sql_path = save_sql_to_file(sql_content, table_name, output_dir)
            results.append(sql_path)
            print(f"  ✓ 完成: {sql_path}")
        except Exception as e:
            print(f"  ✗ 失败: {e}")
    
    return results


if __name__ == "__main__":
    # 测试代码
    import sys
    
    if len(sys.argv) > 1:
        schema_path = sys.argv[1]
        output_path = generate_sql_from_schema_file(schema_path)
        print(f"SQL文件已生成: {output_path}")
    else:
        print("用法: python sql_generator.py <JSON配置文件路径>")

