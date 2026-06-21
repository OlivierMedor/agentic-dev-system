from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.cloud_application.models import ActiveRevisionPointer, ExecutionLease
from agentic_dev.cloud_application.persistence import load_execution_leases


@dataclass(frozen=True)
class PublicationResult:
    accepted: bool
    reason: str
    quarantined: bool
    output_path: Path | None = None
    completion_checksum: str | None = None


def validate_publication_gate(
    project_path: Path,
    *,
    lease: ExecutionLease,
    execution_attempt_id: str,
    active_pointer: ActiveRevisionPointer,
    result_checksum: str,
    result_path: Path,
) -> None:
    if lease.lease_state != "active":
        raise ValueError("Lease is not active.")
    if lease.execution_attempt_id != execution_attempt_id:
        raise ValueError("Execution attempt does not match the active lease.")
    if lease.runtime_revision_id != active_pointer.active_revision_id:
        raise ValueError("Lease revision does not match the active revision.")
    if lease.runtime_revision_checksum != active_pointer.active_revision_checksum:
        raise ValueError("Lease revision checksum does not match the active revision.")
    if lease.completion_checksum:
        raise ValueError("Lease result has already been published.")
    if not result_path.exists():
        raise FileNotFoundError(f"Result path does not exist: {result_path}")
    active_leases = {item.lease_id for item in load_execution_leases(project_path) if item.lease_state == "active"}
    if lease.lease_id not in active_leases:
        raise ValueError("Lease is no longer active.")
    if not result_checksum:
        raise ValueError("Result checksum is missing.")


def quarantine_path(project_path: Path, lease_id: str) -> Path:
    return project_path.resolve() / ".agentic" / "execution_leases" / "quarantine" / f"{lease_id}.yaml"
