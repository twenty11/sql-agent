"""审计日志 CRUD 操作"""

from typing import Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuditLog


async def write_audit_log(
    db: AsyncSession,
    user_id: Optional[str],
    session_id: Optional[str],
    question: Optional[str],
    generated_sql: Optional[str],
    execution_success: Optional[bool],
    execution_time_ms: Optional[int],
    row_count: Optional[int] = None,
    error_message: Optional[str] = None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        session_id=session_id,
        question=question,
        generated_sql=generated_sql,
        execution_success=execution_success,
        execution_time_ms=execution_time_ms,
        row_count=row_count,
        error_message=error_message,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_audit_logs(
    db: AsyncSession,
    user_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLog]:
    query = select(AuditLog).order_by(desc(AuditLog.created_at))
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    result = await db.execute(query.offset(skip).limit(limit))
    return list(result.scalars().all())
