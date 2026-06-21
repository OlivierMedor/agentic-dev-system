from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_dev.cloud_application.models import TransactionRecord
from agentic_dev.cloud_application.persistence import (
    load_transaction_record,
    save_transaction_record,
    transaction_path,
)


@dataclass(frozen=True)
class TransactionPhaseUpdate:
    phase: str
    details: dict[str, Any] | None = None
    recovery_action: str = ""


def create_transaction_record(
    *,
    transaction_id: str,
    application_id: str,
    source_revision_id: str,
    source_revision_checksum: str,
    proposed_revision_id: str,
    proposed_revision_checksum: str,
    expected_active_pointer: str,
    created_at: str,
    updated_at: str,
    artifact_paths: tuple[str, ...] = (),
    recovery_action: str = "",
    details: dict[str, Any] | None = None,
) -> TransactionRecord:
    return TransactionRecord(
        schema_version=1,
        transaction_id=transaction_id,
        application_id=application_id,
        source_revision_id=source_revision_id,
        source_revision_checksum=source_revision_checksum,
        proposed_revision_id=proposed_revision_id,
        proposed_revision_checksum=proposed_revision_checksum,
        expected_active_pointer=expected_active_pointer,
        phase="prepared",
        artifact_paths=artifact_paths,
        created_at=created_at,
        updated_at=updated_at,
        recovery_action=recovery_action,
        details=details or {},
    )


def transaction_file(project_path: Path, transaction_id: str) -> Path:
    return transaction_path(project_path, transaction_id)


def save_transaction_phase(
    project_path: Path,
    record: TransactionRecord,
    *,
    phase: str,
    updated_at: str,
    artifact_paths: tuple[str, ...] | None = None,
    details: dict[str, Any] | None = None,
    recovery_action: str | None = None,
) -> TransactionRecord:
    updated = TransactionRecord.from_dict(
        {
            **record.to_dict(),
            "phase": phase,
            "updated_at": updated_at,
            "artifact_paths": list(artifact_paths if artifact_paths is not None else record.artifact_paths),
            "details": details or record.details,
            "recovery_action": recovery_action if recovery_action is not None else record.recovery_action,
        },
    )
    save_transaction_record(project_path, updated)
    return updated


def load_transaction(project_path: Path, transaction_id: str) -> TransactionRecord:
    return load_transaction_record(transaction_file(project_path, transaction_id))
