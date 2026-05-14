"""简化 meta 表结构：新增 display_name，移除 update_strategy/business_key，统一 upload_history status

Revision ID: 008
Revises: 007
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. meta.logical_tables：新增 display_name，删除 update_strategy / business_key
    op.add_column(
        "logical_tables",
        sa.Column("display_name", sa.String(255), nullable=True),
        schema="meta",
    )
    # 回填：将现有 table_comment 作为 display_name 的初始值
    op.execute(
        "UPDATE meta.logical_tables SET display_name = table_comment WHERE display_name IS NULL"
    )
    op.drop_column("logical_tables", "update_strategy", schema="meta")
    op.drop_column("logical_tables", "business_key", schema="meta")

    # 2. 删除 meta.update_strategy 枚举类型（如果存在）
    op.execute("DROP TYPE IF EXISTS meta.update_strategy")

    # 3. meta.upload_history：删除 pending_review/confirmed/rejected 旧行（不再使用审核流程）
    op.execute(
        "DELETE FROM meta.upload_history "
        "WHERE status IN ('pending_review', 'confirmed', 'rejected')"
    )

    # 4. 更新字段注释
    op.execute(
        "COMMENT ON COLUMN meta.logical_tables.display_name IS '中文显示名（用于前端展示）'"
    )


def downgrade() -> None:
    op.drop_column("logical_tables", "display_name", schema="meta")
    op.add_column(
        "logical_tables",
        sa.Column("update_strategy", sa.String(32), nullable=False, server_default="full_replace"),
        schema="meta",
    )
    op.add_column(
        "logical_tables",
        sa.Column("business_key", sa.ARRAY(sa.Text()), nullable=True),
        schema="meta",
    )
