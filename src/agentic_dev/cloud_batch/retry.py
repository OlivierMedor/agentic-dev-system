from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agentic_dev.cloud_batch.audit import BatchAuditEvent, append_batch_audit_event
from agentic_dev.cloud_batch.models import AttemptRecord
from agentic_dev.cloud_batch.persistence import load_batch_record, save_attempt_record, save_batch_record
from agentic_dev.cloud_queue.persistence import checksum_text, now_iso


@dataclass(frozen=True)
class RetryResult:
    batch_id: str
    attempt_id: str
    prior_attempt_ids: tuple[str, ...]
    status: str


def retry_batch(
    project_path: Path,
    batch_id: str,
    *,
    reason: str = "",
    event_id_factory: Callable[[], str] | None = None,
) -> RetryResult:
    record = load_batch_record(project_path, batch_id)
    attempt_id = f"{batch_id}-attempt-{len(record.attempts) + 1:02d}"
    attempt = AttemptRecord(
        schema_version=1,
        attempt_id=attempt_id,
        batch_id=batch_id,
        phase="retry",
        created_at=now_iso(),
        item_ids=record.item_ids,
        previous_attempt_id=record.latest_attempt_id or None,
        checksum=checksum_text("|".join([batch_id, attempt_id, reason])),
        details={"reason": reason, "prior_attempt_ids": [item.attempt_id for item in record.attempts]},
    )
    save_attempt_record(project_path, attempt)
    append_batch_audit_event(
        project_path,
        BatchAuditEvent(
            event_id="",
            event_type="batch_retry",
            batch_id=batch_id,
            prior_state=record.status,
            new_state="planned",
            timestamp=now_iso(),
            details={"attempt_id": attempt_id, "reason": reason},
        ),
    )
    updated = type(record).from_dict(
        {
            **record.to_dict(),
            "latest_attempt_id": attempt_id,
            "attempts": [*record.attempts, attempt],
            "status": "planned",
        },
    )
    save_batch_record(project_path, updated)
    return RetryResult(batch_id=batch_id, attempt_id=attempt_id, prior_attempt_ids=tuple(item.attempt_id for item in record.attempts), status="planned")

