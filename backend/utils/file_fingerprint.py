"""流式计算文件 SHA-256 指纹。"""

import hashlib
from pathlib import Path


def compute_file_hash(path: Path, chunk_size: int = 65536) -> str:
    """返回文件内容的 SHA-256 十六进制摘要。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()
