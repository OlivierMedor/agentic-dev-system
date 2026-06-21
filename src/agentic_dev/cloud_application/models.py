from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

APPLICATION_SCHEMA_VERSION = 1
REVISION_SCHEMA_VERSION = 1
ACTIVE_POINTER_SCHEMA_VERSION = 1
LEASE_SCHEMA_VERSION = 1
TRANSACTION_SCHEMA_VERSION = 1

ApplicationState = str
ApplicationOperationType = str

APPLICATION_STATES = (
    "application_planned",
    "application_validation_failed",
    "ready_to_apply",
    "applying",
    "applied",
    "resume_pending",
    "resuming",
    "resumed",
    "resume_failed",
    "rollback_available",
    "rolling_back",
    "rolled_back",
    "rollback_failed",
    "superseded",
    "cancelled",
)

TERMINAL_APPLICATION_STATES = (
    "applied",
    "resumed",
    "resume_failed",
    "rolled_back",
    "rollback_failed",
    "superseded",
    "cancelled",
)

SUPPORTED_APPLICATION_OPERATIONS = (
    "replace_task_with_subtasks",
    "update_task_metadata",
)

SUPPORTED_REJECTED_APPLICATION_OPERATIONS = (
    "add_architecture_overlay",
    "add_remediation_tasks",
    "record_final_cloud_review",
)

TRANSACTION_PHASES = (
    "prepared",
    "revision_written",
    "revision_validated",
    "revision_published",
    "pointer_updated",
    "application_updated",
    "audit_completed",
    "committed",
    "failed",
)


@dataclass(frozen=True)
class TaskSnapshot:
    task_id: str
    title: str
    role: str
    depends_on: tuple[str, ...] = ()
    requirement_ids: tuple[str, ...] = ()
    required_context: tuple[str, ...] = ()
    writable_paths: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    validation_steps: tuple[str, ...] = ()
    token_estimate: int | None = None
    usable_input_tokens: int | None = None
    status: str = "pending"
    source_task_id: str | None = None
    superseded_by: tuple[str, ...] = ()
    history: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["depends_on"] = list(self.depends_on)
        data["requirement_ids"] = list(self.requirement_ids)
        data["required_context"] = list(self.required_context)
        data["writable_paths"] = list(self.writable_paths)
        data["expected_outputs"] = list(self.expected_outputs)
        data["validation_steps"] = list(self.validation_steps)
        data["superseded_by"] = list(self.superseded_by)
        data["history"] = list(self.history)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskSnapshot":
        return cls(
            task_id=str(data.get("task_id", "")),
            title=str(data.get("title", "")),
            role=str(data.get("role", "")),
            depends_on=tuple(str(item) for item in data.get("depends_on", []) or []),
            requirement_ids=tuple(str(item) for item in data.get("requirement_ids", []) or []),
            required_context=tuple(str(item) for item in data.get("required_context", []) or []),
            writable_paths=tuple(str(item) for item in data.get("writable_paths", []) or []),
            expected_outputs=tuple(str(item) for item in data.get("expected_outputs", []) or []),
            validation_steps=tuple(str(item) for item in data.get("validation_steps", []) or []),
            token_estimate=maybe_int(data.get("token_estimate")),
            usable_input_tokens=maybe_int(data.get("usable_input_tokens")),
            status=str(data.get("status", "pending")),
            source_task_id=maybe_text(data.get("source_task_id")),
            superseded_by=tuple(str(item) for item in data.get("superseded_by", []) or []),
            history=tuple(str(item) for item in data.get("history", []) or []),
        )


@dataclass(frozen=True)
class TaskChange:
    task_id: str
    change_type: str
    prior_status: str
    new_status: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskChange":
        return cls(
            task_id=str(data.get("task_id", "")),
            change_type=str(data.get("change_type", "")),
            prior_status=str(data.get("prior_status", "")),
            new_status=str(data.get("new_status", "")),
            summary=str(data.get("summary", "")),
        )


@dataclass(frozen=True)
class DependencyChange:
    task_id: str
    prior_dependencies: tuple[str, ...] = ()
    new_dependencies: tuple[str, ...] = ()
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["prior_dependencies"] = list(self.prior_dependencies)
        data["new_dependencies"] = list(self.new_dependencies)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DependencyChange":
        return cls(
            task_id=str(data.get("task_id", "")),
            prior_dependencies=tuple(str(item) for item in data.get("prior_dependencies", []) or []),
            new_dependencies=tuple(str(item) for item in data.get("new_dependencies", []) or []),
            summary=str(data.get("summary", "")),
        )


@dataclass(frozen=True)
class RequirementMapping:
    requirement_id: str
    task_ids: tuple[str, ...] = ()
    source: str = "application"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["task_ids"] = list(self.task_ids)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequirementMapping":
        return cls(
            requirement_id=str(data.get("requirement_id", "")),
            task_ids=tuple(str(item) for item in data.get("task_ids", []) or []),
            source=str(data.get("source", "application")),
        )


@dataclass(frozen=True)
class RollbackMetadata:
    prior_revision_id: str
    prior_revision_checksum: str
    rollback_reason: str
    created_at: str
    application_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RollbackMetadata":
        return cls(
            prior_revision_id=str(data.get("prior_revision_id", "")),
            prior_revision_checksum=str(data.get("prior_revision_checksum", "")),
            rollback_reason=str(data.get("rollback_reason", "")),
            created_at=str(data.get("created_at", "")),
            application_id=str(data.get("application_id", "")),
        )


@dataclass(frozen=True)
class ExecutionLease:
    schema_version: int
    lease_id: str
    task_id: str
    execution_attempt_id: str
    runtime_revision_id: str
    runtime_revision_checksum: str
    local_model: str
    writable_paths: tuple[str, ...]
    start_timestamp: str
    lease_state: str = "active"
    expiry_timestamp: str | None = None
    heartbeat_timestamp: str | None = None
    completion_checksum: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["writable_paths"] = list(self.writable_paths)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionLease":
        return cls(
            schema_version=int(data.get("schema_version", LEASE_SCHEMA_VERSION)),
            lease_id=str(data.get("lease_id", "")),
            task_id=str(data.get("task_id", "")),
            execution_attempt_id=str(data.get("execution_attempt_id", "")),
            runtime_revision_id=str(data.get("runtime_revision_id", "")),
            runtime_revision_checksum=str(data.get("runtime_revision_checksum", "")),
            local_model=str(data.get("local_model", "")),
            writable_paths=tuple(str(item) for item in data.get("writable_paths", []) or []),
            start_timestamp=str(data.get("start_timestamp", "")),
            lease_state=str(data.get("lease_state", "active")),
            expiry_timestamp=maybe_text(data.get("expiry_timestamp")),
            heartbeat_timestamp=maybe_text(data.get("heartbeat_timestamp")),
            completion_checksum=maybe_text(data.get("completion_checksum")),
        )


@dataclass(frozen=True)
class TransactionRecord:
    schema_version: int
    transaction_id: str
    application_id: str
    source_revision_id: str
    source_revision_checksum: str
    proposed_revision_id: str
    proposed_revision_checksum: str
    expected_active_pointer: str
    phase: str
    artifact_paths: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    recovery_action: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["artifact_paths"] = list(self.artifact_paths)
        data["details"] = dict(self.details)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransactionRecord":
        return cls(
            schema_version=int(data.get("schema_version", TRANSACTION_SCHEMA_VERSION)),
            transaction_id=str(data.get("transaction_id", "")),
            application_id=str(data.get("application_id", "")),
            source_revision_id=str(data.get("source_revision_id", "")),
            source_revision_checksum=str(data.get("source_revision_checksum", "")),
            proposed_revision_id=str(data.get("proposed_revision_id", "")),
            proposed_revision_checksum=str(data.get("proposed_revision_checksum", "")),
            expected_active_pointer=str(data.get("expected_active_pointer", "")),
            phase=str(data.get("phase", "")),
            artifact_paths=tuple(str(item) for item in data.get("artifact_paths", []) or []),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            recovery_action=str(data.get("recovery_action", "")),
            details=dict(data.get("details", {}) or {}),
        )


@dataclass(frozen=True)
class ApplicationAuditEvent:
    event_id: str
    event_type: str
    application_id: str
    request_id: str
    prior_state: str
    new_state: str
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["details"] = dict(self.details)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApplicationAuditEvent":
        return cls(
            event_id=str(data.get("event_id", "")),
            event_type=str(data.get("event_type", "")),
            application_id=str(data.get("application_id", "")),
            request_id=str(data.get("request_id", "")),
            prior_state=str(data.get("prior_state", "")),
            new_state=str(data.get("new_state", "")),
            timestamp=str(data.get("timestamp", "")),
            details=dict(data.get("details", {}) or {}),
        )


@dataclass(frozen=True)
class ApplicationSource:
    request_type: str
    response_classification: str
    source_task_id: str
    source_plan_revision: str


@dataclass(frozen=True)
class ApplicationOperation:
    operation_type: ApplicationOperationType
    affected_task_ids: tuple[str, ...]
    proposed_task_ids: tuple[str, ...]
    preserved_requirement_ids: tuple[str, ...]
    dependency_changes: tuple[DependencyChange, ...]
    writable_paths: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    validation_steps: tuple[str, ...]


@dataclass(frozen=True)
class ApplicationSafety:
    canonical_blueprint_modified: bool
    writable_paths_expanded: bool
    requirements_removed: bool
    external_services_added: bool
    network_access_added: bool
    deployment_added: bool


@dataclass(frozen=True)
class ResumeEligibility:
    eligible: bool
    resume_from_task_ids: tuple[str, ...]
    blocked_dependents: tuple[str, ...]
    previously_completed_tasks: tuple[str, ...]
    reasons: tuple[str, ...] = ()
    manual_holds: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplicationRecord:
    schema_version: int
    application_id: str
    request_id: str
    request_checksum: str
    response_checksum: str
    approval_checksum: str | None
    status: ApplicationState
    created_at: str
    source: ApplicationSource
    application: ApplicationOperation
    safety: ApplicationSafety
    resume: ResumeEligibility
    plan_checksum: str
    revision_id: str | None = None
    revision_checksum: str | None = None
    active_revision_id: str | None = None
    rollback_available: bool = False
    notes: tuple[str, ...] = ()
    audit_event_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = asdict(self.source)
        data["application"] = {
            **asdict(self.application),
            "dependency_changes": [change.to_dict() for change in self.application.dependency_changes],
        }
        data["safety"] = asdict(self.safety)
        data["resume"] = asdict(self.resume)
        data["notes"] = list(self.notes)
        data["audit_event_ids"] = list(self.audit_event_ids)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApplicationRecord":
        application = data.get("application", {}) if isinstance(data.get("application"), dict) else {}
        return cls(
            schema_version=int(data.get("schema_version", APPLICATION_SCHEMA_VERSION)),
            application_id=str(data.get("application_id", "")),
            request_id=str(data.get("request_id", "")),
            request_checksum=str(data.get("request_checksum", "")),
            response_checksum=str(data.get("response_checksum", "")),
            approval_checksum=maybe_text(data.get("approval_checksum")),
            status=str(data.get("status", "application_planned")),
            created_at=str(data.get("created_at", "")),
            source=ApplicationSource(
                request_type=str((data.get("source") or {}).get("request_type", "")),
                response_classification=str((data.get("source") or {}).get("response_classification", "")),
                source_task_id=str((data.get("source") or {}).get("source_task_id", "")),
                source_plan_revision=str((data.get("source") or {}).get("source_plan_revision", "")),
            ),
            application=ApplicationOperation(
                operation_type=str(application.get("operation_type", "")),
                affected_task_ids=tuple(str(item) for item in application.get("affected_task_ids", []) or []),
                proposed_task_ids=tuple(str(item) for item in application.get("proposed_task_ids", []) or []),
                preserved_requirement_ids=tuple(
                    str(item) for item in application.get("preserved_requirement_ids", []) or []
                ),
                dependency_changes=tuple(
                    DependencyChange.from_dict(item)
                    for item in application.get("dependency_changes", []) or []
                    if isinstance(item, dict)
                ),
                writable_paths=tuple(str(item) for item in application.get("writable_paths", []) or []),
                expected_outputs=tuple(str(item) for item in application.get("expected_outputs", []) or []),
                validation_steps=tuple(str(item) for item in application.get("validation_steps", []) or []),
            ),
            safety=ApplicationSafety(**dict(data.get("safety", {}) or {})),
            resume=ResumeEligibility(
                eligible=bool((data.get("resume") or {}).get("eligible", False)),
                resume_from_task_ids=tuple(str(item) for item in (data.get("resume") or {}).get("resume_from_task_ids", []) or []),
                blocked_dependents=tuple(str(item) for item in (data.get("resume") or {}).get("blocked_dependents", []) or []),
                previously_completed_tasks=tuple(
                    str(item) for item in (data.get("resume") or {}).get("previously_completed_tasks", []) or []
                ),
                reasons=tuple(str(item) for item in (data.get("resume") or {}).get("reasons", []) or []),
                manual_holds=tuple(str(item) for item in (data.get("resume") or {}).get("manual_holds", []) or []),
            ),
            plan_checksum=str(data.get("plan_checksum", "")),
            revision_id=maybe_text(data.get("revision_id")),
            revision_checksum=maybe_text(data.get("revision_checksum")),
            active_revision_id=maybe_text(data.get("active_revision_id")),
            rollback_available=bool(data.get("rollback_available", False)),
            notes=tuple(str(item) for item in data.get("notes", []) or []),
            audit_event_ids=tuple(str(item) for item in data.get("audit_event_ids", []) or []),
        )


@dataclass(frozen=True)
class ApplicationPlan:
    schema_version: int
    application_id: str
    request_id: str
    request_checksum: str
    response_checksum: str
    approval_checksum: str | None
    source_revision_id: str
    source_revision_checksum: str
    proposed_revision_id: str
    operation_type: ApplicationOperationType
    source_task_snapshot: TaskSnapshot
    proposed_tasks: tuple[TaskSnapshot, ...]
    requirement_mapping: tuple[RequirementMapping, ...]
    dependency_changes: tuple[DependencyChange, ...]
    writable_path_diff: tuple[str, ...]
    context_budget_validation: dict[str, Any]
    expected_outputs: tuple[str, ...]
    validation_steps: tuple[str, ...]
    affected_completed_tasks: tuple[str, ...]
    affected_pending_tasks: tuple[str, ...]
    resume_candidates: tuple[str, ...]
    rollback_target: str
    preconditions: tuple[str, ...]
    predicted_side_effects: tuple[str, ...]
    plan_checksum: str
    created_at: str
    application_record_path: Path | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_task_snapshot"] = self.source_task_snapshot.to_dict()
        data["proposed_tasks"] = [task.to_dict() for task in self.proposed_tasks]
        data["requirement_mapping"] = [mapping.to_dict() for mapping in self.requirement_mapping]
        data["dependency_changes"] = [change.to_dict() for change in self.dependency_changes]
        data["writable_path_diff"] = list(self.writable_path_diff)
        data["expected_outputs"] = list(self.expected_outputs)
        data["validation_steps"] = list(self.validation_steps)
        data["affected_completed_tasks"] = list(self.affected_completed_tasks)
        data["affected_pending_tasks"] = list(self.affected_pending_tasks)
        data["resume_candidates"] = list(self.resume_candidates)
        data["preconditions"] = list(self.preconditions)
        data["predicted_side_effects"] = list(self.predicted_side_effects)
        data["application_record_path"] = str(self.application_record_path) if self.application_record_path else ""
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApplicationPlan":
        return cls(
            schema_version=int(data.get("schema_version", APPLICATION_SCHEMA_VERSION)),
            application_id=str(data.get("application_id", "")),
            request_id=str(data.get("request_id", "")),
            request_checksum=str(data.get("request_checksum", "")),
            response_checksum=str(data.get("response_checksum", "")),
            approval_checksum=maybe_text(data.get("approval_checksum")),
            source_revision_id=str(data.get("source_revision_id", "")),
            source_revision_checksum=str(data.get("source_revision_checksum", "")),
            proposed_revision_id=str(data.get("proposed_revision_id", "")),
            operation_type=str(data.get("operation_type", "")),
            source_task_snapshot=TaskSnapshot.from_dict(dict(data.get("source_task_snapshot", {}) or {})),
            proposed_tasks=tuple(
                TaskSnapshot.from_dict(item)
                for item in data.get("proposed_tasks", []) or []
                if isinstance(item, dict)
            ),
            requirement_mapping=tuple(
                RequirementMapping.from_dict(item)
                for item in data.get("requirement_mapping", []) or []
                if isinstance(item, dict)
            ),
            dependency_changes=tuple(
                DependencyChange.from_dict(item)
                for item in data.get("dependency_changes", []) or []
                if isinstance(item, dict)
            ),
            writable_path_diff=tuple(str(item) for item in data.get("writable_path_diff", []) or []),
            context_budget_validation=dict(data.get("context_budget_validation", {}) or {}),
            expected_outputs=tuple(str(item) for item in data.get("expected_outputs", []) or []),
            validation_steps=tuple(str(item) for item in data.get("validation_steps", []) or []),
            affected_completed_tasks=tuple(str(item) for item in data.get("affected_completed_tasks", []) or []),
            affected_pending_tasks=tuple(str(item) for item in data.get("affected_pending_tasks", []) or []),
            resume_candidates=tuple(str(item) for item in data.get("resume_candidates", []) or []),
            rollback_target=str(data.get("rollback_target", "")),
            preconditions=tuple(str(item) for item in data.get("preconditions", []) or []),
            predicted_side_effects=tuple(str(item) for item in data.get("predicted_side_effects", []) or []),
            plan_checksum=str(data.get("plan_checksum", "")),
            created_at=str(data.get("created_at", "")),
            application_record_path=Path(str(data["application_record_path"])) if data.get("application_record_path") else None,
            dry_run=bool(data.get("dry_run", False)),
        )


@dataclass(frozen=True)
class RuntimePlanRevision:
    schema_version: int
    revision_id: str
    parent_revision_id: str | None
    application_id: str
    created_at: str
    task_graph: tuple[TaskSnapshot, ...]
    task_statuses: dict[str, str]
    requirement_mappings: tuple[RequirementMapping, ...]
    dependency_mappings: tuple[DependencyChange, ...]
    graph_checksum: str
    revision_checksum: str
    change_summary: tuple[str, ...]
    rollback_metadata: RollbackMetadata
    audit_event_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["task_graph"] = [task.to_dict() for task in self.task_graph]
        data["requirement_mappings"] = [mapping.to_dict() for mapping in self.requirement_mappings]
        data["dependency_mappings"] = [change.to_dict() for change in self.dependency_mappings]
        data["rollback_metadata"] = self.rollback_metadata.to_dict()
        data["change_summary"] = list(self.change_summary)
        data["audit_event_ids"] = list(self.audit_event_ids)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimePlanRevision":
        return cls(
            schema_version=int(data.get("schema_version", REVISION_SCHEMA_VERSION)),
            revision_id=str(data.get("revision_id", "")),
            parent_revision_id=maybe_text(data.get("parent_revision_id")),
            application_id=str(data.get("application_id", "")),
            created_at=str(data.get("created_at", "")),
            task_graph=tuple(
                TaskSnapshot.from_dict(item)
                for item in data.get("task_graph", []) or []
                if isinstance(item, dict)
            ),
            task_statuses={str(key): str(value) for key, value in dict(data.get("task_statuses", {}) or {}).items()},
            requirement_mappings=tuple(
                RequirementMapping.from_dict(item)
                for item in data.get("requirement_mappings", []) or []
                if isinstance(item, dict)
            ),
            dependency_mappings=tuple(
                DependencyChange.from_dict(item)
                for item in data.get("dependency_mappings", []) or []
                if isinstance(item, dict)
            ),
            graph_checksum=str(data.get("graph_checksum", "")),
            revision_checksum=str(data.get("revision_checksum", "")),
            change_summary=tuple(str(item) for item in data.get("change_summary", []) or []),
            rollback_metadata=RollbackMetadata.from_dict(dict(data.get("rollback_metadata", {}) or {})),
            audit_event_ids=tuple(str(item) for item in data.get("audit_event_ids", []) or []),
        )


@dataclass(frozen=True)
class ActiveRevisionPointer:
    schema_version: int
    active_revision_id: str
    active_revision_checksum: str
    previous_revision_id: str | None
    update_timestamp: str
    application_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActiveRevisionPointer":
        return cls(
            schema_version=int(data.get("schema_version", ACTIVE_POINTER_SCHEMA_VERSION)),
            active_revision_id=str(data.get("active_revision_id", "")),
            active_revision_checksum=str(data.get("active_revision_checksum", "")),
            previous_revision_id=maybe_text(data.get("previous_revision_id")),
            update_timestamp=str(data.get("update_timestamp", "")),
            application_id=str(data.get("application_id", "")),
        )


@dataclass(frozen=True)
class RecoveryResult:
    project_path: Path
    findings: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    reconciled: bool
    active_pointer: ActiveRevisionPointer | None = None
    application_id: str | None = None
    transaction_id: str | None = None


@dataclass(frozen=True)
class ResumeResult:
    project_path: Path
    application_id: str
    revision_id: str
    revision_checksum: str
    task_ids: tuple[str, ...]
    lease_ids: tuple[str, ...]
    status: str
    reasons: tuple[str, ...] = ()
    resume_state_path: Path | None = None
    execution_status_path: Path | None = None
    execution_report_path: Path | None = None


@dataclass(frozen=True)
class ApplicationStatusResult:
    project_path: Path
    applications: tuple[ApplicationRecord, ...]
    active_pointer: ActiveRevisionPointer | None
    counts_by_state: dict[str, int]


def maybe_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def maybe_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None
