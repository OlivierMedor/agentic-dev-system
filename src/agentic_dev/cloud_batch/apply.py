from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.cloud_batch.service import BatchService


@dataclass(frozen=True)
class BatchApplyResult:
    batch_id: str
    status: str
    dry_run: bool
    plan_checksum: str


def apply_batch(project_path: Path, batch_id: str, *, dry_run: bool = False) -> BatchApplyResult:
    service = BatchService(project_path)
    result = service.apply(batch_id, dry_run=dry_run)
    return BatchApplyResult(batch_id=batch_id, status=result.status, dry_run=dry_run, plan_checksum=result.plan.checksums.get("plan", ""))

