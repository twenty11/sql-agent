"""Persistent async upload batch helpers."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Optional, Sequence

from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.engine import Connection

from db.connection import get_engine
from services.admin_data_pipeline.merger import apply_upload
from services.admin_data_pipeline.proposer import propose_for_new_columns, propose_for_new_table
from services.admin_data_pipeline.staging import StagedFile, resolve_staged_path, write_staged_file
from services.admin_data_pipeline.validation import normalize_new_table_proposal, normalize_schema_change_columns
from utils.data_loader import get_file_info, read_data_file


BATCH_ACTIVE_STATUSES = {"queued", "processing"}
BATCH_TERMINAL_STATUSES = {"success", "partial_failed", "failed"}
ITEM_ACTIVE_STATUSES = {"queued", "processing"}
ITEM_TERMINAL_STATUSES = {"applied", "failed"}


@dataclass
class UploadBatchCreated:
    batch_id: str
    count: int


def create_upload_batch(
    *,
    files: Sequence[UploadFile],
    user_id: str,
    group_id: str,
    target_table_id: Optional[str],
    target_table_ids: Sequence[str | None] | None = None,
) -> UploadBatchCreated:
    """Stage uploaded files and create a persistent queued batch."""
    batch_id = str(uuid.uuid4())
    item_target_table_ids = _resolve_item_target_table_ids(files, target_table_id, target_table_ids)
    mode = "update" if any(item_target_table_ids) else "new"
    staged_files: list[StagedFile] = []

    engine = get_engine()
    target_ids = [table_id for table_id in item_target_table_ids if table_id]
    if target_ids:
        with engine.begin() as conn:
            _validate_target_tables_sync(conn, group_id, target_ids)

    for file in files:
        staged_files.append(write_staged_file(file, user_id, extract_info=False))

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO meta.upload_batches
                (id, group_id, target_table_id, uploaded_by, mode, status, total_count)
            VALUES
                (:id, :gid, :target_table_id, :uploaded_by, :mode, 'queued', :total_count)
        """), {
            "id": batch_id,
            "gid": group_id,
            "target_table_id": target_table_id,
            "uploaded_by": user_id,
            "mode": mode,
            "total_count": len(staged_files),
        })

        conn.execute(text("""
            INSERT INTO meta.upload_batch_items
                (id, batch_id, table_id, file_hash, file_name, file_size, stored_path, status)
            VALUES
                (:id, :batch_id, :table_id, :file_hash, :file_name, :file_size, :stored_path, 'queued')
        """), [
            {
                "id": str(uuid.uuid4()),
                "batch_id": batch_id,
                "table_id": item_target_table_ids[idx],
                "file_hash": staged.file_hash,
                "file_name": staged.file_name,
                "file_size": staged.file_size,
                "stored_path": staged.stored_path,
            }
            for idx, staged in enumerate(staged_files)
        ])

    return UploadBatchCreated(batch_id=batch_id, count=len(staged_files))


def _resolve_item_target_table_ids(
    files: Sequence[UploadFile],
    target_table_id: Optional[str],
    target_table_ids: Sequence[str | None] | None,
) -> list[str | None]:
    if target_table_ids is None:
        return [target_table_id] * len(files) if target_table_id else [None] * len(files)

    item_target_table_ids = [str(item or "").strip() or None for item in target_table_ids]
    if len(item_target_table_ids) != len(files):
        raise ValueError("更新已有表需要为每个文件选择一个目标表")
    return item_target_table_ids


def _validate_target_tables_sync(conn: Connection, group_id: str, target_table_ids: Sequence[str]) -> None:
    for table_id in target_table_ids:
        row = conn.execute(text("""
            SELECT 1
            FROM meta.logical_tables t
            JOIN public.table_group_members gm
              ON gm.table_schema = t.physical_schema
             AND gm.table_name = t.physical_name
            WHERE t.id=:tid
              AND t.status='active'
              AND gm.group_id=:gid
            LIMIT 1
        """), {"tid": table_id, "gid": group_id}).fetchone()
        if not row:
            raise ValueError(f"目标表不存在或不属于所选分组: {table_id}")


def mark_batch_enqueue_failed(batch_id: str, error_message: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE meta.upload_batches
            SET status='failed',
                failed_count=total_count,
                error_message=:error,
                started_at=COALESCE(started_at, now()),
                finished_at=now()
            WHERE id=:id
        """), {"id": batch_id, "error": error_message[:2048]})
        conn.execute(text("""
            UPDATE meta.upload_batch_items
            SET status='failed',
                error_message=:error,
                started_at=COALESCE(started_at, now()),
                finished_at=now()
            WHERE batch_id=:id AND status IN ('queued', 'processing')
        """), {"id": batch_id, "error": error_message[:2048]})


def process_upload_batch(batch_id: str) -> dict:
    """Process all queued files in a batch. Each item succeeds or fails independently."""
    engine = get_engine()
    with engine.begin() as conn:
        batch = _fetch_batch(conn, batch_id)
        if batch is None:
            raise ValueError(f"upload batch {batch_id} 不存在")
        if batch["status"] in BATCH_TERMINAL_STATUSES:
            return {"status": batch["status"], "success": batch["success_count"], "failed": batch["failed_count"]}

        conn.execute(text("""
            UPDATE meta.upload_batches
            SET status='processing',
                started_at=COALESCE(started_at, now())
            WHERE id=:id
        """), {"id": batch_id})

    any_success = False
    for item in _fetch_batch_items(batch_id):
        try:
            _process_batch_item(batch_id, item["id"])
            any_success = True
        except Exception as exc:
            _mark_item_failed(item["id"], str(exc))
        finally:
            _refresh_batch_counts(batch_id)

    final_status = _finish_batch(batch_id)
    if any_success:
        _enqueue_vector_sync()
    return final_status


def _process_batch_item(batch_id: str, item_id: str) -> None:
    engine = get_engine()

    with engine.begin() as conn:
        batch = _fetch_batch(conn, batch_id)
        item = _fetch_item(conn, item_id)
        if batch is None or item is None:
            raise ValueError("上传任务不存在")
        if item["status"] in ITEM_TERMINAL_STATUSES:
            return

        conn.execute(text("""
            UPDATE meta.upload_batch_items
            SET status='processing',
                started_at=COALESCE(started_at, now()),
                error_message=NULL
            WHERE id=:id
        """), {"id": item_id})

    staged_path = resolve_staged_path(item["stored_path"])
    df = read_data_file(staged_path)
    file_info = get_file_info(staged_path, df=df)

    with engine.begin() as conn:
        batch = _fetch_batch(conn, batch_id)
        item = _fetch_item(conn, item_id)
        if batch is None or item is None:
            raise ValueError("上传任务不存在")

        target_table_id = _require_update_target_table_id(batch, item)
        action_type, table_id = _decide_action_sync(conn, file_info, target_table_id)
        if _should_reject_duplicate_file(action_type):
            duplicate = conn.execute(text("""
                SELECT id
                FROM meta.upload_history
                WHERE group_id=:gid
                  AND file_hash=:file_hash
                  AND action_type='new_table'
                  AND status='applied'
                ORDER BY uploaded_at DESC
                LIMIT 1
            """), {"gid": batch["group_id"], "file_hash": item["file_hash"]}).fetchone()
            if duplicate:
                raise ValueError(f"相同文件已应用，upload_id={duplicate.id}")

        proposal: dict = {}
        diff: dict = {}
        if action_type == "new_table":
            existing_names = _get_all_physical_table_names_sync(conn)
            meta = propose_for_new_table(
                file_info,
                forbidden_table_names=_get_group_table_names_sync(conn, batch["group_id"]),
            )
            proposal = normalize_new_table_proposal(
                meta.model_dump(),
                file_info.get("columns", []),
                existing_names,
            )
        elif action_type == "schema_change":
            extra, missing = _column_diff_sync(conn, file_info, table_id)
            meta = propose_for_new_columns(file_info, extra)
            new_columns = normalize_schema_change_columns(
                meta.model_dump(),
                extra,
                _get_table_physical_column_names_sync(conn, table_id),
            )
            proposal = {"columns": new_columns}
            diff = {
                "message": "上传文件包含新增字段，已自动补列并增量追加数据",
                "added_columns": [
                    {
                        "original_name": c["original_name"],
                        "physical_name": c["column_name"],
                        "column_comment": c["column_comment"],
                    }
                    for c in new_columns
                ],
                "missing_columns": missing,
            }
        else:
            extra, missing = _column_diff_sync(conn, file_info, table_id)
            diff = {
                "message": "无新增字段，已增量追加数据",
                "added_columns": extra,
                "missing_columns": missing,
            }

        upload_id = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO meta.upload_history
                (id, table_id, group_id, file_hash, file_name, file_size, stored_path,
                 uploaded_by, status, action_type, llm_proposal, diff_summary)
            VALUES
                (:id, :table_id, :group_id, :file_hash, :file_name, :file_size, :stored_path,
                 :uploaded_by, 'applied', :action_type,
                 CAST(:proposal AS jsonb), CAST(:diff AS jsonb))
        """), {
            "id": upload_id,
            "table_id": table_id,
            "group_id": batch["group_id"],
            "file_hash": item["file_hash"],
            "file_name": item["file_name"],
            "file_size": item["file_size"],
            "stored_path": item["stored_path"],
            "uploaded_by": batch["uploaded_by"],
            "action_type": action_type,
            "proposal": json.dumps(proposal, ensure_ascii=False),
            "diff": json.dumps(diff, ensure_ascii=False),
        })
        conn.execute(text("""
            UPDATE meta.upload_batch_items
            SET action_type=:action_type, upload_history_id=:upload_id
            WHERE id=:id
        """), {"id": item_id, "action_type": action_type, "upload_id": upload_id})

    try:
        apply_upload(upload_id, applied_by=batch["uploaded_by"], group_id=batch["group_id"])
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE meta.upload_history
                SET status='failed', error_message=:error
                WHERE id=:id
            """), {"id": upload_id, "error": str(exc)[:2048]})
        raise

    with engine.begin() as conn:
        final = conn.execute(text("""
            SELECT table_id FROM meta.upload_history WHERE id=:id
        """), {"id": upload_id}).fetchone()
        conn.execute(text("""
            UPDATE meta.upload_batch_items
            SET status='applied',
                table_id=:table_id,
                error_message=NULL,
                finished_at=now()
            WHERE id=:id
        """), {"id": item_id, "table_id": final.table_id if final else None})


def _decide_action_sync(conn: Connection, file_info: dict, target_table_id: Optional[str]) -> tuple[str, Optional[str]]:
    if not target_table_id:
        return "new_table", None

    rows = conn.execute(text("""
        SELECT original_name
        FROM meta.logical_columns
        WHERE table_id = :tid AND is_active = true
    """), {"tid": target_table_id}).fetchall()
    existing = {r.original_name for r in rows}
    file_columns = {str(c) for c in file_info.get("columns", [])}

    if file_columns - existing:
        return "schema_change", target_table_id

    return "data_only", target_table_id


def _get_item_target_table_id(batch: dict, item: dict) -> Optional[str]:
    return item.get("table_id") or batch.get("target_table_id")


def _require_update_target_table_id(batch: dict, item: dict) -> Optional[str]:
    target_table_id = _get_item_target_table_id(batch, item)
    if batch.get("mode") == "update" and not target_table_id:
        raise ValueError("更新已有表缺少目标表")
    return target_table_id


def _column_diff_sync(conn: Connection, file_info: dict, target_table_id: Optional[str]) -> tuple[list[str], list[str]]:
    if not target_table_id:
        return [], []
    rows = conn.execute(text("""
        SELECT original_name
        FROM meta.logical_columns
        WHERE table_id = :tid AND is_active = true
    """), {"tid": target_table_id}).fetchall()
    existing = {r.original_name for r in rows}
    file_columns = [str(c) for c in file_info.get("columns", [])]
    file_column_set = set(file_columns)
    return [c for c in file_columns if c not in existing], sorted(existing - file_column_set)


def _should_reject_duplicate_file(action_type: str) -> bool:
    return action_type == "new_table"


def _fetch_batch_items(batch_id: str) -> list[dict]:
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT id, batch_id, file_name, status
            FROM meta.upload_batch_items
            WHERE batch_id=:batch_id
              AND status IN ('queued', 'processing')
            ORDER BY created_at ASC
        """), {"batch_id": batch_id}).fetchall()
        return [dict(row._mapping) for row in rows]


def _fetch_batch(conn: Connection, batch_id: str) -> Optional[dict]:
    row = conn.execute(text("""
        SELECT id, group_id, target_table_id, uploaded_by, mode, status,
               total_count, success_count, failed_count
        FROM meta.upload_batches
        WHERE id=:id
    """), {"id": batch_id}).fetchone()
    return dict(row._mapping) if row else None


def _fetch_item(conn: Connection, item_id: str) -> Optional[dict]:
    row = conn.execute(text("""
        SELECT id, batch_id, upload_history_id, table_id, file_hash, file_name,
               file_size, stored_path, status, action_type
        FROM meta.upload_batch_items
        WHERE id=:id
    """), {"id": item_id}).fetchone()
    return dict(row._mapping) if row else None


def _mark_item_failed(item_id: str, error_message: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE meta.upload_batch_items
            SET status='failed',
                error_message=:error,
                finished_at=now()
            WHERE id=:id
        """), {"id": item_id, "error": error_message[:2048]})


def _refresh_batch_counts(batch_id: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE meta.upload_batches
            SET success_count=(
                    SELECT count(*) FROM meta.upload_batch_items
                    WHERE batch_id=:id AND status='applied'
                ),
                failed_count=(
                    SELECT count(*) FROM meta.upload_batch_items
                    WHERE batch_id=:id AND status='failed'
                )
            WHERE id=:id
        """), {"id": batch_id})


def _finish_batch(batch_id: str) -> dict:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT total_count, success_count, failed_count
            FROM meta.upload_batches
            WHERE id=:id
        """), {"id": batch_id}).fetchone()
        if not row:
            raise ValueError(f"upload batch {batch_id} 不存在")

        if row.success_count == row.total_count:
            status = "success"
        elif row.success_count == 0:
            status = "failed"
        else:
            status = "partial_failed"

        conn.execute(text("""
            UPDATE meta.upload_batches
            SET status=:status, finished_at=now()
            WHERE id=:id
        """), {"id": batch_id, "status": status})
        return {"status": status, "success": row.success_count, "failed": row.failed_count}


def _get_group_table_names_sync(conn: Connection, group_id: str) -> list[str]:
    rows = conn.execute(text("""
        SELECT table_name
        FROM public.table_group_members
        WHERE group_id=:gid
    """), {"gid": group_id}).fetchall()
    return [r.table_name for r in rows]


def _get_all_physical_table_names_sync(conn: Connection) -> set[str]:
    rows = conn.execute(text("""
        SELECT physical_name
        FROM meta.logical_tables
        WHERE status='active'
    """)).fetchall()
    return {r.physical_name for r in rows}


def _get_table_physical_column_names_sync(conn: Connection, table_id: Optional[str]) -> set[str]:
    if not table_id:
        return set()
    rows = conn.execute(text("""
        SELECT physical_name
        FROM meta.logical_columns
        WHERE table_id=:tid AND is_active=true
    """), {"tid": table_id}).fetchall()
    names = {r.physical_name for r in rows}

    table_row = conn.execute(text("""
        SELECT physical_schema, physical_name
        FROM meta.logical_tables
        WHERE id=:tid
    """), {"tid": table_id}).fetchone()
    if table_row:
        physical_rows = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema=:schema AND table_name=:table
        """), {
            "schema": table_row.physical_schema,
            "table": table_row.physical_name,
        }).fetchall()
        names.update(r.column_name for r in physical_rows)

    return names


def _enqueue_vector_sync() -> None:
    try:
        from tasks.vectorstore import sync_vectorstore_task

        sync_vectorstore_task.delay()
    except Exception:
        pass
