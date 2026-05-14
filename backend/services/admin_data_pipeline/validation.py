"""Validation helpers for admin upload metadata and SQL identifiers."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Mapping, Sequence


_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_SAFE_CHARS_RE = re.compile(r"[^0-9a-zA-Z_]+")
_MULTI_UNDERSCORE_RE = re.compile(r"_+")

_RESERVED_WORDS = {
    "all",
    "and",
    "as",
    "between",
    "case",
    "create",
    "delete",
    "drop",
    "else",
    "from",
    "group",
    "insert",
    "into",
    "join",
    "limit",
    "not",
    "null",
    "or",
    "order",
    "select",
    "table",
    "then",
    "update",
    "where",
}

_ALLOWED_DATA_TYPES = {
    "TEXT",
    "INTEGER",
    "BIGINT",
    "DOUBLE PRECISION",
    "REAL",
    "BOOLEAN",
    "DATE",
    "TIMESTAMP",
    "TIMESTAMPTZ",
}


def validate_upload_file_count(
    file_count: int,
    target_table_id: str | None,
    max_new_table_files: int = 20,
    target_table_ids: Sequence[str] | None = None,
    mode: str | None = None,
) -> list[str | None]:
    """Validate upload batch shape and return the per-file target table ids."""
    if file_count <= 0:
        raise ValueError("请选择文件")

    upload_mode = str(mode or "").strip().lower() or None
    if upload_mode and upload_mode not in {"new", "update"}:
        raise ValueError("上传方式无效")

    single_target = str(target_table_id or "").strip() or None
    repeated_targets = None
    if target_table_ids is not None:
        repeated_targets = [str(item or "").strip() for item in target_table_ids]

    if upload_mode == "new" and (single_target or repeated_targets):
        raise ValueError("新建表不能选择目标表")
    if upload_mode == "update" and not single_target and repeated_targets is None:
        raise ValueError("更新已有表需要选择目标表")

    if single_target and repeated_targets:
        raise ValueError("target_table_id 与 target_table_ids 不能同时使用")

    if single_target:
        if file_count != 1:
            raise ValueError("target_table_id 仅支持 1 个文件；批量更新请使用 target_table_ids")
        return [single_target]

    if repeated_targets is not None:
        if file_count > max_new_table_files:
            raise ValueError(f"更新已有表一次最多上传 {max_new_table_files} 个文件")
        if len(repeated_targets) != file_count:
            raise ValueError("更新已有表需要为每个文件选择一个目标表")
        if any(not item for item in repeated_targets):
            raise ValueError("目标表不能为空")
        if len(set(repeated_targets)) != len(repeated_targets):
            raise ValueError("更新已有表不能重复选择同一张表")
        return repeated_targets

    if file_count > max_new_table_files:
        raise ValueError(f"新建表一次最多上传 {max_new_table_files} 个文件")
    return [None] * file_count


def quote_identifier(identifier: str) -> str:
    """Return a safely quoted PostgreSQL identifier."""
    return f'"{str(identifier).replace("\"", "\"\"")}"'


def qualified_identifier(schema: str, name: str) -> str:
    return f"{quote_identifier(schema)}.{quote_identifier(name)}"


def is_valid_identifier(identifier: str) -> bool:
    value = str(identifier)
    return bool(_IDENTIFIER_RE.match(value)) and value not in _RESERVED_WORDS


def sanitize_identifier(value: object, fallback: str) -> str:
    """Convert arbitrary text into a PostgreSQL-safe lowercase identifier."""
    raw = str(value or "").strip()
    candidate = _SAFE_CHARS_RE.sub("_", raw).lower()
    candidate = _MULTI_UNDERSCORE_RE.sub("_", candidate).strip("_")

    if not candidate or candidate[0].isdigit():
        candidate = fallback
    candidate = candidate[:63].rstrip("_")

    if not candidate or candidate[0].isdigit() or candidate in _RESERVED_WORDS:
        candidate = fallback[:63].rstrip("_") or "col"

    if not _IDENTIFIER_RE.match(candidate):
        candidate = re.sub(r"[^a-z0-9_]", "_", candidate.lower())
        candidate = _MULTI_UNDERSCORE_RE.sub("_", candidate).strip("_")
        if not candidate or candidate[0].isdigit():
            candidate = fallback[:63].rstrip("_") or "col"

    return candidate[:63]


def make_unique_identifier(name: str, existing: Iterable[str]) -> str:
    existing_set = {str(item).lower() for item in existing}
    base = sanitize_identifier(name, "item")
    if base not in existing_set:
        return base

    suffix = 2
    while True:
        suffix_text = f"_{suffix}"
        candidate = f"{base[:63 - len(suffix_text)].rstrip('_')}{suffix_text}"
        if candidate not in existing_set:
            return candidate
        suffix += 1


def make_unique_column_name(name: str, used: set[str], fallback: str) -> str:
    base = sanitize_identifier(name, fallback)
    candidate = base
    suffix = 2
    while candidate in used:
        suffix_text = f"_{suffix}"
        candidate = f"{base[:63 - len(suffix_text)].rstrip('_')}{suffix_text}"
        suffix += 1
    used.add(candidate)
    return candidate


def normalize_data_type(value: object) -> str:
    raw = str(value or "TEXT").strip().upper()
    if raw in _ALLOWED_DATA_TYPES:
        return raw
    if re.fullmatch(r"(VARCHAR|CHAR)\([1-9][0-9]{0,3}\)", raw):
        return raw
    if re.fullmatch(r"NUMERIC\([1-9][0-9]?(,[0-9]{1,2})?\)", raw):
        return raw
    return "TEXT"


def normalize_new_table_proposal(
    proposal: Mapping[str, object],
    file_columns: Sequence[str],
    existing_table_names: Iterable[str] = (),
) -> dict:
    """Validate and normalize LLM metadata for a new uploaded table."""
    if not isinstance(proposal, Mapping):
        raise ValueError("LLM 元数据格式无效")
    if not file_columns:
        raise ValueError("上传文件没有可用字段")

    duplicates = [name for name, count in Counter(file_columns).items() if count > 1]
    if duplicates:
        raise ValueError(f"上传文件存在重复字段: {duplicates}")

    raw_columns = proposal.get("columns")
    if not isinstance(raw_columns, list) or len(raw_columns) != len(file_columns):
        raise ValueError("LLM 返回字段数量与上传文件不一致")

    ordered_columns = _order_columns(raw_columns, file_columns)
    table_name = make_unique_identifier(
        sanitize_identifier(proposal.get("table_name"), "uploaded_table"),
        existing_table_names,
    )

    used_column_names: set[str] = set()
    columns: list[dict] = []
    for idx, original_name in enumerate(file_columns, 1):
        raw = ordered_columns[idx - 1]
        fallback = f"col_{idx}"
        column_name = make_unique_column_name(
            raw.get("column_name") or original_name,
            used_column_names,
            fallback,
        )
        columns.append({
            "original_name": original_name,
            "column_name": column_name,
            "column_comment": str(raw.get("column_comment") or original_name),
            "data_type": normalize_data_type(raw.get("data_type")),
        })

    return {
        "table_name": table_name,
        "display_name": str(proposal.get("display_name") or table_name),
        "table_comment": str(proposal.get("table_comment") or ""),
        "columns": columns,
    }


def normalize_schema_change_columns(
    proposal: Mapping[str, object],
    new_file_columns: Sequence[str],
    existing_column_names: Iterable[str] = (),
) -> list[dict]:
    """Validate and normalize LLM metadata for columns added to an existing table."""
    if not isinstance(proposal, Mapping):
        raise ValueError("LLM 元数据格式无效")
    if not new_file_columns:
        return []

    duplicates = [name for name, count in Counter(new_file_columns).items() if count > 1]
    if duplicates:
        raise ValueError(f"上传文件存在重复新增字段: {duplicates}")

    raw_columns = proposal.get("columns")
    if not isinstance(raw_columns, list) or len(raw_columns) != len(new_file_columns):
        raise ValueError("LLM 返回新增字段数量与上传文件不一致")

    ordered_columns = _order_columns(raw_columns, new_file_columns)
    used_column_names = {str(name) for name in existing_column_names}
    columns: list[dict] = []
    for idx, original_name in enumerate(new_file_columns, 1):
        raw = ordered_columns[idx - 1]
        fallback = f"col_{idx}"
        column_name = make_unique_column_name(
            raw.get("column_name") or original_name,
            used_column_names,
            fallback,
        )
        columns.append({
            "original_name": original_name,
            "column_name": column_name,
            "column_comment": str(raw.get("column_comment") or original_name),
            "data_type": "TEXT",
        })

    return columns


def _order_columns(raw_columns: list[object], file_columns: Sequence[str]) -> list[dict]:
    normalized = [c if isinstance(c, Mapping) else {} for c in raw_columns]
    names = [str(c.get("original_name") or "") for c in normalized]
    if all(names) and set(names) == set(file_columns):
        by_original = {str(c.get("original_name")): dict(c) for c in normalized}
        return [by_original[name] for name in file_columns]
    return [dict(c) for c in normalized]
