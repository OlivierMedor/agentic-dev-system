from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.cloud_batch.audit import BatchAuditEvent, append_batch_audit_event
from agentic_dev.cloud_batch.models import RecoveryRecord
from agentic_dev.cloud_batch.persistence import load_batch_record, save_recovery_record
from agentic_dev.cloud_queue.persistence import checksum_text, now_iso


@dataclass(frozen=True)
class BatchRecoveryResult:
    batch_id: str
    findings: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    reconciled: bool


def recover_batch(project_path: Path, batch_id: str) -> BatchRecoveryResult:
    record = load_batch_record(project_path, batch_id)
    findings: list[str] = []
    actions: list[str] = []
    reconciled = False
    if record.results.status != record.status:
        findings.append("batch result status diverged from batch record status")
        actions.append("align batch result and batch record status")
    if not record.checksums.get("batch_record"):
        findings.append("missing batch record checksum")
        actions.append("recompute batch checksum")
    if not findings:
        reconciled = True
    recovery = RecoveryRecord(
        schema_version=1,
        batch_id=batch_id,
        created_at=now_iso(),
        findings=tuple(findings),
        recommended_actions=tuple(actions),
        reconciled=reconciled,
        checksum=checksum_text("|".join([batch_id, str(findings), str(actions), str(reconciled)])),
        details={"status": record.status},
    )
    save_recovery_record(project_path, recovery)
    append_batch_audit_event(
        project_path,
        BatchAuditEvent(
            event_id="",
            event_type="batch_recovery",
            batch_id=batch_id,
            prior_state=record.status,
            new_state=record.status,
            timestamp=now_iso(),
            details={"findings": list(findings), "reconciled": reconciled},
        ),
    )
    return BatchRecoveryResult(batch_id=batch_id, findings=tuple(findings), recommended_actions=tuple(actions), reconciled=reconciled)

