"""Deduplicate pending vector sync tasks

Revision ID: 015
Revises: 014
Create Date: 2026-05-12
"""

from alembic import op


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY target_id, target_type, op
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS rn
            FROM meta.vector_sync_log
            WHERE status IN ('pending', 'pending_retry')
        )
        DELETE FROM meta.vector_sync_log v
        USING ranked r
        WHERE v.id = r.id AND r.rn > 1
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_vector_sync_log_pending_target_op
        ON meta.vector_sync_log (target_id, target_type, op)
        WHERE status IN ('pending', 'pending_retry')
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS meta.ux_vector_sync_log_pending_target_op")
