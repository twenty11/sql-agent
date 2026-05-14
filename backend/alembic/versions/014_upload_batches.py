"""上传批次任务表

Revision ID: 014
Revises: 013
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "group_id",
            sa.String(36),
            sa.ForeignKey("public.table_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_table_id",
            sa.String(36),
            sa.ForeignKey("meta.logical_tables.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploaded_by",
            sa.String(36),
            sa.ForeignKey("public.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        schema="meta",
    )
    op.execute("""
        CREATE INDEX ix_upload_batches_user_created
        ON meta.upload_batches (uploaded_by, created_at DESC)
    """)
    op.create_index("ix_upload_batches_status", "upload_batches", ["status"], schema="meta")

    op.create_table(
        "upload_batch_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(36),
            sa.ForeignKey("meta.upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "upload_history_id",
            sa.String(36),
            sa.ForeignKey("meta.upload_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "table_id",
            sa.String(36),
            sa.ForeignKey("meta.logical_tables.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("stored_path", sa.String(512), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("action_type", sa.String(32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        schema="meta",
    )
    op.create_index("ix_upload_batch_items_batch", "upload_batch_items", ["batch_id"], schema="meta")
    op.create_index(
        "ix_upload_batch_items_batch_status",
        "upload_batch_items",
        ["batch_id", "status"],
        schema="meta",
    )


def downgrade() -> None:
    op.drop_index("ix_upload_batch_items_batch_status", table_name="upload_batch_items", schema="meta")
    op.drop_index("ix_upload_batch_items_batch", table_name="upload_batch_items", schema="meta")
    op.drop_table("upload_batch_items", schema="meta")

    op.drop_index("ix_upload_batches_status", table_name="upload_batches", schema="meta")
    op.drop_index("ix_upload_batches_user_created", table_name="upload_batches", schema="meta")
    op.drop_table("upload_batches", schema="meta")
