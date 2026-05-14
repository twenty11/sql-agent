"""管理员：业务数据表元数据路由（含上传 / 注释编辑 / 中文表名编辑）"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_session, require_admin
from auth.dependencies import UserContext
from config import get_settings
from db.connection import get_engine
from db.crud.table_groups import get_table_to_groups_map
from db.metadata import get_all_tables_metadata
from services.admin_data_pipeline.validation import (
    qualified_identifier,
    quote_identifier,
    validate_upload_file_count,
)

router = APIRouter(prefix="/admin/tables", tags=["管理员-数据表"])

MAX_NEW_TABLE_UPLOAD_FILES = 20


# ── Pydantic 模型 ────────────────────────────────────────────────

class GroupTag(BaseModel):
    id: str
    name: str


class TableInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[str]
    name: str
    table_schema: str = Field(alias="schema")
    display_name: Optional[str]
    comment: Optional[str]
    column_count: int
    groups: list[GroupTag]


class ColumnInfo(BaseModel):
    id: Optional[str]
    name: str
    original_name: Optional[str] = None
    data_type: str
    nullable: bool
    is_primary_key: bool
    comment: Optional[str]


class TableDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[str]
    name: str
    table_schema: str = Field(alias="schema")
    display_name: Optional[str]
    comment: Optional[str]
    columns: list[ColumnInfo]
    groups: list[GroupTag]


class UpdateCommentBody(BaseModel):
    comment: str


class UpdateDisplayNameBody(BaseModel):
    display_name: str


class UpdateMetadataBody(BaseModel):
    display_name: str
    comment: str


class BatchDeleteBody(BaseModel):
    table_ids: List[str]


class UploadBatchItemOut(BaseModel):
    id: str
    batch_id: str
    upload_history_id: Optional[str]
    table_id: Optional[str]
    file_name: str
    file_size: Optional[int]
    status: str
    action_type: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class UploadBatchOut(BaseModel):
    id: str
    group_id: Optional[str]
    group_name: Optional[str]
    target_table_id: Optional[str]
    mode: str
    status: str
    total_count: int
    success_count: int
    failed_count: int
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class UploadBatchDetailOut(UploadBatchOut):
    items: list[UploadBatchItemOut]


class UploadAcceptedOut(BaseModel):
    batch_id: str
    count: int
    status: str
    message: str


# ── 列表端点 ──────────────────────────────────────────────────────

@router.get("", response_model=list[TableInfo], response_model_by_alias=True)
async def list_business_tables(
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    """列出业务 schema 下所有数据表，附带分组、id、display_name。"""
    settings = get_settings()
    engine = get_engine()
    tables = get_all_tables_metadata(engine)
    group_map = await get_table_to_groups_map(db)

    return [
        TableInfo(
            id=t.id,
            name=t.name,
            schema=t.schema,
            display_name=t.display_name,
            comment=t.comment,
            column_count=len(t.columns),
            groups=[GroupTag(**g) for g in group_map.get((t.schema, t.name), [])],
        )
        for t in tables
        if t.schema == settings.pg_schema
    ]


@router.get("/schema")
async def get_business_schema(admin: UserContext = Depends(require_admin)):
    """返回业务 schema 名（前端用于展示）。"""
    return {"schema": get_settings().pg_schema}


# ── 上传端点（异步批次任务） ────────────────────────────────────

@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=UploadAcceptedOut)
async def upload_file(
    files: Optional[List[UploadFile]] = File(default=None),
    legacy_files: Optional[List[UploadFile]] = File(default=None, alias="file"),
    group_id: str = Form(...),
    mode: Optional[str] = Form(default=None),
    target_table_id: Optional[str] = Form(default=None),
    target_table_ids: Optional[List[str]] = Form(default=None),
    target_table_ids_json: Optional[str] = Form(default=None),
    admin: UserContext = Depends(require_admin),
):
    """
    上传 Excel/CSV，创建异步批次任务后立即返回。
    - group_id 必填（上传时选择分组）
    - mode 可选（new / update；前端会显式传入，防止更新请求误按新建处理）
    - target_table_id 可选（旧版单表更新时传入 meta.logical_tables.id）
    - target_table_ids 可选（批量更新已有表时与 files 一一对应）
    - target_table_ids_json 可选（批量更新目标表 JSON 数组，作为 multipart 重复字段解析兜底）
    - 新建表模式可一次上传多个文件，最多 20 个；更新已有表批量模式最多 20 组
    - files 为新字段；file 为旧字段兼容
    """
    selected_files = [*(files or []), *(legacy_files or [])]
    try:
        parsed_target_table_ids = _parse_target_table_ids(target_table_ids, target_table_ids_json)
        item_target_table_ids = validate_upload_file_count(
            len(selected_files),
            target_table_id,
            MAX_NEW_TABLE_UPLOAD_FILES,
            parsed_target_table_ids,
            mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from services.admin_data_pipeline.upload_batches import (
        create_upload_batch,
        mark_batch_enqueue_failed,
    )
    from tasks.uploads import process_upload_batch_task

    try:
        created = create_upload_batch(
            files=selected_files,
            user_id=admin.user_id,
            group_id=group_id,
            target_table_id=target_table_id,
            target_table_ids=item_target_table_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        process_upload_batch_task.delay(created.batch_id)
    except Exception as exc:
        mark_batch_enqueue_failed(created.batch_id, str(exc))
        raise HTTPException(status_code=503, detail=f"上传任务入队失败: {exc}")

    return UploadAcceptedOut(
        batch_id=created.batch_id,
        count=created.count,
        status="queued",
        message="上传任务已创建",
    )


def _parse_target_table_ids(
    target_table_ids: Optional[List[str]],
    target_table_ids_json: Optional[str],
) -> Optional[list[str]]:
    repeated = [str(item or "").strip() for item in (target_table_ids or [])]
    repeated = [item for item in repeated if item]

    if not target_table_ids_json:
        return repeated or None

    try:
        raw = json.loads(target_table_ids_json)
    except json.JSONDecodeError as exc:
        raise ValueError("target_table_ids_json 格式无效") from exc
    if not isinstance(raw, list):
        raise ValueError("target_table_ids_json 必须是数组")

    parsed = [str(item or "").strip() for item in raw]
    if repeated and repeated != parsed:
        raise ValueError("target_table_ids 与 target_table_ids_json 不一致")
    return parsed


@router.get("/upload-batches", response_model=list[UploadBatchOut])
async def list_upload_batches(
    limit: int = Query(default=50, ge=1, le=100),
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    rows = await db.execute(text("""
        SELECT b.id, b.group_id, g.name AS group_name, b.target_table_id, b.mode,
               b.status, b.total_count, b.success_count, b.failed_count,
               b.error_message, b.created_at, b.started_at, b.finished_at
        FROM meta.upload_batches b
        LEFT JOIN public.table_groups g ON g.id=b.group_id
        WHERE b.uploaded_by=:uid
        ORDER BY b.created_at DESC
        LIMIT :limit
    """), {"uid": admin.user_id, "limit": limit})
    return [UploadBatchOut(**dict(row._mapping)) for row in rows.fetchall()]


@router.get("/upload-batches/{batch_id}", response_model=UploadBatchDetailOut)
async def get_upload_batch(
    batch_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    batch_row = await db.execute(text("""
        SELECT b.id, b.group_id, g.name AS group_name, b.target_table_id, b.mode,
               b.status, b.total_count, b.success_count, b.failed_count,
               b.error_message, b.created_at, b.started_at, b.finished_at
        FROM meta.upload_batches b
        LEFT JOIN public.table_groups g ON g.id=b.group_id
        WHERE b.id=:id AND b.uploaded_by=:uid
    """), {"id": batch_id, "uid": admin.user_id})
    batch = batch_row.fetchone()
    if not batch:
        raise HTTPException(status_code=404, detail="上传批次不存在")

    item_rows = await db.execute(text("""
        SELECT id, batch_id, upload_history_id, table_id, file_name, file_size,
               status, action_type, error_message, created_at, started_at, finished_at
        FROM meta.upload_batch_items
        WHERE batch_id=:id
        ORDER BY created_at ASC
    """), {"id": batch_id})
    data = dict(batch._mapping)
    data["items"] = [UploadBatchItemOut(**dict(row._mapping)) for row in item_rows.fetchall()]
    return UploadBatchDetailOut(**data)


# ── 批量删除 ─────────────────────────────────────────────────────

@router.delete("/batch")
async def batch_delete_tables(
    body: BatchDeleteBody,
    background_tasks: BackgroundTasks,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    """批量删除表：物理表 + meta元数据 + 分组绑定 + Milvus 删除任务。"""
    engine = get_engine()
    deleted: list[str] = []
    errors: list[dict] = []

    for table_id in body.table_ids:
        try:
            row = await db.execute(text(
                "SELECT physical_schema, physical_name FROM meta.logical_tables WHERE id=:id"
            ), {"id": table_id})
            record = row.fetchone()
            if not record:
                errors.append({"id": table_id, "error": "表不存在"})
                continue

            pg_schema = record.physical_schema
            table_name = record.physical_name

            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {qualified_identifier(pg_schema, table_name)}"))

            # 清理关联的 upload_history 及暂存文件，避免 ON DELETE SET NULL 导致旧记录落入唯一索引
            upload_rows = await db.execute(text(
                "SELECT stored_path FROM meta.upload_history WHERE table_id=:id"
            ), {"id": table_id})
            for r in upload_rows.fetchall():
                try:
                    Path(r.stored_path).unlink(missing_ok=True)
                except Exception:
                    pass

            await db.execute(text(
                "DELETE FROM meta.upload_history WHERE table_id=:id"
            ), {"id": table_id})
            await db.execute(text(
                "DELETE FROM meta.logical_columns WHERE table_id=:id"
            ), {"id": table_id})
            await db.execute(text(
                "DELETE FROM public.table_group_members WHERE table_schema=:s AND table_name=:n"
            ), {"s": pg_schema, "n": table_name})
            await db.execute(text(
                "DELETE FROM meta.vector_sync_log WHERE target_id=:id"
            ), {"id": table_id})
            await db.execute(text("""
                INSERT INTO meta.vector_sync_log
                    (id, target_id, target_type, op, status)
                VALUES
                    (:sync_id, :target_id, 'table', 'delete', 'pending')
            """), {"sync_id": str(uuid4()), "target_id": table_id})
            await db.execute(text(
                "DELETE FROM meta.logical_tables WHERE id=:id"
            ), {"id": table_id})
            await db.commit()

            deleted.append(table_id)
        except Exception as exc:
            await db.rollback()
            errors.append({"id": table_id, "error": str(exc)})

    if deleted:
        background_tasks.add_task(_trigger_milvus_sync)

    return {"deleted": deleted, "errors": errors}


# ── 注释编辑端点 ──────────────────────────────────────────────────

@router.put("/{table_id}/metadata")
async def update_table_metadata(
    table_id: str,
    body: UpdateMetadataBody,
    background_tasks: BackgroundTasks,
    admin: UserContext = Depends(require_admin),
):
    """原子更新表中文显示名和表注释，同步 PG COMMENT、meta 和 Milvus 队列。"""
    _update_table_metadata_sync(
        table_id,
        display_name=body.display_name,
        comment=body.comment,
    )
    background_tasks.add_task(_trigger_milvus_sync)
    return {"message": "表元数据已更新"}


@router.put("/{table_id}/display-name")
async def update_table_display_name(
    table_id: str,
    body: UpdateDisplayNameBody,
    background_tasks: BackgroundTasks,
    admin: UserContext = Depends(require_admin),
):
    """编辑表中文显示名，同步更新 meta + Milvus。"""
    _update_table_metadata_sync(table_id, display_name=body.display_name)
    background_tasks.add_task(_trigger_milvus_sync)
    return {"message": "中文表名已更新"}


@router.put("/{table_id}/comment")
async def update_table_comment(
    table_id: str,
    body: UpdateCommentBody,
    background_tasks: BackgroundTasks,
    admin: UserContext = Depends(require_admin),
):
    """编辑表注释，同步更新 PG COMMENT + meta + Milvus。"""
    _update_table_metadata_sync(table_id, comment=body.comment)
    background_tasks.add_task(_trigger_milvus_sync)
    return {"message": "表注释已更新"}


@router.put("/{table_id}/columns/{col_id}/comment")
async def update_column_comment(
    table_id: str,
    col_id: str,
    body: UpdateCommentBody,
    admin: UserContext = Depends(require_admin),
):
    """Update column comment and enqueue vector sync; manual flush required."""
    engine = get_engine()
    with engine.begin() as conn:
        record = conn.execute(text("""
            SELECT c.physical_name, t.physical_schema, t.physical_name AS table_name
            FROM meta.logical_columns c
            JOIN meta.logical_tables t ON t.id=c.table_id
            WHERE c.id=:cid AND c.table_id=:tid
        """), {"cid": col_id, "tid": table_id}).fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="字段不存在")

        conn.execute(text(
            "COMMENT ON COLUMN "
            f"{qualified_identifier(record.physical_schema, record.table_name)}."
            f"{quote_identifier(record.physical_name)} IS :c"
        ), {"c": body.comment})
        conn.execute(text("""
            UPDATE meta.logical_columns
            SET column_comment=:c, updated_at=now()
            WHERE id=:id
        """), {"c": body.comment, "id": col_id})
        from services.milvus_sync import enqueue_sync
        enqueue_sync(conn, table_id, "table", "upsert")
    return {"message": "字段注释已更新"}


# ── 详情端点 ──────────────────────────────────────────────────────

@router.get("/{table_name}", response_model=TableDetail, response_model_by_alias=True)
async def get_table_detail(
    table_name: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    settings = get_settings()
    engine = get_engine()
    tables = get_all_tables_metadata(engine)
    target = next(
        (t for t in tables if t.schema == settings.pg_schema and t.name == table_name),
        None,
    )
    if not target:
        raise HTTPException(status_code=404, detail="表不存在")

    group_map = await get_table_to_groups_map(db)
    return TableDetail(
        id=target.id,
        name=target.name,
        schema=target.schema,
        display_name=target.display_name,
        comment=target.comment,
        columns=[
            ColumnInfo(
                id=c.id,
                name=c.name,
                original_name=c.original_name,
                data_type=c.data_type,
                nullable=c.is_nullable,
                is_primary_key=c.is_primary_key,
                comment=c.comment,
            )
            for c in target.columns
        ],
        groups=[GroupTag(**g) for g in group_map.get((target.schema, target.name), [])],
    )


# ── 辅助 ────────────────────────────────────────────────────────

def _trigger_milvus_sync():
    from services.milvus_sync import flush_pending_syncs
    try:
        flush_pending_syncs()
    except Exception:
        pass


def _update_table_metadata_sync(
    table_id: str,
    display_name: Optional[str] = None,
    comment: Optional[str] = None,
) -> None:
    """Update table metadata and vector sync log in one PostgreSQL transaction."""
    if display_name is None and comment is None:
        return

    engine = get_engine()
    with engine.begin() as conn:
        record = conn.execute(text("""
            SELECT physical_schema, physical_name
            FROM meta.logical_tables
            WHERE id=:id
        """), {"id": table_id}).fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="逻辑表不存在")

        params: dict[str, Any] = {"id": table_id}
        updates = ["updated_at=now()"]
        if display_name is not None:
            updates.append("display_name=:display_name")
            params["display_name"] = display_name
        if comment is not None:
            updates.append("table_comment=:comment")
            params["comment"] = comment
            conn.execute(text(
                f"COMMENT ON TABLE {qualified_identifier(record.physical_schema, record.physical_name)} IS :comment"
            ), {"comment": comment})

        conn.execute(text(f"""
            UPDATE meta.logical_tables
            SET {", ".join(updates)}
            WHERE id=:id
        """), params)

        from services.milvus_sync import enqueue_sync
        enqueue_sync(conn, table_id, "table", "upsert")


async def _get_group_table_names(db: AsyncSession, group_id: str) -> list[str]:
    rows = await db.execute(text("""
        SELECT table_name
        FROM public.table_group_members
        WHERE group_id=:gid
    """), {"gid": group_id})
    return [r.table_name for r in rows.fetchall()]


async def _get_all_physical_table_names(db: AsyncSession) -> set[str]:
    rows = await db.execute(text("""
        SELECT physical_name
        FROM meta.logical_tables
        WHERE status='active'
    """))
    return {r.physical_name for r in rows.fetchall()}


def _make_unique_table_name(table_name: str, existing_names: set[str]) -> str:
    if table_name not in existing_names:
        return table_name

    suffix = 2
    while True:
        suffix_text = f"_{suffix}"
        base = table_name[: 128 - len(suffix_text)]
        candidate = f"{base}_{suffix}"
        if candidate not in existing_names:
            return candidate
        suffix += 1


async def _find_same_schema_table_in_group(
    db: AsyncSession,
    group_id: str,
    file_columns: list[str],
) -> Optional[dict[str, str]]:
    file_col_set = set(file_columns)
    if not file_col_set:
        return None

    table_rows = await db.execute(text("""
        SELECT t.id, t.physical_schema, t.physical_name, t.display_name
        FROM public.table_group_members gm
        JOIN meta.logical_tables t
          ON t.physical_schema = gm.table_schema
         AND t.physical_name = gm.table_name
        WHERE gm.group_id=:gid
          AND t.status='active'
    """), {"gid": group_id})

    for row in table_rows.fetchall():
        col_rows = await db.execute(text("""
            SELECT original_name
            FROM meta.logical_columns
            WHERE table_id=:tid AND is_active=true
            ORDER BY ordinal_position
        """), {"tid": row.id})
        existing_col_set = {c.original_name for c in col_rows.fetchall()}
        if existing_col_set == file_col_set:
            return {
                "id": row.id,
                "physical_schema": row.physical_schema,
                "physical_name": row.physical_name,
                "display_name": row.display_name,
            }
    return None
