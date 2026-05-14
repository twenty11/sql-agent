"""管理员向量库路由（Milvus 版）"""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import text

from api.deps import require_admin
from auth.dependencies import UserContext
from db.async_connection import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin/vectorstore", tags=["管理员-向量库"])


@router.post("/sync")
async def sync_vectorstore(
    background_tasks: BackgroundTasks,
    admin: UserContext = Depends(require_admin),
):
    """触发 Milvus 同步（消费 pending/pending_retry 行）。"""
    background_tasks.add_task(_do_flush)
    return {"message": "向量库同步已在后台启动"}


@router.post("/rebuild")
async def rebuild_vectorstore(
    background_tasks: BackgroundTasks,
    admin: UserContext = Depends(require_admin),
):
    """从 meta.* 全量重建 Milvus collection（兜底操作）。"""
    background_tasks.add_task(_do_rebuild)
    return {"message": "向量库全量重建已在后台启动"}


@router.post("/retry")
async def retry_vectorstore(
    background_tasks: BackgroundTasks,
    admin: UserContext = Depends(require_admin),
):
    """将 failed 行重置后重试同步。"""
    background_tasks.add_task(_do_retry)
    return {"message": "向量库失败重试已在后台启动"}


@router.get("/status")
async def vectorstore_status(admin: UserContext = Depends(require_admin)):
    """返回 collection 数量统计。"""
    from vectorstore.milvus_store import get_milvus_store
    store = get_milvus_store()
    return {
        "table_count": store.count_tables(),
        "ready": store.ping(),
    }


@router.get("/sync-log")
async def sync_log(
    limit: int = 50,
    admin: UserContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """最近的向量同步日志（按时间倒序）。"""
    result = await session.execute(text("""
        SELECT id, target_id, target_type, op, status, attempts, last_error,
               created_at, updated_at
        FROM meta.vector_sync_log
        ORDER BY updated_at DESC
        LIMIT :lim
    """), {"lim": limit})
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


# ── 后台任务函数 ──────────────────────────────────────────────────

def _do_flush():
    from services.milvus_sync import flush_pending_syncs
    flush_pending_syncs()


def _do_rebuild():
    from services.milvus_sync import rebuild_all_from_pg
    rebuild_all_from_pg()


def _do_retry():
    from services.milvus_sync import retry_failed_syncs
    retry_failed_syncs()
