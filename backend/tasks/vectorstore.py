"""向量库异步同步任务（Milvus 版）"""

from tasks import celery_app
from tasks.path_setup import ensure_backend_root_on_path

ensure_backend_root_on_path()


@celery_app.task(name="tasks.vectorstore.sync_vectorstore_task", bind=True, max_retries=3)
def sync_vectorstore_task(self):
    """消费 meta.vector_sync_log 中 pending/pending_retry 行，同步到 Milvus。"""
    try:
        ensure_backend_root_on_path()
        from services.milvus_sync import flush_pending_syncs
        report = flush_pending_syncs()
        return {"status": "success", "synced": report.success, "failed": report.failed}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="tasks.vectorstore.retry_failed_syncs_task", bind=True, max_retries=1)
def retry_failed_syncs_task(self):
    """将 failed 行重置后重试。"""
    try:
        ensure_backend_root_on_path()
        from services.milvus_sync import retry_failed_syncs
        report = retry_failed_syncs()
        return {"status": "success", "synced": report.success, "failed": report.failed}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
