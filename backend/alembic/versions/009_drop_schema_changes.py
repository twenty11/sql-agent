"""删除 meta.schema_changes 表及 change_type 枚举，取消字段变更功能

Revision ID: 009
Revises: 008
Create Date: 2026-05-05
"""

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS meta.schema_changes")
    op.execute("DROP TYPE IF EXISTS meta.change_type")


def downgrade() -> None:
    op.execute("""
        CREATE TYPE meta.change_type AS ENUM
            ('add_col','drop_col','comment_update')
    """)
    op.execute("""
        CREATE TABLE meta.schema_changes (
            id                VARCHAR(36) PRIMARY KEY,
            table_id          VARCHAR(36) NOT NULL
                              REFERENCES meta.logical_tables(id) ON DELETE CASCADE,
            upload_history_id VARCHAR(36)
                              REFERENCES meta.upload_history(id) ON DELETE SET NULL,
            change_type       meta.change_type NOT NULL,
            column_id         VARCHAR(36)
                              REFERENCES meta.logical_columns(id) ON DELETE SET NULL,
            before_state      JSONB,
            after_state       JSONB,
            applied_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            applied_by        VARCHAR(36)
                              REFERENCES public.users(id) ON DELETE SET NULL
        )
    """)
    op.execute("""
        CREATE INDEX ix_schema_changes_table_id
            ON meta.schema_changes (table_id, applied_at DESC)
    """)
