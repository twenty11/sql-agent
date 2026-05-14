"""上传批次异步处理任务。"""

from tasks import celery_app
from tasks.path_setup import ensure_backend_root_on_path

ensure_backend_root_on_path()


@celery_app.task(name="tasks.uploads.process_upload_batch_task", bind=True, max_retries=0)
def process_upload_batch_task(self, batch_id: str):
    ensure_backend_root_on_path()
    from services.admin_data_pipeline.upload_batches import process_upload_batch

    return process_upload_batch(batch_id)
