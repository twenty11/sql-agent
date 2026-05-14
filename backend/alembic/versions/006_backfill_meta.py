"""回填现有业务表到 meta.* catalog

将 sql_agent.* 下已有的表/列按现有 information_schema 信息直接写入
meta.logical_tables 和 meta.logical_columns，不调用 LLM。

original_name 暂用 physical_name 占位（历史中文原名已丢失）；
admin 在下次上传相同表时可在 ReviewModal 中通过选择「视为同表数据刷新」跳过 LLM 重命名。

Revision ID: 006
Revises: 005
Create Date: 2026-05-03
"""
from sqlalchemy import text
from alembic import op
import uuid


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    settings_row = conn.execute(text(
        "SHOW search_path"
    )).scalar()

    # 动态获取 pg_schema（从 alembic.ini 连接串或默认 sql_agent）
    pg_schema = _detect_business_schema(conn)

    tables = conn.execute(text(
        f"""
        SELECT t.table_name,
               obj_description(
                   (quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass,
                   'pg_class'
               ) AS table_comment
        FROM information_schema.tables t
        WHERE t.table_schema = '{pg_schema}'
          AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name
        """
    )).fetchall()

    for table in tables:
        table_id = str(uuid.uuid4())

        # 跳过已存在的记录（迁移重跑安全）
        existing = conn.execute(text(
            f"SELECT id FROM meta.logical_tables WHERE physical_schema='{pg_schema}' AND physical_name='{table.table_name}'"
        )).fetchone()
        if existing:
            table_id = existing.id
        else:
            conn.execute(text(f"""
                INSERT INTO meta.logical_tables
                    (id, physical_schema, physical_name, table_comment,
                     update_strategy, status, created_at, updated_at)
                VALUES
                    ('{table_id}', '{pg_schema}', '{table.table_name}',
                     {_sql_str(table.table_comment)},
                     'full_replace', 'active', now(), now())
            """))

        columns = conn.execute(text(
            f"""
            SELECT c.column_name, c.data_type, c.ordinal_position,
                   col_description(
                       (quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass,
                       c.ordinal_position
                   ) AS column_comment
            FROM information_schema.columns c
            WHERE c.table_schema = '{pg_schema}'
              AND c.table_name = '{table.table_name}'
            ORDER BY c.ordinal_position
            """
        )).fetchall()

        for col in columns:
            col_existing = conn.execute(text(
                f"SELECT id FROM meta.logical_columns WHERE table_id='{table_id}' AND physical_name='{col.column_name}'"
            )).fetchone()
            if col_existing:
                continue
            col_id = str(uuid.uuid4())
            conn.execute(text(f"""
                INSERT INTO meta.logical_columns
                    (id, table_id, original_name, physical_name, column_comment,
                     ordinal_position, data_type, is_active, created_at, updated_at)
                VALUES
                    ('{col_id}', '{table_id}',
                     '{col.column_name}', '{col.column_name}',
                     {_sql_str(col.column_comment)},
                     {col.ordinal_position}, '{col.data_type}',
                     true, now(), now())
            """))


def downgrade() -> None:
    # 只清空回填数据，不破坏 schema（005 downgrade 负责删 schema）
    conn = op.get_bind()
    pg_schema = _detect_business_schema(conn)
    conn.execute(text(
        f"""
        DELETE FROM meta.logical_columns
        WHERE table_id IN (
            SELECT id FROM meta.logical_tables WHERE physical_schema='{pg_schema}'
        )
        """
    ))
    conn.execute(text(
        f"DELETE FROM meta.logical_tables WHERE physical_schema='{pg_schema}'"
    ))


# ── 辅助 ────────────────────────────────────────────────────────

def _detect_business_schema(conn) -> str:
    """从 search_path 中取第三个（meta 之后的业务 schema），默认 sql_agent。"""
    try:
        sp = conn.execute(text("SHOW search_path")).scalar() or ""
        parts = [p.strip() for p in sp.split(",") if p.strip() not in ("", '"$user"', "public", "meta")]
        return parts[0] if parts else "sql_agent"
    except Exception:
        return "sql_agent"


def _sql_str(value) -> str:
    """将 Python 值转为 SQL 字符串字面量（NULL 或单引号转义）。"""
    if value is None:
        return "NULL"
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"
