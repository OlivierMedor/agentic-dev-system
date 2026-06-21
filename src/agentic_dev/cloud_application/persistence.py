from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.cloud_application.models import (
    ActiveRevisionPointer,
    ApplicationPlan,
    ApplicationRecord,
    ExecutionLease,
    TaskPublicationRecord,
    RuntimePlanRevision,
    TransactionRecord,
)


def application_root_path(project_path: Path) -> Path:
    return project_path.resolve() / ".agentic" / "cloud_applications"


def runtime_plan_path(project_path: Path) -> Path:
    return project_path.resolve() / ".agentic" / "runtime_plans"


def application_path(project_path: Path, application_id: str) -> Path:
    return application_root_path(project_path) / "applications" / f"{application_id}.yaml"


def application_plan_path(project_path: Path, application_id: str) -> Path:
    return application_root_path(project_path) / "plans" / f"{application_id}.yaml"


def application_audit_log_path(project_path: Path) -> Path:
    return application_root_path(project_path) / "audits" / "application_audit.jsonl"


def application_recovery_path(project_path: Path) -> Path:
    return application_root_path(project_path) / "recovery" / "recovery.yaml"


def revision_path(project_path: Path, revision_id: str) -> Path:
    return runtime_plan_path(project_path) / "revisions" / f"{revision_id}.yaml"


def active_pointer_path(project_path: Path) -> Path:
    return runtime_plan_path(project_path) / "active.yaml"


def transaction_root_path(project_path: Path) -> Path:
    return runtime_plan_path(project_path) / "transactions"


def publication_root_path(project_path: Path) -> Path:
    return project_path.resolve() / ".agentic" / "execution_leases" / "publications"


def transaction_path(project_path: Path, transaction_id: str) -> Path:
    return transaction_root_path(project_path) / f"{transaction_id}.yaml"


def runtime_active_pointer_path(project_path: Path) -> Path:
    return active_pointer_path(project_path)


def execution_lease_path(project_path: Path, lease_id: str) -> Path:
    return project_path.resolve() / ".agentic" / "execution_leases" / f"{lease_id}.yaml"


def ensure_cloud_application_dirs(project_path: Path) -> None:
    for directory in (
        application_root_path(project_path),
        application_root_path(project_path) / "applications",
        application_root_path(project_path) / "plans",
        application_root_path(project_path) / "audits",
        application_root_path(project_path) / "recovery",
        runtime_plan_path(project_path),
        runtime_plan_path(project_path) / "revisions",
        transaction_root_path(project_path),
        project_path.resolve() / ".agentic" / "execution_leases",
        publication_root_path(project_path),
    ):
        directory.mkdir(parents=True, exist_ok=True)


def write_yaml_atomic(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return path


def write_text_atomic(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return path


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return loaded


def load_application_record(path: Path) -> ApplicationRecord:
    return ApplicationRecord.from_dict(load_yaml_mapping(path))


def load_application_plan(path: Path) -> ApplicationPlan:
    return ApplicationPlan.from_dict(load_yaml_mapping(path))


def load_runtime_revision(path: Path) -> RuntimePlanRevision:
    return RuntimePlanRevision.from_dict(load_yaml_mapping(path))


def load_transaction_record(path: Path) -> TransactionRecord:
    return TransactionRecord.from_dict(load_yaml_mapping(path))


def load_runtime_revisions(project_path: Path) -> list[RuntimePlanRevision]:
    revisions_root = runtime_plan_path(project_path) / "revisions"
    if not revisions_root.exists():
        return []
    result = []
    for path in sorted(revisions_root.glob("*.yaml")):
        result.append(load_runtime_revision(path))
    return result


def load_active_pointer(path: Path) -> ActiveRevisionPointer:
    return ActiveRevisionPointer.from_dict(load_yaml_mapping(path))


def save_application_record(project_path: Path, record: ApplicationRecord) -> Path:
    ensure_cloud_application_dirs(project_path)
    return write_yaml_atomic(application_path(project_path, record.application_id), record.to_dict())


def save_application_plan(project_path: Path, plan: ApplicationPlan) -> Path:
    ensure_cloud_application_dirs(project_path)
    return write_yaml_atomic(application_plan_path(project_path, plan.application_id), plan.to_dict())


def save_runtime_revision(project_path: Path, revision: RuntimePlanRevision) -> Path:
    ensure_cloud_application_dirs(project_path)
    return write_yaml_atomic(revision_path(project_path, revision.revision_id), revision.to_dict())


def save_transaction_record(project_path: Path, record: TransactionRecord) -> Path:
    ensure_cloud_application_dirs(project_path)
    return write_yaml_atomic(transaction_path(project_path, record.transaction_id), record.to_dict())


def save_active_pointer(project_path: Path, pointer: ActiveRevisionPointer) -> Path:
    ensure_cloud_application_dirs(project_path)
    return write_yaml_atomic(active_pointer_path(project_path), pointer.to_dict())


def save_execution_lease(project_path: Path, lease: ExecutionLease) -> Path:
    ensure_cloud_application_dirs(project_path)
    return write_yaml_atomic(execution_lease_path(project_path, lease.lease_id), lease.to_dict())


def publication_path(project_path: Path, lease_id: str) -> Path:
    return publication_root_path(project_path) / f"{lease_id}.yaml"


def save_task_publication_record(project_path: Path, record: TaskPublicationRecord) -> Path:
    ensure_cloud_application_dirs(project_path)
    return write_yaml_atomic(publication_path(project_path, record.lease_id), record.to_dict())


def load_task_publication_record(path: Path) -> TaskPublicationRecord:
    return TaskPublicationRecord.from_dict(load_yaml_mapping(path))


def load_task_publication_records(project_path: Path) -> list[TaskPublicationRecord]:
    root = publication_root_path(project_path)
    if not root.exists():
        return []
    return [load_task_publication_record(path) for path in sorted(root.glob("*.yaml"))]


def load_execution_lease(path: Path) -> ExecutionLease:
    return ExecutionLease.from_dict(load_yaml_mapping(path))


def load_execution_leases(project_path: Path) -> list[ExecutionLease]:
    leases_root = project_path.resolve() / ".agentic" / "execution_leases"
    if not leases_root.exists():
        return []
    return [load_execution_lease(path) for path in sorted(leases_root.glob("*.yaml"))]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")
    return path


def checksum_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized_yaml_checksum(payload: Any) -> str:
    return checksum_text(yaml.safe_dump(payload, sort_keys=True))


def canonical_model_checksum(obj: Any) -> str:
    if hasattr(obj, "to_dict"):
        payload = obj.to_dict()
    else:
        payload = asdict(obj)
    return normalized_yaml_checksum(payload)
