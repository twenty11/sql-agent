"""审计日志异步写入任务"""

import asyncio
from typing import Optional

from tasks import celery_app
from tasks.path_setup import ensure_backend_root_on_path

ensure_backend_root_on_path()


@celery_app.task(name="tasks.audit.write_audit_log_task", bind=True, max_retries=3)
def write_audit_log_task(
    self,
    user_id: Optional[str],
    session_id: Optional[str],
    question: Optional[str],
    generated_sql: Optional[str],
    execution_success: Optional[bool],
    execution_time_ms: Optional[int],
    row_count: Optional[int] = None,
    error_message: Optional[str] = None,
):
    """异步写入审计日志到 PostgreSQL"""
    try:
        ensure_backend_root_on_path()
        asyncio.run(_write_log(
            user_id, session_id, question, generated_sql,
            execution_success, execution_time_ms, row_count, error_message,
        ))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)


async def _write_log(
    user_id, session_id, question, generated_sql,
    execution_success, execution_time_ms, row_count, error_message,
):
    ensure_backend_root_on_path()
    from db.async_connection import AsyncSessionLocal
    from db.crud.audit import write_audit_log

    async with AsyncSessionLocal() as db:
        await write_audit_log(
            db,
            user_id=user_id,
            session_id=session_id,
            question=question,
            generated_sql=generated_sql,
            execution_success=execution_success,
            execution_time_ms=execution_time_ms,
            row_count=row_count,
            error_message=error_message,
        )
