from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from hashlib import sha256
from pathlib import Path

from agentic_dev.cloud_application.models import (
    ActiveRevisionPointer,
    ExecutionLease,
    RuntimePlanRevision,
    TaskPublicationRecord,
    TaskSnapshot,
)
from agentic_dev.cloud_application.persistence import (
    load_execution_leases,
    load_task_publication_records,
    publication_path,
    save_task_publication_record,
)


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
    publication: TaskPublicationRecord,
    lease: ExecutionLease,
    active_pointer: ActiveRevisionPointer,
    revision: RuntimePlanRevision,
    task: TaskSnapshot,
    result_path: Path,
    result_bytes: bytes,
) -> None:
    project_path = project_path.resolve()
    if lease.lease_state != "active":
        raise ValueError("Lease is not active.")
    if lease.lease_id != publication.lease_id:
        raise ValueError("Publication lease does not match the active lease.")
    if lease.task_id != publication.task_id:
        raise ValueError("Lease task does not match the publication task.")
    if lease.execution_attempt_id != publication.execution_attempt_id:
        raise ValueError("Execution attempt does not match the active lease.")
    if lease.runtime_revision_id != publication.revision_id:
        raise ValueError("Publication revision does not match the active lease.")
    if lease.runtime_revision_checksum != publication.revision_checksum:
        raise ValueError("Lease revision checksum does not match the publication revision.")
    if lease.completion_checksum:
        raise ValueError("Lease result has already been published.")
    if publication.revision_id != active_pointer.active_revision_id:
        raise ValueError("Publication revision does not match the active revision.")
    if publication.revision_checksum != active_pointer.active_revision_checksum:
        raise ValueError("Publication revision checksum does not match the active revision.")
    if publication.result_checksum != checksum_bytes(result_bytes):
        raise ValueError("Publication result checksum does not match the result bytes.")
    if not publication.result_checksum:
        raise ValueError("Result checksum is missing.")
    if not result_path.exists():
        raise FileNotFoundError(f"Result path does not exist: {result_path}")
    if publication_path(project_path, lease.lease_id).exists():
        raise ValueError("Result has already been published for this lease.")
    active_leases = {item.lease_id for item in load_execution_leases(project_path) if item.lease_state == "active"}
    if lease.lease_id not in active_leases:
        raise ValueError("Lease is no longer active.")
    if publication.task_id not in {item.task_id for item in revision.task_graph}:
        raise ValueError("Task does not exist in the active revision.")
    task_in_revision = next(item for item in revision.task_graph if item.task_id == publication.task_id)
    if task_in_revision.status != "ready":
        raise ValueError("Task status does not permit publication.")
    if task.task_id != publication.task_id:
        raise ValueError("Task does not match the publication task.")
    task_paths = tuple(task.writable_paths)
    lease_paths = tuple(lease.writable_paths)
    if not set(task_paths).issubset(set(lease_paths)):
        raise ValueError("Task writable paths do not match the lease.")
    if not _path_within_writable_scope(project_path, result_path, lease.writable_paths):
        raise ValueError("Result path is outside the leased writable paths.")
    if publication.validation_status != "passed":
        raise ValueError("Publication validation status does not permit publication.")


def save_publication_record(project_path: Path, record: TaskPublicationRecord) -> Path:
    return save_task_publication_record(project_path, record)


def load_publication_records(project_path: Path) -> list[TaskPublicationRecord]:
    return load_task_publication_records(project_path)


def quarantine_path(project_path: Path, lease_id: str) -> Path:
    return project_path.resolve() / ".agentic" / "execution_leases" / "quarantine" / f"{lease_id}.yaml"


def checksum_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _path_within_writable_scope(project_path: Path, result_path: Path, writable_paths: tuple[str, ...]) -> bool:
    try:
        relative = result_path.resolve().relative_to(project_path.resolve()).as_posix()
    except ValueError:
        return False
    return any(fnmatchcase(relative, pattern) for pattern in writable_paths)
