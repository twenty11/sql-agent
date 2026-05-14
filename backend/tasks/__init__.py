"""Celery 应用初始化"""

import sys

from celery import Celery

from .path_setup import ensure_backend_root_on_path

ensure_backend_root_on_path()
from config import get_settings


def make_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "sql_agent",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["tasks.audit", "tasks.vectorstore", "tasks.uploads"],
    )
    config = {
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "Asia/Shanghai",
        "enable_utc": True,
        "task_track_started": True,
    }
    if sys.platform.startswith("win"):
        # Celery's default prefork pool is not reliable on Windows and can fail
        # before task code runs with: ValueError("not enough values to unpack").
        config.update(
            worker_pool="solo",
            worker_concurrency=1,
        )

    app.conf.update(**config)
    return app


celery_app = make_celery()
