"""
Merger：apply_upload — 事务核心。

事务边界：
  1. DDL（CREATE / ALTER TABLE ADD COLUMN）
  2. 写 meta.logical_tables / logical_columns
  3. 新表全量插入；已有表增量追加并跳过重复行
  4. meta.upload_history.status='applied'
  5. 插 meta.vector_sync_log（status='pending'）
  全部在同一 PG 事务，失败完整回滚。
  Milvus 同步在事务提交后由 BackgroundTask 触发，失败不回滚 PG。
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from config import get_settings
from services.milvus_sync import enqueue_sync
from services.admin_data_pipeline.validation import (
    make_unique_column_name,
    normalize_data_type,
    normalize_new_table_proposal,
    qualified_identifier,
    quote_identifier,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── 入口 ─────────────────────────────────────────────────────────

def apply_upload(
    upload_id: str,
    applied_by: str,
    group_id: Optional[str] = None,
    edited_proposal: Optional[dict] = None,
) -> None:
    """
    在单一 PG 事务内完成 DDL + 元数据更新 + 数据落库。

    Args:
        upload_id:       meta.upload_history.id
        applied_by:      执行上传的 admin user_id
        group_id:        上传时选择的分组 UUID（必填，用于绑定表到分组）
        edited_proposal: 可选，覆盖 llm_proposal
    """
    from db.connection import get_engine
    engine = get_engine()

    with engine.begin() as conn:
        upload = _fetch_upload(conn, upload_id)
        if upload is None:
            raise ValueError(f"upload_history {upload_id} 不存在")

        proposal = edited_proposal or upload["llm_proposal"]
        action_type = upload["action_type"]
        table_id = upload["table_id"]
        staged_path = Path(upload["stored_path"])

        df = _load_dataframe(staged_path)

        if action_type == "new_table":
            table_id = _apply_new_table(conn, upload, proposal, df, applied_by)
        else:  # data_only / schema_change
            _apply_existing_table_incremental(conn, upload, proposal, df)

        # 更新 upload_history
        conn.execute(text("""
            UPDATE meta.upload_history
            SET status='applied', applied_at=now(), table_id=:tid
            WHERE id=:id
        """), {"id": upload_id, "tid": table_id})

        # 绑定到分组
        if group_id and table_id:
            tbl = conn.execute(text(
                "SELECT physical_schema, physical_name FROM meta.logical_tables WHERE id=:id"
            ), {"id": table_id}).fetchone()
            if tbl:
                conn.execute(text("""
                    INSERT INTO public.table_group_members (group_id, table_schema, table_name)
                    VALUES (:gid, :schema, :name)
                    ON CONFLICT DO NOTHING
                """), {"gid": group_id, "schema": tbl.physical_schema, "name": tbl.physical_name})

        # 入队 vector_sync（表级）
        enqueue_sync(conn, table_id, "table", "upsert")


# ── 新表 ──────────────────────────────────────────────────────────

def _apply_new_table(conn: Connection, upload: dict, proposal: dict, df: pd.DataFrame, applied_by: str) -> str:
    """创建新物理表 + 插入 meta.logical_tables/logical_columns + 加载数据。"""
    settings = get_settings()
    pg_schema = settings.pg_schema
    proposal = normalize_new_table_proposal(proposal, [str(c) for c in df.columns])
    table_name: str = proposal["table_name"]
    display_name: str = proposal.get("display_name", "")
    table_comment: str = proposal.get("table_comment", "")
    columns: list = proposal.get("columns", [])

    # 创建物理表
    col_ddl = ",\n  ".join(
        f'{quote_identifier(c["column_name"])} {normalize_data_type(c.get("data_type"))}'
        for c in columns
    )
    table_ref = qualified_identifier(pg_schema, table_name)
    conn.execute(text(f"CREATE TABLE IF NOT EXISTS {table_ref} (\n  {col_ddl}\n)"))
    conn.execute(text(f"COMMENT ON TABLE {table_ref} IS :c"), {"c": table_comment})
    for c in columns:
        if c.get("column_comment"):
            conn.execute(text(
                f'COMMENT ON COLUMN {table_ref}.{quote_identifier(c["column_name"])} IS :c'
            ), {"c": c["column_comment"]})

    # 写 meta.logical_tables
    table_id = str(uuid.uuid4())
    conn.execute(text("""
        INSERT INTO meta.logical_tables
            (id, physical_schema, physical_name, display_name, table_comment,
             status, created_by, created_at, updated_at)
        VALUES
            (:id, :schema, :name, :display_name, :comment, 'active', :by, now(), now())
    """), {
        "id": table_id, "schema": pg_schema, "name": table_name,
        "display_name": display_name, "comment": table_comment, "by": applied_by,
    })

    # 写 meta.logical_columns
    for pos, c in enumerate(columns, 1):
        col_id = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO meta.logical_columns
                (id, table_id, original_name, physical_name, column_comment,
                 ordinal_position, data_type, is_active, created_at, updated_at)
            VALUES
                (:id, :tid, :orig, :phys, :comment, :pos, :dt, true, now(), now())
        """), {
            "id": col_id, "tid": table_id,
            "orig": c.get("original_name", c["column_name"]),
            "phys": c["column_name"],
            "comment": c.get("column_comment", ""),
            "pos": pos, "dt": normalize_data_type(c.get("data_type")),
        })

    # 新表直接 INSERT（无需影子表 swap）
    normalized_cols = [{**c, "physical_name": c["column_name"]} for c in columns]
    _bulk_insert(conn, pg_schema, table_name, normalized_cols, df)
    return table_id


# ── 已有表增量追加 ───────────────────────────────────────────────

def _apply_existing_table_incremental(conn: Connection, upload: dict, proposal: dict, df: pd.DataFrame) -> None:
    table_id = upload["table_id"]
    if not table_id:
        raise ValueError("更新已有表缺少 table_id")

    table_row = conn.execute(text("""
        SELECT physical_schema, physical_name
        FROM meta.logical_tables
        WHERE id=:id AND status='active'
    """), {"id": table_id}).fetchone()
    if not table_row:
        raise ValueError(f"目标表不存在或不可用: {table_id}")

    df = _normalize_dataframe_columns(df)
    upload_columns = [str(c) for c in df.columns]
    if not upload_columns:
        raise ValueError("上传文件没有可用字段")

    pg_schema = table_row.physical_schema
    table_name = table_row.physical_name
    existing_cols = _get_active_columns(conn, table_id)
    new_cols = _plan_new_columns(
        upload_columns,
        existing_cols,
        proposed_columns=proposal.get("columns", []) if isinstance(proposal, dict) else [],
        used_physical_names=_get_physical_column_names(conn, pg_schema, table_name),
    )
    if new_cols:
        _add_columns_to_existing_table(conn, pg_schema, table_name, table_id, new_cols)

    all_cols = [*existing_cols, *new_cols]
    dedupe_cols = _choose_dedupe_columns(upload_columns, existing_cols, all_cols)
    filtered_df = _filter_new_rows(conn, pg_schema, table_name, all_cols, df, dedupe_cols)
    _bulk_insert(conn, pg_schema, table_name, all_cols, filtered_df)


def _normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result.columns = [str(c) for c in result.columns]
    return result


def _plan_new_columns(
    upload_columns: list[str],
    existing_cols: list[dict],
    *,
    proposed_columns: list[dict] | None = None,
    used_physical_names: set[str] | None = None,
) -> list[dict]:
    existing_originals = {c["original_name"] for c in existing_cols}
    proposed_by_original = {
        str(c.get("original_name")): c
        for c in (proposed_columns or [])
        if isinstance(c, dict) and c.get("original_name") is not None
    }
    used = {c["physical_name"] for c in existing_cols}
    used.update(used_physical_names or set())
    ordinal = max((int(c.get("ordinal_position") or 0) for c in existing_cols), default=0)
    planned: list[dict] = []

    for original_name in upload_columns:
        if original_name in existing_originals:
            continue
        ordinal += 1
        proposed = proposed_by_original.get(original_name, {})
        physical_name = make_unique_column_name(
            proposed.get("column_name") or proposed.get("physical_name") or original_name,
            used,
            f"col_{ordinal}",
        )
        planned.append({
            "id": str(uuid.uuid4()),
            "original_name": original_name,
            "physical_name": physical_name,
            "column_comment": str(proposed.get("column_comment") or original_name),
            "ordinal_position": ordinal,
            "data_type": "TEXT",
        })
        existing_originals.add(original_name)

    return planned


def _add_columns_to_existing_table(
    conn: Connection,
    pg_schema: str,
    table_name: str,
    table_id: str,
    new_cols: list[dict],
) -> None:
    table_ref = qualified_identifier(pg_schema, table_name)
    for c in new_cols:
        conn.execute(text(
            f"ALTER TABLE {table_ref} "
            f"ADD COLUMN IF NOT EXISTS {quote_identifier(c['physical_name'])} TEXT"
        ))
        conn.execute(text(
            f"COMMENT ON COLUMN {table_ref}.{quote_identifier(c['physical_name'])} IS :comment"
        ), {"comment": c["column_comment"]})
        conn.execute(text("""
            INSERT INTO meta.logical_columns
                (id, table_id, original_name, physical_name, column_comment,
                 ordinal_position, data_type, is_active, created_at, updated_at)
            VALUES
                (:id, :tid, :orig, :phys, :comment, :pos, 'TEXT', true, now(), now())
        """), {
            "id": c["id"],
            "tid": table_id,
            "orig": c["original_name"],
            "phys": c["physical_name"],
            "comment": c["column_comment"],
            "pos": c["ordinal_position"],
        })


def _choose_dedupe_columns(
    upload_columns: list[str],
    existing_cols: list[dict],
    all_cols: list[dict],
) -> list[dict]:
    existing_by_original = {c["original_name"]: c for c in existing_cols}
    common_old_cols = [existing_by_original[name] for name in upload_columns if name in existing_by_original]
    if common_old_cols:
        return common_old_cols

    all_by_original = {c["original_name"]: c for c in all_cols}
    return [all_by_original[name] for name in upload_columns if name in all_by_original]


def _filter_new_rows(
    conn: Connection,
    pg_schema: str,
    table_name: str,
    all_cols: list[dict],
    df: pd.DataFrame,
    dedupe_cols: list[dict],
) -> pd.DataFrame:
    if df.empty:
        return df
    if not all_cols:
        raise ValueError("目标表没有可插入字段")
    if not dedupe_cols:
        return df

    rows = []
    seen_keys: set[tuple] = set()
    for _, row in df.iterrows():
        key = tuple(_get_row_value(row, c) for c in dedupe_cols)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if not _row_exists(conn, pg_schema, table_name, dedupe_cols, row):
            rows.append(row.to_dict())

    if not rows:
        return df.iloc[0:0].copy()
    return pd.DataFrame(rows, columns=df.columns)


def _row_exists(
    conn: Connection,
    pg_schema: str,
    table_name: str,
    dedupe_cols: list[dict],
    row: pd.Series,
) -> bool:
    conditions = []
    params = {}
    for idx, c in enumerate(dedupe_cols):
        bind_name = f"v{idx}"
        conditions.append(f"{quote_identifier(c['physical_name'])}::text IS NOT DISTINCT FROM :{bind_name}")
        params[bind_name] = _get_row_value(row, c)

    sql = text(
        f"SELECT 1 FROM {qualified_identifier(pg_schema, table_name)} "
        f"WHERE {' AND '.join(conditions)} LIMIT 1"
    )
    return conn.execute(sql, params).fetchone() is not None


# ── 通用辅助 ─────────────────────────────────────────────────────

def _bulk_insert(conn: Connection, pg_schema: str, table_name: str, cols: list, df: pd.DataFrame) -> None:
    if df.empty:
        return
    if not cols:
        raise ValueError("目标表没有可插入字段")
    phys_names = [c["physical_name"] for c in cols]
    bind_names = [f"v{i}" for i in range(len(phys_names))]
    col_list = ", ".join(quote_identifier(c) for c in phys_names)
    placeholders = ", ".join(f":{name}" for name in bind_names)
    sql = text(
        f"INSERT INTO {qualified_identifier(pg_schema, table_name)} ({col_list}) "
        f"VALUES ({placeholders})"
    )
    _execute_df(conn, sql, cols, df, bind_names)


def _execute_df(conn: Connection, sql, cols: list, df: pd.DataFrame, bind_names: list[str]) -> None:
    rows = _df_to_rows(cols, df, bind_names)
    if rows:
        conn.execute(sql, rows)


def _df_to_rows(cols: list, df: pd.DataFrame, bind_names: list[str]) -> list:
    """将 DataFrame 转为 [{physical_name: value}] 列表。"""
    rows = []
    for _, row in df.iterrows():
        record = {}
        for idx, c in enumerate(cols):
            record[bind_names[idx]] = _get_row_value(row, c)
        rows.append(record)
    return rows


def _get_row_value(row: pd.Series, col: dict):
    orig = col.get("original_name", col["physical_name"])
    phys = col["physical_name"]
    if orig in row.index:
        val = row[orig]
    elif phys in row.index:
        val = row[phys]
    else:
        val = None
    return _normalize_cell_value(val)


def _normalize_cell_value(value):
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _get_active_columns(conn: Connection, table_id: str) -> list:
    rows = conn.execute(text("""
        SELECT id, original_name, physical_name, column_comment,
               ordinal_position, data_type
        FROM meta.logical_columns
        WHERE table_id=:tid AND is_active=true
        ORDER BY ordinal_position
    """), {"tid": table_id}).fetchall()
    return [dict(r._mapping) for r in rows]


def _get_physical_column_names(conn: Connection, pg_schema: str, table_name: str) -> set[str]:
    rows = conn.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema=:schema AND table_name=:table
    """), {"schema": pg_schema, "table": table_name}).fetchall()
    return {r.column_name for r in rows}


def _fetch_upload(conn: Connection, upload_id: str) -> Optional[dict]:
    row = conn.execute(text("""
        SELECT id, table_id, stored_path, action_type, status,
               llm_proposal, diff_summary
        FROM meta.upload_history WHERE id=:id
    """), {"id": upload_id}).fetchone()
    if row is None:
        return None
    return dict(row._mapping)


def _load_dataframe(path: Path) -> pd.DataFrame:
    from utils.data_loader import read_data_file
    return read_data_file(path)
