"""表分组：支持按分组向角色授权可访问表

Revision ID: 003
Revises: 002
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "table_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_table_groups_name"),
    )

    op.create_table(
        "table_group_members",
        sa.Column(
            "group_id",
            sa.String(36),
            sa.ForeignKey("table_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("table_schema", sa.String(64), nullable=False),
        sa.Column("table_name", sa.String(128), nullable=False),
        sa.PrimaryKeyConstraint("group_id", "table_schema", "table_name"),
    )

    op.create_table(
        "role_table_groups",
        sa.Column(
            "role_id",
            sa.String(36),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            sa.String(36),
            sa.ForeignKey("table_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("role_id", "group_id"),
    )


def downgrade() -> None:
    op.drop_table("role_table_groups")
    op.drop_table("table_group_members")
    op.drop_table("table_groups")
