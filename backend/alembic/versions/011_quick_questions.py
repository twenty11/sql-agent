"""新增个人快捷问题

Revision ID: 011
Revises: 010
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quick_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("table_group_id", sa.String(36), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["table_group_id"], ["table_groups.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_quick_questions_user_id", "quick_questions", ["user_id"])
    op.create_index("ix_quick_questions_table_group_id", "quick_questions", ["table_group_id"])
    op.create_index(
        "ix_quick_questions_user_order",
        "quick_questions",
        ["user_id", "is_pinned", "sort_order", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_quick_questions_user_order", table_name="quick_questions")
    op.drop_index("ix_quick_questions_table_group_id", table_name="quick_questions")
    op.drop_index("ix_quick_questions_user_id", table_name="quick_questions")
    op.drop_table("quick_questions")
