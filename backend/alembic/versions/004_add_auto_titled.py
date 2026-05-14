"""sessions 表增加 auto_titled 列，支持区分自动生成标题与用户手动重命名

Revision ID: 004
Revises: 003
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "auto_titled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "auto_titled")
