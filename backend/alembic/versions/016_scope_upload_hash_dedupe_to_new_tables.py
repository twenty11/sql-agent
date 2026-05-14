"""Scope upload file-hash dedupe to new-table uploads

Revision ID: 016
Revises: 015
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS meta.uq_upload_history_group_hash_applied")
    op.create_index(
        "uq_upload_history_group_hash_new_table_applied",
        "upload_history",
        ["group_id", "file_hash"],
        unique=True,
        schema="meta",
        postgresql_where=sa.text(
            "group_id IS NOT NULL AND status = 'applied' AND action_type = 'new_table'"
        ),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS meta.uq_upload_history_group_hash_new_table_applied")
    op.create_index(
        "uq_upload_history_group_hash_applied",
        "upload_history",
        ["group_id", "file_hash"],
        unique=True,
        schema="meta",
        postgresql_where=sa.text("group_id IS NOT NULL AND status = 'applied'"),
    )
