from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.cloud_batch.models import AttemptRecord, BatchRecord, OrchestrationPlan, RecoveryRecord


@dataclass(frozen=True)
class BatchPaths:
    root: Path
    records: Path
    plans: Path
    attempts: Path
    audits: Path
    locks: Path
    recovery: Path
    audit_log: Path


def batch_root_path(project_path: Path) -> Path:
    return project_path.resolve() / ".agentic" / "cloud_batches"


def batch_record_path(project_path: Path, batch_id: str) -> Path:
    return batch_root_path(project_path) / "records" / f"{batch_id}.yaml"


def batch_plan_path(project_path: Path, batch_id: str) -> Path:
    return batch_root_path(project_path) / "plans" / f"{batch_id}.yaml"


def batch_attempts_root(project_path: Path) -> Path:
    return batch_root_path(project_path) / "attempts"


def batch_audit_log_path(project_path: Path) -> Path:
    return batch_root_path(project_path) / "audits" / "batch_audit.jsonl"


def batch_lock_root(project_path: Path) -> Path:
    return batch_root_path(project_path) / "locks"


def batch_recovery_path(project_path: Path, batch_id: str) -> Path:
    return batch_root_path(project_path) / "recovery" / f"{batch_id}.yaml"


def ensure_batch_dirs(project_path: Path) -> BatchPaths:
    root = batch_root_path(project_path)
    paths = BatchPaths(
        root=root,
        records=root / "records",
        plans=root / "plans",
        attempts=root / "attempts",
        audits=root / "audits",
        locks=root / "locks",
        recovery=root / "recovery",
        audit_log=root / "audits" / "batch_audit.jsonl",
    )
    for directory in (paths.root, paths.records, paths.plans, paths.attempts, paths.audits, paths.locks, paths.recovery):
        directory.mkdir(parents=True, exist_ok=True)
    return paths


def _write_atomic_yaml(path: Path, payload: Any) -> Path:
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


def save_batch_record(project_path: Path, record: BatchRecord) -> Path:
    ensure_batch_dirs(project_path)
    return _write_atomic_yaml(batch_record_path(project_path, record.batch_id), record.to_dict())


def load_batch_record(project_path: Path, batch_id: str) -> BatchRecord:
    path = batch_record_path(project_path, batch_id)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Batch record must be a YAML mapping: {path}")
    return BatchRecord.from_dict(loaded)


def save_orchestration_plan(project_path: Path, plan: OrchestrationPlan) -> Path:
    ensure_batch_dirs(project_path)
    return _write_atomic_yaml(batch_plan_path(project_path, plan.batch_id), plan.to_dict())


def load_orchestration_plan(project_path: Path, batch_id: str) -> OrchestrationPlan:
    path = batch_plan_path(project_path, batch_id)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Batch plan must be a YAML mapping: {path}")
    return OrchestrationPlan.from_dict(loaded)


def attempt_record_path(project_path: Path, attempt_id: str, batch_id: str) -> Path:
    return batch_attempts_root(project_path) / batch_id / f"{attempt_id}.yaml"


def save_attempt_record(project_path: Path, record: AttemptRecord) -> Path:
    ensure_batch_dirs(project_path)
    return _write_atomic_yaml(attempt_record_path(project_path, record.attempt_id, record.batch_id), record.to_dict())


def load_attempt_record(project_path: Path, batch_id: str, attempt_id: str) -> AttemptRecord:
    path = attempt_record_path(project_path, attempt_id, batch_id)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Attempt record must be a YAML mapping: {path}")
    return AttemptRecord.from_dict(loaded)


def save_recovery_record(project_path: Path, record: RecoveryRecord) -> Path:
    ensure_batch_dirs(project_path)
    return _write_atomic_yaml(batch_recovery_path(project_path, record.batch_id), record.to_dict())
