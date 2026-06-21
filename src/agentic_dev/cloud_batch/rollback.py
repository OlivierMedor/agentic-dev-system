from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.cloud_application import build_default_application_service
from agentic_dev.cloud_batch.audit import BatchAuditEvent, append_batch_audit_event
from agentic_dev.cloud_batch.persistence import load_batch_record, save_batch_record
from agentic_dev.cloud_queue.persistence import now_iso


@dataclass(frozen=True)
class RollbackResult:
    batch_id: str
    rolled_back_item_ids: tuple[str, ...]
    blocked_item_ids: tuple[str, ...]
    status: str
    reasons: tuple[str, ...]


def rollback_batch(
    project_path: Path,
    batch_id: str,
    *,
    reason: str = "",
) -> RollbackResult:
    record = load_batch_record(project_path, batch_id)
    service = build_default_application_service(project_path)
    rolled_back: list[str] = []
    blocked: list[str] = []
    reasons: list[str] = []
    for item in reversed(record.items):
        if item.status not in {"applied", "resumed"} and not item.application_id:
            continue
        try:
            service.rollback(item.application_id)
            rolled_back.append(item.item_id)
        except Exception as error:  # noqa: BLE001
            blocked.append(item.item_id)
            reasons.append(f"{item.item_id}: {error}")
            break
    status = "rolled_back" if not blocked else "partially_rolled_back"
    updated = type(record).from_dict({**record.to_dict(), "status": status})
    save_batch_record(project_path, updated)
    append_batch_audit_event(
        project_path,
        BatchAuditEvent(
            event_id="",
            event_type="batch_rollback",
            batch_id=batch_id,
            prior_state=record.status,
            new_state=status,
            timestamp=now_iso(),
            details={"reason": reason, "rolled_back_item_ids": rolled_back, "blocked_item_ids": blocked},
        ),
    )
    return RollbackResult(batch_id=batch_id, rolled_back_item_ids=tuple(rolled_back), blocked_item_ids=tuple(blocked), status=status, reasons=tuple(reasons))

