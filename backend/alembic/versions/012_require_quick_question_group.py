"""快捷问题强制绑定表分组

Revision ID: 012
Revises: 011
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM quick_questions WHERE table_group_id IS NULL")
    op.execute(
        "ALTER TABLE quick_questions "
        "DROP CONSTRAINT IF EXISTS quick_questions_table_group_id_fkey"
    )
    op.alter_column(
        "quick_questions",
        "table_group_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )
    op.create_foreign_key(
        "quick_questions_table_group_id_fkey",
        "quick_questions",
        "table_groups",
        ["table_group_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE quick_questions "
        "DROP CONSTRAINT IF EXISTS quick_questions_table_group_id_fkey"
    )
    op.alter_column(
        "quick_questions",
        "table_group_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )
    op.create_foreign_key(
        "quick_questions_table_group_id_fkey",
        "quick_questions",
        "table_groups",
        ["table_group_id"],
        ["id"],
        ondelete="SET NULL",
    )
