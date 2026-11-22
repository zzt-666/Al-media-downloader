from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import FILE_TTL_SECONDS, MAX_CONCURRENT_DOWNLOADS


@dataclass
class FileRecord:
    path: Path
    created_at: float
    title: str
    ext: str
    filename: str
    size: int


class FileRegistry:
    """In-memory file_id registry with TTL cleanup and download concurrency limit."""

    def __init__(
        self,
        max_concurrent: int = MAX_CONCURRENT_DOWNLOADS,
        ttl_seconds: int = FILE_TTL_SECONDS,
    ) -> None:
        self._lock = threading.Lock()
        self._files: dict[str, FileRecord] = {}
        self._semaphore = threading.Semaphore(max_concurrent)
        self._ttl_seconds = ttl_seconds

    def try_acquire_download_slot(self) -> bool:
        return self._semaphore.acquire(blocking=False)

    def release_download_slot(self) -> None:
        self._semaphore.release()

    def register(
        self,
        path: Path,
        title: str,
        ext: str,
        filename: str,
        size: int,
    ) -> str:
        file_id = str(uuid.uuid4())
        with self._lock:
            self._files[file_id] = FileRecord(
                path=path,
                created_at=time.time(),
                title=title,
                ext=ext,
                filename=filename,
                size=size,
            )
        return file_id

    def get(self, file_id: str) -> Optional[FileRecord]:
        self.cleanup_expired()
        with self._lock:
            record = self._files.get(file_id)
            if record is None:
                return None
            if not record.path.is_file():
                self._files.pop(file_id, None)
                return None
            return record

    def cleanup_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                fid
                for fid, rec in self._files.items()
                if now - rec.created_at > self._ttl_seconds
            ]
            for fid in expired:
                rec = self._files.pop(fid, None)
                if rec is not None:
                    self._safe_unlink(rec.path)

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


registry = FileRegistry()
