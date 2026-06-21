from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import yaml


BATCH_SCHEMA_VERSION = 1
ATTEMPT_SCHEMA_VERSION = 1
BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION = "cloud_queue_orchestration"

BATCH_STATUSES = (
    "draft",
    "ready",
    "exported",
    "awaiting_responses",
    "responses_imported",
    "validation_partial",
    "validation_complete",
    "planning",
    "planned",
    "applying",
    "partially_applied",
    "applied",
    "resume_pending",
    "resuming",
    "partially_resumed",
    "resumed",
    "partially_failed",
    "failed",
    "rollback_pending",
    "rolling_back",
    "partially_rolled_back",
    "rolled_back",
    "cancelled",
    "superseded",
)

BATCH_TERMINAL_STATUSES = (
    "applied",
    "resumed",
    "failed",
    "rolled_back",
    "cancelled",
    "superseded",
)

BatchStatus = str
BatchType = str


@dataclass(frozen=True)
class ExecutionPolicy:
    manual_cloud_only: bool = True
    automatic_apply_enabled: bool = False
    automatic_resume_enabled: bool = False
    max_concurrency: int = 1
    max_retry_attempts: int = 3
    packet_size_limit_bytes: int = 5 * 1024 * 1024
    response_bundle_limit_bytes: int = 5 * 1024 * 1024
    request_limit: int = 32

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionPolicy":
        return cls(
            manual_cloud_only=bool(data.get("manual_cloud_only", True)),
            automatic_apply_enabled=bool(data.get("automatic_apply_enabled", False)),
            automatic_resume_enabled=bool(data.get("automatic_resume_enabled", False)),
            max_concurrency=int(data.get("max_concurrency", 1)),
            max_retry_attempts=int(data.get("max_retry_attempts", 3)),
            packet_size_limit_bytes=int(data.get("packet_size_limit_bytes", 5 * 1024 * 1024)),
            response_bundle_limit_bytes=int(data.get("response_bundle_limit_bytes", 5 * 1024 * 1024)),
            request_limit=int(data.get("request_limit", 32)),
        )


@dataclass(frozen=True)
class BatchDependencyGraph:
    schema_version: int
    batch_id: str
    node_ids: tuple[str, ...]
    dependency_map: dict[str, tuple[str, ...]]
    topological_order: tuple[str, ...]
    ready_set: tuple[str, ...] = ()
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "node_ids": list(self.node_ids),
            "dependency_map": {key: list(value) for key, value in sorted(self.dependency_map.items())},
            "topological_order": list(self.topological_order),
            "ready_set": list(self.ready_set),
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BatchDependencyGraph":
        return cls(
            schema_version=int(data.get("schema_version", BATCH_SCHEMA_VERSION)),
            batch_id=str(data.get("batch_id", "")),
            node_ids=tuple(str(item) for item in data.get("node_ids", []) or []),
            dependency_map={
                str(key): tuple(str(item) for item in value or [])
                for key, value in dict(data.get("dependency_map", {}) or {}).items()
            },
            topological_order=tuple(str(item) for item in data.get("topological_order", []) or []),
            ready_set=tuple(str(item) for item in data.get("ready_set", []) or []),
            checksum=str(data.get("checksum", "")),
        )


@dataclass(frozen=True)
class BatchItem:
    item_id: str
    request_id: str
    response_id: str = ""
    status: BatchStatus = "draft"
    dependencies: tuple[str, ...] = ()
    writable_paths: tuple[str, ...] = ()
    request_checksum: str = ""
    response_checksum: str = ""
    approval_checksum: str = ""
    plan_checksum: str = ""
    application_id: str = ""
    revision_id: str = ""
    lease_id: str = ""
    attempt_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["dependencies"] = list(self.dependencies)
        data["writable_paths"] = list(self.writable_paths)
        data["attempt_ids"] = list(self.attempt_ids)
        data["notes"] = list(self.notes)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BatchItem":
        return cls(
            item_id=str(data.get("item_id", "")),
            request_id=str(data.get("request_id", "")),
            response_id=str(data.get("response_id", "")),
            status=str(data.get("status", "draft")),
            dependencies=tuple(str(item) for item in data.get("dependencies", []) or []),
            writable_paths=tuple(str(item) for item in data.get("writable_paths", []) or []),
            request_checksum=str(data.get("request_checksum", "")),
            response_checksum=str(data.get("response_checksum", "")),
            approval_checksum=str(data.get("approval_checksum", "")),
            plan_checksum=str(data.get("plan_checksum", "")),
            application_id=str(data.get("application_id", "")),
            revision_id=str(data.get("revision_id", "")),
            lease_id=str(data.get("lease_id", "")),
            attempt_ids=tuple(str(item) for item in data.get("attempt_ids", []) or []),
            notes=tuple(str(item) for item in data.get("notes", []) or []),
            result=dict(data.get("result", {}) or {}),
        )


@dataclass(frozen=True)
class ExecutionWave:
    wave_id: str
    phase: str
    item_ids: tuple[str, ...]
    blocked_by: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["item_ids"] = list(self.item_ids)
        data["blocked_by"] = list(self.blocked_by)
        data["prerequisites"] = list(self.prerequisites)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionWave":
        return cls(
            wave_id=str(data.get("wave_id", "")),
            phase=str(data.get("phase", "")),
            item_ids=tuple(str(item) for item in data.get("item_ids", []) or []),
            blocked_by=tuple(str(item) for item in data.get("blocked_by", []) or []),
            prerequisites=tuple(str(item) for item in data.get("prerequisites", []) or []),
            checksum=str(data.get("checksum", "")),
        )


@dataclass(frozen=True)
class AttemptRecord:
    schema_version: int
    attempt_id: str
    batch_id: str
    phase: str
    created_at: str
    item_ids: tuple[str, ...]
    previous_attempt_id: str | None = None
    checksum: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["item_ids"] = list(self.item_ids)
        data["details"] = dict(self.details)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttemptRecord":
        return cls(
            schema_version=int(data.get("schema_version", ATTEMPT_SCHEMA_VERSION)),
            attempt_id=str(data.get("attempt_id", "")),
            batch_id=str(data.get("batch_id", "")),
            phase=str(data.get("phase", "")),
            created_at=str(data.get("created_at", "")),
            item_ids=tuple(str(item) for item in data.get("item_ids", []) or []),
            previous_attempt_id=_maybe_text(data.get("previous_attempt_id")),
            checksum=str(data.get("checksum", "")),
            details=dict(data.get("details", {}) or {}),
        )


@dataclass(frozen=True)
class ProgressSummary:
    total: int
    pending: int
    running: int
    succeeded: int
    failed: int
    blocked: int
    skipped: int
    cancelled: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProgressSummary":
        return cls(
            total=int(data.get("total", 0)),
            pending=int(data.get("pending", 0)),
            running=int(data.get("running", 0)),
            succeeded=int(data.get("succeeded", 0)),
            failed=int(data.get("failed", 0)),
            blocked=int(data.get("blocked", 0)),
            skipped=int(data.get("skipped", 0)),
            cancelled=int(data.get("cancelled", 0)),
        )


@dataclass(frozen=True)
class ItemResult:
    item_id: str
    outcome: str
    message: str
    request_checksum: str = ""
    response_checksum: str = ""
    approval_checksum: str = ""
    plan_checksum: str = ""
    application_id: str = ""
    revision_id: str = ""
    lease_ids: tuple[str, ...] = ()
    attempt_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["lease_ids"] = list(self.lease_ids)
        data["details"] = dict(self.details)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemResult":
        return cls(
            item_id=str(data.get("item_id", "")),
            outcome=str(data.get("outcome", "")),
            message=str(data.get("message", "")),
            request_checksum=str(data.get("request_checksum", "")),
            response_checksum=str(data.get("response_checksum", "")),
            approval_checksum=str(data.get("approval_checksum", "")),
            plan_checksum=str(data.get("plan_checksum", "")),
            application_id=str(data.get("application_id", "")),
            revision_id=str(data.get("revision_id", "")),
            lease_ids=tuple(str(item) for item in data.get("lease_ids", []) or []),
            attempt_id=str(data.get("attempt_id", "")),
            details=dict(data.get("details", {}) or {}),
        )


@dataclass(frozen=True)
class BatchResult:
    batch_id: str
    status: BatchStatus
    progress: ProgressSummary
    item_results: tuple[ItemResult, ...]
    attempt_ids: tuple[str, ...] = ()
    checksum: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["progress"] = self.progress.to_dict()
        data["item_results"] = [item.to_dict() for item in self.item_results]
        data["attempt_ids"] = list(self.attempt_ids)
        data["details"] = dict(self.details)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BatchResult":
        return cls(
            batch_id=str(data.get("batch_id", "")),
            status=str(data.get("status", "draft")),
            progress=ProgressSummary.from_dict(dict(data.get("progress", {}) or {})),
            item_results=tuple(
                ItemResult.from_dict(item)
                for item in data.get("item_results", []) or []
                if isinstance(item, dict)
            ),
            attempt_ids=tuple(str(item) for item in data.get("attempt_ids", []) or []),
            checksum=str(data.get("checksum", "")),
            details=dict(data.get("details", {}) or {}),
        )


@dataclass(frozen=True)
class LockRecord:
    schema_version: int
    lock_id: str
    batch_id: str
    operation: str
    holder: str
    created_at: str
    expires_at: str | None = None
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LockRecord":
        return cls(
            schema_version=int(data.get("schema_version", BATCH_SCHEMA_VERSION)),
            lock_id=str(data.get("lock_id", "")),
            batch_id=str(data.get("batch_id", "")),
            operation=str(data.get("operation", "")),
            holder=str(data.get("holder", "")),
            created_at=str(data.get("created_at", "")),
            expires_at=_maybe_text(data.get("expires_at")),
            checksum=str(data.get("checksum", "")),
        )


@dataclass(frozen=True)
class RecoveryRecord:
    schema_version: int
    batch_id: str
    created_at: str
    findings: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    reconciled: bool
    checksum: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["findings"] = list(self.findings)
        data["recommended_actions"] = list(self.recommended_actions)
        data["details"] = dict(self.details)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecoveryRecord":
        return cls(
            schema_version=int(data.get("schema_version", BATCH_SCHEMA_VERSION)),
            batch_id=str(data.get("batch_id", "")),
            created_at=str(data.get("created_at", "")),
            findings=tuple(str(item) for item in data.get("findings", []) or []),
            recommended_actions=tuple(str(item) for item in data.get("recommended_actions", []) or []),
            reconciled=bool(data.get("reconciled", False)),
            checksum=str(data.get("checksum", "")),
            details=dict(data.get("details", {}) or {}),
        )


@dataclass(frozen=True)
class OrchestrationPlan:
    schema_version: int
    batch_id: str
    plan_id: str
    batch_type: BatchType
    created_at: str
    item_ids: tuple[str, ...]
    items: tuple[BatchItem, ...]
    dependency_graph: BatchDependencyGraph
    execution_policy: ExecutionPolicy
    execution_waves: tuple[ExecutionWave, ...]
    conflict_graph: tuple[dict[str, Any], ...]
    expected_revision_chain: tuple[str, ...]
    checksums: dict[str, str]
    progress: ProgressSummary
    status: BatchStatus = "planned"
    dry_run: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "plan_id": self.plan_id,
            "batch_type": self.batch_type,
            "created_at": self.created_at,
            "item_ids": list(self.item_ids),
            "items": [item.to_dict() for item in self.items],
            "dependency_graph": self.dependency_graph.to_dict(),
            "execution_policy": self.execution_policy.to_dict(),
            "execution_waves": [wave.to_dict() for wave in self.execution_waves],
            "conflict_graph": [dict(item) for item in self.conflict_graph],
            "expected_revision_chain": list(self.expected_revision_chain),
            "checksums": dict(self.checksums),
            "progress": self.progress.to_dict(),
            "status": self.status,
            "dry_run": self.dry_run,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrchestrationPlan":
        return cls(
            schema_version=int(data.get("schema_version", BATCH_SCHEMA_VERSION)),
            batch_id=str(data.get("batch_id", "")),
            plan_id=str(data.get("plan_id", "")),
            batch_type=str(data.get("batch_type", BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION)),
            created_at=str(data.get("created_at", "")),
            item_ids=tuple(str(item) for item in data.get("item_ids", []) or []),
            items=tuple(
                BatchItem.from_dict(item)
                for item in data.get("items", []) or []
                if isinstance(item, dict)
            ),
            dependency_graph=BatchDependencyGraph.from_dict(dict(data.get("dependency_graph", {}) or {})),
            execution_policy=ExecutionPolicy.from_dict(dict(data.get("execution_policy", {}) or {})),
            execution_waves=tuple(
                ExecutionWave.from_dict(item)
                for item in data.get("execution_waves", []) or []
                if isinstance(item, dict)
            ),
            conflict_graph=tuple(
                dict(item)
                for item in data.get("conflict_graph", []) or []
                if isinstance(item, dict)
            ),
            expected_revision_chain=tuple(str(item) for item in data.get("expected_revision_chain", []) or []),
            checksums={str(key): str(value) for key, value in dict(data.get("checksums", {}) or {}).items()},
            progress=ProgressSummary.from_dict(dict(data.get("progress", {}) or {})),
            status=str(data.get("status", "planned")),
            dry_run=bool(data.get("dry_run", False)),
            details=dict(data.get("details", {}) or {}),
        )


@dataclass(frozen=True)
class BatchRecord:
    schema_version: int
    batch_id: str
    batch_type: BatchType
    created_at: str
    status: BatchStatus
    item_ids: tuple[str, ...]
    items: tuple[BatchItem, ...]
    dependency_graph: BatchDependencyGraph
    execution_policy: ExecutionPolicy
    progress: ProgressSummary
    results: BatchResult
    checksums: dict[str, str]
    attempts: tuple[AttemptRecord, ...] = ()
    audits: tuple[str, ...] = ()
    latest_plan_id: str = ""
    latest_attempt_id: str = ""
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "batch_type": self.batch_type,
            "created_at": self.created_at,
            "status": self.status,
            "item_ids": list(self.item_ids),
            "items": [item.to_dict() for item in self.items],
            "dependency_graph": self.dependency_graph.to_dict(),
            "execution_policy": self.execution_policy.to_dict(),
            "progress": self.progress.to_dict(),
            "results": self.results.to_dict(),
            "checksums": dict(self.checksums),
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "audits": list(self.audits),
            "latest_plan_id": self.latest_plan_id,
            "latest_attempt_id": self.latest_attempt_id,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BatchRecord":
        return cls(
            schema_version=int(data.get("schema_version", BATCH_SCHEMA_VERSION)),
            batch_id=str(data.get("batch_id", "")),
            batch_type=str(data.get("batch_type", BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION)),
            created_at=str(data.get("created_at", "")),
            status=str(data.get("status", "draft")),
            item_ids=tuple(str(item) for item in data.get("item_ids", []) or []),
            items=tuple(
                BatchItem.from_dict(item)
                for item in data.get("items", []) or []
                if isinstance(item, dict)
            ),
            dependency_graph=BatchDependencyGraph.from_dict(dict(data.get("dependency_graph", {}) or {})),
            execution_policy=ExecutionPolicy.from_dict(dict(data.get("execution_policy", {}) or {})),
            progress=ProgressSummary.from_dict(dict(data.get("progress", {}) or {})),
            results=BatchResult.from_dict(dict(data.get("results", {}) or {})),
            checksums={str(key): str(value) for key, value in dict(data.get("checksums", {}) or {}).items()},
            attempts=tuple(
                AttemptRecord.from_dict(item)
                for item in data.get("attempts", []) or []
                if isinstance(item, dict)
            ),
            audits=tuple(str(item) for item in data.get("audits", []) or []),
            latest_plan_id=str(data.get("latest_plan_id", "")),
            latest_attempt_id=str(data.get("latest_attempt_id", "")),
            notes=tuple(str(item) for item in data.get("notes", []) or []),
        )


def validate_supported_batch_type(batch_type: str) -> None:
    if batch_type != BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION:
        raise ValueError(f"Unsupported batch type: {batch_type}")


def validate_status(status: str) -> None:
    if status not in BATCH_STATUSES:
        raise ValueError(f"Invalid batch status: {status}")


def validate_checksum(checksum: str) -> None:
    if not checksum:
        return
    normalized = checksum.strip()
    if normalized.startswith("sha256:"):
        normalized = normalized[len("sha256:") :]
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized.lower()):
        raise ValueError(f"Malformed checksum: {checksum}")


def validate_execution_policy(policy: ExecutionPolicy) -> None:
    if policy.manual_cloud_only is not True:
        raise ValueError("Batch execution must remain manual-cloud-only.")
    if policy.automatic_apply_enabled:
        raise ValueError("Automatic batch apply must remain disabled.")
    if policy.automatic_resume_enabled:
        raise ValueError("Automatic batch resume must remain disabled.")
    for field_name, value in (
        ("max_concurrency", policy.max_concurrency),
        ("max_retry_attempts", policy.max_retry_attempts),
        ("packet_size_limit_bytes", policy.packet_size_limit_bytes),
        ("response_bundle_limit_bytes", policy.response_bundle_limit_bytes),
        ("request_limit", policy.request_limit),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"Invalid execution policy limit: {field_name}")


def validate_batch_record(record: BatchRecord) -> None:
    if record.schema_version != BATCH_SCHEMA_VERSION:
        raise ValueError(f"Unsupported batch schema version: {record.schema_version}")
    validate_supported_batch_type(record.batch_type)
    validate_status(record.status)
    validate_execution_policy(record.execution_policy)
    validate_checksum(record.checksums.get("batch_record", ""))
    validate_checksum(record.results.checksum)
    if len(set(record.item_ids)) != len(record.item_ids):
        raise ValueError("Duplicate batch item IDs are not allowed.")
    if len(record.items) != len(record.item_ids):
        raise ValueError("Batch item IDs and item records must match.")
    seen_request_ids: set[str] = set()
    for item in record.items:
        if item.request_id in seen_request_ids:
            raise ValueError("Duplicate request IDs are not allowed in a batch.")
        seen_request_ids.add(item.request_id)
        validate_checksum(item.request_checksum)
        validate_checksum(item.response_checksum)
        validate_checksum(item.approval_checksum)
        validate_checksum(item.plan_checksum)
        validate_status(item.status)
    dependencies = record.dependency_graph.dependency_map
    for item_id, required in dependencies.items():
        if item_id not in record.item_ids:
            raise ValueError(f"Dependency graph references unknown item: {item_id}")
        for dependency in required:
            if dependency not in record.item_ids:
                raise ValueError(f"Missing dependency: {dependency}")


def _maybe_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def dump_yaml(payload: Any) -> str:
    return yaml.safe_dump(payload, sort_keys=False)

