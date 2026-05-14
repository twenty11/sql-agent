"""管理员审计日志路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_session, require_admin
from auth.dependencies import UserContext
from db.crud.audit import list_audit_logs

router = APIRouter(prefix="/admin/audit", tags=["管理员-审计日志"])


@router.get("")
async def get_audit_logs(
    user_id: str | None = Query(default=None, description="按用户 ID 过滤"),
    skip: int = 0,
    limit: int = 100,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    logs = await list_audit_logs(db, user_id=user_id, skip=skip, limit=limit)
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "session_id": log.session_id,
            "question": log.question,
            "generated_sql": log.generated_sql,
            "execution_success": log.execution_success,
            "execution_time_ms": log.execution_time_ms,
            "row_count": log.row_count,
            "error_message": log.error_message,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
