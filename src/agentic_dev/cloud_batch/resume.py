from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.cloud_batch.service import BatchService


@dataclass(frozen=True)
class BatchResumeResult:
    batch_id: str
    status: str
    resume_group_count: int


def resume_batch(project_path: Path, batch_id: str) -> BatchResumeResult:
    service = BatchService(project_path)
    result = service.resume(batch_id)
    return BatchResumeResult(batch_id=batch_id, status=result.status, resume_group_count=len(result.resume_groups))

