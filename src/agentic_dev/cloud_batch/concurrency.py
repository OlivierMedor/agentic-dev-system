from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from agentic_dev.cloud_batch.persistence import batch_lock_root, ensure_batch_dirs
from agentic_dev.cloud_queue.persistence import checksum_text, now_iso


@dataclass(frozen=True)
class BatchLock:
    lock_id: str
    batch_id: str
    operation: str
    holder: str
    created_at: str
    lock_path: Path


def batch_lock_path(project_path: Path, batch_id: str, operation: str) -> Path:
    return batch_lock_root(project_path) / f"{batch_id}-{operation}.lock"


@contextmanager
def acquire_batch_lock(project_path: Path, batch_id: str, operation: str, holder: str = "operator"):
    ensure_batch_dirs(project_path)
    lock_path = batch_lock_path(project_path, batch_id, operation)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        raise ValueError(f"Batch lock already exists: {lock_path}")
    lock_path.write_text(
        checksum_text("|".join([batch_id, operation, holder, now_iso()])),
        encoding="utf-8",
    )
    try:
        yield BatchLock(
            lock_id=lock_path.stem,
            batch_id=batch_id,
            operation=operation,
            holder=holder,
            created_at=now_iso(),
            lock_path=lock_path,
        )
    finally:
        lock_path.unlink(missing_ok=True)

