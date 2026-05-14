"""按表分组隔离上传文件去重

Revision ID: 010
Revises: 009
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "upload_history",
        sa.Column("group_id", sa.String(36), nullable=True),
        schema="meta",
    )
    op.create_foreign_key(
        "fk_upload_history_group_id",
        "upload_history",
        "table_groups",
        ["group_id"],
        ["id"],
        source_schema="meta",
        referent_schema="public",
        ondelete="SET NULL",
    )

    op.execute(
        "ALTER TABLE meta.upload_history "
        "DROP CONSTRAINT IF EXISTS uq_upload_history_table_hash"
    )
    op.execute("DROP INDEX IF EXISTS meta.uq_upload_history_new_table")

    op.create_index(
        "uq_upload_history_group_hash_applied",
        "upload_history",
        ["group_id", "file_hash"],
        unique=True,
        schema="meta",
        postgresql_where=sa.text("group_id IS NOT NULL AND status = 'applied'"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS meta.uq_upload_history_group_hash_applied")
    op.create_unique_constraint(
        "uq_upload_history_table_hash",
        "upload_history",
        ["table_id", "file_hash"],
        schema="meta",
    )
    op.create_index(
        "uq_upload_history_new_table",
        "upload_history",
        ["uploaded_by", "file_hash"],
        unique=True,
        schema="meta",
        postgresql_where=sa.text("table_id IS NULL"),
    )
    op.execute(
        "ALTER TABLE meta.upload_history "
        "DROP CONSTRAINT IF EXISTS fk_upload_history_group_id"
    )
    op.drop_column("upload_history", "group_id", schema="meta")
