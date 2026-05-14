"""元数据目录：meta.* schema — 稳定命名真相源

Revision ID: 005
Revises: 004
Create Date: 2026-05-03
"""

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS meta")

    # ── 枚举类型 ────────────────────────────────────────────────
    op.execute("""
        CREATE TYPE meta.update_strategy AS ENUM
            ('full_replace','upsert','append','versioned_append')
    """)
    op.execute("""
        CREATE TYPE meta.table_status AS ENUM ('active','deprecated')
    """)
    op.execute("""
        CREATE TYPE meta.upload_status AS ENUM
            ('pending_review','confirmed','rejected','applied','failed')
    """)
    op.execute("""
        CREATE TYPE meta.action_type AS ENUM
            ('new_table','schema_change','data_only')
    """)
    op.execute("""
        CREATE TYPE meta.change_type AS ENUM
            ('add_col','drop_col','comment_update')
    """)
    op.execute("""
        CREATE TYPE meta.sync_target AS ENUM ('table','column')
    """)
    op.execute("""
        CREATE TYPE meta.sync_op AS ENUM ('upsert','delete')
    """)
    op.execute("""
        CREATE TYPE meta.sync_status AS ENUM
            ('pending','success','pending_retry','failed')
    """)

    # ── meta.logical_tables ──────────────────────────────────────
    op.execute("""
        CREATE TABLE meta.logical_tables (
            id              VARCHAR(36) PRIMARY KEY,
            physical_schema VARCHAR(64)  NOT NULL DEFAULT 'sql_agent',
            physical_name   VARCHAR(128) NOT NULL,
            table_comment   TEXT,
            update_strategy meta.update_strategy NOT NULL DEFAULT 'full_replace',
            business_key    TEXT[],
            status          meta.table_status NOT NULL DEFAULT 'active',
            created_by      VARCHAR(36) REFERENCES public.users(id) ON DELETE SET NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_logical_tables_name UNIQUE (physical_schema, physical_name)
        )
    """)

    # ── meta.logical_columns ─────────────────────────────────────
    op.execute("""
        CREATE TABLE meta.logical_columns (
            id               VARCHAR(36) PRIMARY KEY,
            table_id         VARCHAR(36) NOT NULL
                             REFERENCES meta.logical_tables(id) ON DELETE CASCADE,
            original_name    TEXT        NOT NULL,
            physical_name    VARCHAR(128) NOT NULL,
            column_comment   TEXT,
            ordinal_position INTEGER     NOT NULL,
            data_type        VARCHAR(64) NOT NULL DEFAULT 'TEXT',
            is_active        BOOLEAN     NOT NULL DEFAULT true,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_logical_columns_orig UNIQUE (table_id, original_name),
            CONSTRAINT uq_logical_columns_phys UNIQUE (table_id, physical_name)
        )
    """)
    op.execute("""
        CREATE INDEX ix_logical_columns_table_pos
            ON meta.logical_columns (table_id, ordinal_position)
    """)

    # ── meta.upload_history ──────────────────────────────────────
    op.execute("""
        CREATE TABLE meta.upload_history (
            id           VARCHAR(36) PRIMARY KEY,
            table_id     VARCHAR(36)
                         REFERENCES meta.logical_tables(id) ON DELETE SET NULL,
            file_hash    VARCHAR(64)  NOT NULL,
            file_name    VARCHAR(512) NOT NULL,
            file_size    BIGINT,
            stored_path  VARCHAR(512) NOT NULL,
            uploaded_by  VARCHAR(36)  NOT NULL
                         REFERENCES public.users(id) ON DELETE RESTRICT,
            uploaded_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            status       meta.upload_status NOT NULL DEFAULT 'pending_review',
            action_type  meta.action_type   NOT NULL,
            llm_proposal JSONB        NOT NULL DEFAULT '{}',
            diff_summary JSONB,
            error_message TEXT,
            applied_at   TIMESTAMPTZ,
            CONSTRAINT uq_upload_history_table_hash UNIQUE (table_id, file_hash)
        )
    """)
    # 新表上传时 table_id 为 NULL，用 partial unique 防同一用户重复提交相同文件
    op.execute("""
        CREATE UNIQUE INDEX uq_upload_history_new_table
            ON meta.upload_history (uploaded_by, file_hash)
            WHERE table_id IS NULL
    """)
    op.execute("""
        CREATE INDEX ix_upload_history_status
            ON meta.upload_history (status, uploaded_at DESC)
    """)

    # ── meta.schema_changes ──────────────────────────────────────
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

    # ── meta.vector_sync_log ─────────────────────────────────────
    op.execute("""
        CREATE TABLE meta.vector_sync_log (
            id           VARCHAR(36) PRIMARY KEY,
            target_id    VARCHAR(36) NOT NULL,
            target_type  meta.sync_target NOT NULL,
            op           meta.sync_op     NOT NULL,
            status       meta.sync_status NOT NULL DEFAULT 'pending',
            attempts     INTEGER     NOT NULL DEFAULT 0,
            last_error   TEXT,
            payload_hash VARCHAR(64),
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX ix_vector_sync_log_retry
            ON meta.vector_sync_log (status, updated_at)
            WHERE status IN ('pending', 'pending_retry')
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS meta.vector_sync_log")
    op.execute("DROP TABLE IF EXISTS meta.schema_changes")
    op.execute("DROP TABLE IF EXISTS meta.upload_history")
    op.execute("DROP TABLE IF EXISTS meta.logical_columns")
    op.execute("DROP TABLE IF EXISTS meta.logical_tables")

    op.execute("DROP TYPE IF EXISTS meta.sync_status")
    op.execute("DROP TYPE IF EXISTS meta.sync_op")
    op.execute("DROP TYPE IF EXISTS meta.sync_target")
    op.execute("DROP TYPE IF EXISTS meta.change_type")
    op.execute("DROP TYPE IF EXISTS meta.action_type")
    op.execute("DROP TYPE IF EXISTS meta.upload_status")
    op.execute("DROP TYPE IF EXISTS meta.table_status")
    op.execute("DROP TYPE IF EXISTS meta.update_strategy")

    op.execute("DROP SCHEMA IF EXISTS meta")
