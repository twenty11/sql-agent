"""新增查询结果快照表

Revision ID: 013
Revises: 012
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "query_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("fused_question", sa.Text(), nullable=True),
        sa.Column("sql", sa.Text(), nullable=True),
        sa.Column("result_data", sa.JSON(), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("referenced_tables", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index("ix_query_results_created_at", "query_results", ["created_at"], unique=False)
    op.create_index("ix_query_results_message_id", "query_results", ["message_id"], unique=False)
    op.create_index("ix_query_results_session_id", "query_results", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_query_results_session_id", table_name="query_results")
    op.drop_index("ix_query_results_message_id", table_name="query_results")
    op.drop_index("ix_query_results_created_at", table_name="query_results")
    op.drop_table("query_results")
