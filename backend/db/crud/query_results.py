"""查询结果快照 CRUD。"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session as SyncSession

from db.models import QueryResult


def _json_safe(obj: Any) -> Any:
    """转换为 JSON 安全对象，保持与消息 metadata 的序列化策略一致。"""
    return json.loads(json.dumps(obj, default=str, ensure_ascii=False))


def _row_to_dict(row: QueryResult, include_data: bool = False) -> dict:
    data = {
        "id": row.id,
        "session_id": row.session_id,
        "message_id": row.message_id,
        "question": row.question,
        "fused_question": row.fused_question,
        "sql": row.sql,
        "columns": row.columns or [],
        "row_count": row.row_count,
        "summary": row.summary or "",
        "referenced_tables": row.referenced_tables or [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if include_data:
        data["result_data"] = row.result_data or {}
    return data


def build_query_result_summary(question: str, result_data: dict | None) -> str:
    """生成可给意图路由使用的短摘要，不额外消耗 LLM。"""
    result_data = result_data or {}
    columns = result_data.get("columns") or []
    row_count = result_data.get("row_count", 0)
    column_text = "、".join(str(c) for c in columns[:8])
    if len(columns) > 8:
        column_text += " 等"
    return f"问题：{question}；返回 {row_count} 行；字段：{column_text or '无'}"


def save_query_result_sync(
    session_id: str,
    message_id: str,
    question: str,
    fused_question: str | None,
    sql: str | None,
    result_data: dict,
    summary: str | None = None,
    referenced_tables: list[str] | None = None,
) -> str:
    """保存一次成功查询的结果快照，返回 result_id。"""
    from db.connection import get_engine

    safe_result = _json_safe(result_data or {})
    columns = safe_result.get("columns") or []
    row_count = int(safe_result.get("row_count") or 0)
    now = datetime.now(timezone.utc)
    result_id = str(uuid.uuid4())

    with SyncSession(get_engine()) as session:
        session.add(QueryResult(
            id=result_id,
            session_id=session_id,
            message_id=message_id,
            question=question,
            fused_question=fused_question,
            sql=sql,
            result_data=safe_result,
            columns=_json_safe(columns),
            row_count=row_count,
            summary=summary or build_query_result_summary(question, safe_result),
            referenced_tables=_json_safe(referenced_tables or []),
            created_at=now,
        ))
        session.commit()
    return result_id


def list_query_result_summaries_sync(session_id: str, limit: int = 10) -> list[dict]:
    """读取当前会话最近的结果摘要，供意图路由判断引用对象。"""
    from db.connection import get_engine

    with SyncSession(get_engine()) as session:
        result = session.execute(
            select(QueryResult)
            .where(QueryResult.session_id == session_id)
            .order_by(desc(QueryResult.created_at))
            .limit(limit)
        )
        return [_row_to_dict(row, include_data=False) for row in result.scalars().all()]


def get_query_results_by_ids_sync(session_id: str, result_ids: list[str]) -> list[dict]:
    """按 result_id 读取同一会话内的完整结果快照。"""
    if not result_ids:
        return []

    from db.connection import get_engine

    with SyncSession(get_engine()) as session:
        result = session.execute(
            select(QueryResult)
            .where(QueryResult.session_id == session_id)
            .where(QueryResult.id.in_(result_ids))
            .order_by(desc(QueryResult.created_at))
        )
        rows = [_row_to_dict(row, include_data=True) for row in result.scalars().all()]

    order = {result_id: idx for idx, result_id in enumerate(result_ids)}
    rows.sort(key=lambda item: order.get(item["id"], len(order)))
    return rows
