from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.cloud_batch.audit import BatchAuditEvent, append_batch_audit_event
from agentic_dev.cloud_batch.models import BatchItem
from agentic_dev.cloud_batch.persistence import load_batch_record, save_batch_record
from agentic_dev.cloud_queue.persistence import now_iso


@dataclass(frozen=True)
class CancellationResult:
    batch_id: str
    cancelled_item_ids: tuple[str, ...]
    preserved_item_ids: tuple[str, ...]
    status: str


def cancel_batch(project_path: Path, batch_id: str, reason: str = "") -> CancellationResult:
    record = load_batch_record(project_path, batch_id)
    cancelled: list[str] = []
    preserved: list[str] = []
    updated_items: list[BatchItem] = []
    for item in record.items:
        if item.status in {"applied", "resumed", "failed", "rolled_back"}:
            preserved.append(item.item_id)
            updated_items.append(item)
            continue
        cancelled.append(item.item_id)
        updated_items.append(type(item).from_dict({**item.to_dict(), "status": "cancelled"}))
    updated = type(record).from_dict(
        {
            **record.to_dict(),
            "status": "cancelled",
            "items": [item.to_dict() for item in updated_items],
            "progress": {
                **record.progress.to_dict(),
                "cancelled": record.progress.cancelled + len(cancelled),
            },
        },
    )
    save_batch_record(project_path, updated)
    append_batch_audit_event(
        project_path,
        BatchAuditEvent(
            event_id="",
            event_type="batch_cancel",
            batch_id=batch_id,
            prior_state=record.status,
            new_state="cancelled",
            timestamp=now_iso(),
            details={"reason": reason, "cancelled_item_ids": cancelled},
        ),
    )
    return CancellationResult(batch_id=batch_id, cancelled_item_ids=tuple(cancelled), preserved_item_ids=tuple(preserved), status="cancelled")

