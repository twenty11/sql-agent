"""Import-path setup for Celery task execution."""

from pathlib import Path
import sys


def ensure_backend_root_on_path() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    backend_root_text = str(backend_root)
    if backend_root_text not in sys.path:
        sys.path.insert(0, backend_root_text)
