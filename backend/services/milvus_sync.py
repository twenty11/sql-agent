"""
Milvus 同步服务

职责:
  1. 从 meta.vector_sync_log 消费 pending/pending_retry 行，写入 Milvus。
  2. 全量重建：从 meta.logical_tables 重建 table_schemas collection。
  3. 单表触发：admin 确认上传后调用 on_table_committed。

失败策略：Milvus 失败只记日志，不回滚 PG（PG 是真相源）。
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from db.connection import get_engine
from vectorstore.milvus_store import get_milvus_store, payload_hash


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_table_doc(row) -> str:
    """从 meta.logical_tables 行 + 关联列 生成 doc_text。"""
    lines = [f"英文表名: {row.physical_name}"]
    lines.append(f"表注释: {row.table_comment or '无'}")
    lines.append("字段列表:")
    return "\n".join(lines)



@dataclass
class SyncReport:
    success: int = 0
    failed: int = 0
    skipped: int = 0


# ── 挂起行处理 ────────────────────────────────────────────────────

def flush_pending_syncs(max_attempts: int = 5) -> SyncReport:
    """
    消费 meta.vector_sync_log 中 status='pending' 或 'pending_retry' 的行，
    执行对应的 Milvus upsert/delete 操作。
    """
    engine = get_engine()
    store = get_milvus_store()
    report = SyncReport()

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, target_id, target_type, op, attempts, payload_hash
            FROM meta.vector_sync_log
            WHERE status IN ('pending', 'pending_retry')
            ORDER BY updated_at
            LIMIT 200
        """)).fetchall()

        for row in rows:
            if row.attempts >= max_attempts:
                conn.execute(text("""
                    UPDATE meta.vector_sync_log
                    SET status='failed', updated_at=now()
                    WHERE id=:id
                """), {"id": row.id})
                report.failed += 1
                continue

            try:
                _execute_sync_op(store, conn, row)
                conn.execute(text("""
                    UPDATE meta.vector_sync_log
                    SET status='success', attempts=attempts+1, last_error=NULL, updated_at=now()
                    WHERE id=:id
                """), {"id": row.id})
                report.success += 1
            except Exception as exc:
                conn.execute(text("""
                    UPDATE meta.vector_sync_log
                    SET status='pending_retry',
                        attempts=attempts+1,
                        last_error=:err,
                        updated_at=now()
                    WHERE id=:id
                """), {"id": row.id, "err": str(exc)[:2048]})
                report.failed += 1

        conn.commit()

    return report


def _execute_sync_op(store, conn, log_row) -> None:
    """执行单条 vector_sync_log 对应的 Milvus 操作。"""
    if log_row.target_type != "table":
        return
    if log_row.op == "delete":
        store.delete_table(log_row.target_id)
    else:
        _upsert_table(store, conn, log_row.target_id)


def _upsert_table(store, conn, table_id: str) -> None:
    row = conn.execute(text("""
        SELECT t.id, t.physical_schema, t.physical_name, t.display_name,
               t.table_comment, t.status,
               count(c.id) AS column_count
        FROM meta.logical_tables t
        LEFT JOIN meta.logical_columns c ON c.table_id = t.id AND c.is_active = true
        WHERE t.id = :id
        GROUP BY t.id
    """), {"id": table_id}).fetchone()

    if row is None:
        return

    col_rows = conn.execute(text("""
        SELECT physical_name, data_type, column_comment
        FROM meta.logical_columns
        WHERE table_id = :id AND is_active = true
        ORDER BY ordinal_position
    """), {"id": table_id}).fetchall()

    col_lines = [f"- {c.physical_name} ({c.data_type}): {c.column_comment or '无'}" for c in col_rows]
    display = row.display_name or ""
    doc_text = (
        f"中文表名: {display}\n"
        f"英文表名: {row.physical_name}\n"
        f"表注释: {row.table_comment or '无'}\n"
        f"字段列表:\n" + "\n".join(col_lines)
    )

    store.upsert_table(
        table_id=table_id,
        doc_text=doc_text,
        physical_schema=row.physical_schema,
        physical_name=row.physical_name,
        display_name=display,
        table_comment=row.table_comment or "",
        column_count=int(row.column_count),
        status=row.status,
    )



# ── 重试失败项 ────────────────────────────────────────────────────

def retry_failed_syncs(max_attempts: int = 5) -> SyncReport:
    """将 status='failed' 的行强制重置（含 attempts 归零）后再 flush。"""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE meta.vector_sync_log
            SET status='pending_retry', attempts=0, updated_at=now()
            WHERE status='failed'
        """))
        conn.commit()
    return flush_pending_syncs(max_attempts=max_attempts)


# ── 全量重建 ─────────────────────────────────────────────────────

def rebuild_all_from_pg() -> SyncReport:
    """
    从 meta.logical_tables 全量重建 Milvus table_schemas collection。
    先 drop + recreate，再全量插入。
    """
    from pymilvus import utility
    from config import get_settings
    from vectorstore.milvus_store import (
        TABLE_COLLECTION, _table_schema, _HNSW_INDEX,
    )
    from pymilvus import Collection

    s = get_settings()
    store = get_milvus_store()
    store.connect()

    # Drop & recreate
    if utility.has_collection(TABLE_COLLECTION, using=s.milvus_alias):
        utility.drop_collection(TABLE_COLLECTION, using=s.milvus_alias)
    col = Collection(TABLE_COLLECTION, schema=_table_schema(), using=s.milvus_alias)
    col.create_index("embedding", _HNSW_INDEX)
    col.load()

    # 重置单例内部引用
    store._table_col = Collection(TABLE_COLLECTION, using=s.milvus_alias)
    store._table_col.load()

    engine = get_engine()
    report = SyncReport()

    with engine.connect() as conn:
        tables = conn.execute(text("""
            SELECT id FROM meta.logical_tables WHERE status='active'
        """)).fetchall()

        for t in tables:
            try:
                _upsert_table(store, conn, t.id)
                report.success += 1
            except Exception as exc:
                _log_sync_failure(conn, t.id, "table", "upsert", str(exc))
                report.failed += 1

        conn.commit()

    return report


# ── 单表触发（admin confirm 后调用）──────────────────────────────

def on_table_committed(table_id: str) -> None:
    """
    在 PG 事务提交后调用（FastAPI BackgroundTask）。
    将 meta.vector_sync_log 中 pending 行执行一次 flush。
    失败时不抛出，只确保日志已记录。
    """
    try:
        flush_pending_syncs()
    except Exception:
        pass  # 失败已记录在 vector_sync_log，不影响 PG 已提交的数据


# ── 工具函数 ─────────────────────────────────────────────────────

def enqueue_sync(conn, target_id: str, target_type: str, op: str, doc_text: str = "") -> None:
    """Queue one pending sync per target/op; refresh updated_at if it already exists."""
    conn.execute(text("""
        INSERT INTO meta.vector_sync_log AS v
            (id, target_id, target_type, op, status, attempts, last_error, payload_hash)
        VALUES
            (:id, :target_id, :target_type, :op, 'pending', 0, NULL, :ph)
        ON CONFLICT (target_id, target_type, op)
        WHERE status IN ('pending', 'pending_retry')
        DO UPDATE SET
            status='pending',
            attempts=0,
            last_error=NULL,
            payload_hash=COALESCE(EXCLUDED.payload_hash, v.payload_hash),
            updated_at=now()
    """), {
        "id": str(uuid.uuid4()),
        "target_id": target_id,
        "target_type": target_type,
        "op": op,
        "ph": payload_hash(doc_text) if doc_text else None,
    })


def _log_sync_failure(conn, target_id: str, target_type: str, op: str, error: str) -> None:
    conn.execute(text("""
        INSERT INTO meta.vector_sync_log
            (id, target_id, target_type, op, status, last_error, attempts)
        VALUES
            (:id, :target_id, :target_type, :op, 'failed', :err, 1)
    """), {
        "id": str(uuid.uuid4()),
        "target_id": target_id,
        "target_type": target_type,
        "op": op,
        "err": error[:2048],
    })
