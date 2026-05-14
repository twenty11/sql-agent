"""
Staging：保存上传文件到暂存目录，计算文件指纹，提取 file_info。
"""

import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

from fastapi import UploadFile

from config import get_settings
from utils.file_fingerprint import compute_file_hash
from utils.data_loader import get_file_info, read_data_file


@dataclass
class StagedFile:
    stored_path: str
    file_hash: str
    file_name: str
    file_size: int
    file_info: Dict[str, Any]  # columns, sample_data, etc.


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_upload_staging_dir(configured_path: str | None = None) -> Path:
    """Resolve upload staging dir independently from the process cwd."""
    raw = Path(configured_path or get_settings().upload_staging_dir)
    if raw.is_absolute():
        return raw
    return (_project_root() / raw).resolve()


def resolve_staged_path(stored_path: str | Path) -> Path:
    """Resolve stored upload paths written by old and new app processes."""
    path = Path(stored_path)
    if path.is_absolute():
        return path

    candidates = [
        (Path.cwd() / path).resolve(),
        (_project_root() / path).resolve(),
        (_backend_root() / path).resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[1]


def write_staged_file(
    upload: UploadFile,
    user_id: str,
    *,
    extract_info: bool = True,
) -> StagedFile:
    """
    将上传的 UploadFile 写入暂存目录，返回 StagedFile。

    文件路径格式: {staging_dir}/{user_id}/{uuid}_{filename}
    """
    settings = get_settings()
    staging_dir = resolve_upload_staging_dir(settings.upload_staging_dir) / user_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    dest_name = f"{uuid.uuid4().hex}_{upload.filename}"
    dest_path = staging_dir / dest_name

    # 写文件
    with dest_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    file_size = dest_path.stat().st_size
    file_hash = compute_file_hash(dest_path)

    info: Dict[str, Any] = {}
    if extract_info:
        # 提取文件信息（列名、样本数据等）
        try:
            df = read_data_file(dest_path)
            info = get_file_info(dest_path, df=df)
        except Exception as exc:
            raise ValueError(f"无法读取上传文件 {upload.filename}: {exc}") from exc

    return StagedFile(
        stored_path=str(dest_path.resolve()),
        file_hash=file_hash,
        file_name=upload.filename or dest_name,
        file_size=file_size,
        file_info=info,
    )
