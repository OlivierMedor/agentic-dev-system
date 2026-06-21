from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from agentic_dev.cloud_application.models import (
    ActiveRevisionPointer,
    ApplicationPlan,
    SUPPORTED_APPLICATION_OPERATIONS,
    TaskSnapshot,
)
from agentic_dev.cloud_queue.classification import APPROVAL_REQUIRED, CLASSIFIED_SAFE, VALIDATED_SAFE
from agentic_dev.cloud_queue.models import CloudQueueRequest
from agentic_dev.cloud_queue.persistence import checksum_text
from agentic_dev.cloud_queue.validation import normalize_relative_path

VALIDATED_SAFE_SOURCE = "validated_safe"
APPROVAL_REQUIRED_SOURCE = "approval_required"
REQUEST_STATUS_ELIGIBLE = {"validated_safe", "approved"}
REQUEST_STATUS_REJECTED = {"validation_failed", "rejected", "cancelled", "failed", "canceled"}
SENSITIVE_PATH_TOKENS = {
    ".git",
    ".env",
    "credentials",
    "secrets",
    "private",
}
LOCAL_CONTEXT_LIMIT = 120000


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    request_id: str
    source_kind: str
    reason: str
    request_checksum: str
    response_checksum: str
    approval_checksum: str | None
    eligible_for_approval: bool = False


def canonical_request_checksum(request: CloudQueueRequest) -> str:
    payload = {
        "request_id": request.request_id,
        "story": request.story,
        "title": request.title,
        "blocker_type": request.blocker_type,
        "details": request.details,
        "state": request.state,
        "prior_state": request.prior_state,
        "batch_id": request.batch_id,
        "request_count": request.request_count,
        "request_schema_version": request.request_schema_version,
        "response_schema_version": request.response_schema_version,
        "requirements": list(request.requirements),
        "writable_paths": list(request.writable_paths),
        "dependencies": list(request.dependencies),
        "context_files": list(request.context_files),
        "packet_checksum": request.packet_checksum,
        "normalized_response_checksum": request.normalized_response_checksum,
        "approval_checksum": request.approval_checksum,
        "raw_response_checksum": request.raw_response_checksum,
        "classification": request.classification,
        "next_action": request.next_action,
    }
    return checksum_text(_yaml_dump(payload))


def canonical_response_checksum(request: CloudQueueRequest) -> str:
    return request.normalized_response_checksum or request.raw_response_checksum


def validate_eligibility(
    request: CloudQueueRequest,
    *,
    approval_record: dict[str, Any] | None = None,
) -> EligibilityResult:
    if request.state in REQUEST_STATUS_REJECTED:
        return EligibilityResult(
            eligible=False,
            request_id=request.request_id,
            source_kind=str(request.classification or "unknown"),
            reason=f"Request is not eligible in state {request.state}.",
            request_checksum=canonical_request_checksum(request),
            response_checksum=canonical_response_checksum(request),
            approval_checksum=request.approval_checksum or None,
        )

    request_checksum = canonical_request_checksum(request)
    response_checksum = canonical_response_checksum(request)
    approval_checksum = request.approval_checksum or None

    if request.state == VALIDATED_SAFE and request.classification in {CLASSIFIED_SAFE, VALIDATED_SAFE}:
        if not request.packet_checksum:
            return EligibilityResult(
                eligible=False,
                request_id=request.request_id,
                source_kind=VALIDATED_SAFE_SOURCE,
                reason="Validated-safe request does not have a request checksum.",
                request_checksum=request_checksum,
                response_checksum=response_checksum,
                approval_checksum=approval_checksum,
            )
        if not response_checksum:
            return EligibilityResult(
                eligible=False,
                request_id=request.request_id,
                source_kind=VALIDATED_SAFE_SOURCE,
                reason="Validated-safe request does not have a response checksum.",
                request_checksum=request_checksum,
                response_checksum=response_checksum,
                approval_checksum=approval_checksum,
            )
        return EligibilityResult(
            eligible=True,
            request_id=request.request_id,
            source_kind=VALIDATED_SAFE_SOURCE,
            reason="Validated-safe response is eligible.",
            request_checksum=request_checksum,
            response_checksum=response_checksum,
            approval_checksum=approval_checksum,
        )

    if request.state != "approved" and request.classification == APPROVAL_REQUIRED:
        return EligibilityResult(
            eligible=False,
            request_id=request.request_id,
            source_kind=APPROVAL_REQUIRED_SOURCE,
            reason="Approval-required response needs explicit approval before application.",
            request_checksum=request_checksum,
            response_checksum=response_checksum,
            approval_checksum=approval_checksum,
            eligible_for_approval=True,
        )

    if request.state == "approved":
        if approval_record is None:
            raise ValueError("Approval-required response is missing an approval record.")
        record_request_id = str(approval_record.get("request_id", ""))
        approved = bool(approval_record.get("approved", False))
        record_response_checksum = str(approval_record.get("normalized_response_checksum", ""))
        expected_response_checksum = approval_checksum or response_checksum
        if record_request_id != request.request_id:
            raise ValueError("Approval record does not match the request.")
        if not approved:
            raise ValueError("Approval record is not approved.")
        if record_response_checksum != expected_response_checksum:
            raise ValueError("Approval checksum does not match the normalized response checksum.")
        return EligibilityResult(
            eligible=True,
            request_id=request.request_id,
            source_kind=APPROVAL_REQUIRED_SOURCE,
            reason="Approved response is eligible.",
            request_checksum=request_checksum,
            response_checksum=response_checksum,
            approval_checksum=approval_checksum or record_response_checksum,
            eligible_for_approval=True,
        )

    raise ValueError(f"Request is not eligible for application in state {request.state}.")


def validate_application_state_boundaries(plan: ApplicationPlan) -> None:
    if plan.operation_type not in SUPPORTED_APPLICATION_OPERATIONS:
        raise ValueError(f"Unsupported application operation: {plan.operation_type}")
    if not plan.plan_checksum:
        raise ValueError("Application plan checksum is missing.")


def validate_writable_paths_exact(
    approved_paths: list[str],
    proposed_paths: list[str],
) -> list[str]:
    normalized_approved = [normalize_relative_path(path) for path in approved_paths]
    normalized_proposed = [normalize_relative_path(path) for path in proposed_paths]
    if sorted(normalized_approved) != sorted(normalized_proposed):
        if set(normalized_proposed) - set(normalized_approved):
            raise ValueError("Application expands writable paths beyond the approved scope.")
        raise ValueError("Application narrows writable paths without matching approval.")
    for path in normalized_proposed:
        parts = PurePosixPath(path).parts
        if not parts:
            raise ValueError("Writable path cannot be empty.")
        if any(token in path.lower() for token in SENSITIVE_PATH_TOKENS):
            raise ValueError(f"Writable path is unsafe: {path}")
        if path.startswith(("../", "./")) or "/../" in path:
            raise ValueError(f"Writable path traversal is not allowed: {path}")
        if path.startswith("/") or path.startswith("//") or ":" in path:
            raise ValueError(f"Absolute writable path is not allowed: {path}")
    return normalized_proposed


def validate_dependency_graph(tasks: list[TaskSnapshot]) -> None:
    task_ids = [task.task_id for task in tasks]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("Task IDs must be unique.")
    task_map = {task.task_id: task for task in tasks}
    for task in tasks:
        for dependency in task.depends_on:
            if dependency not in task_map:
                raise ValueError(f"Missing dependency: {dependency}")
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            raise ValueError(f"Dependency cycle detected: {task_id}")
        visiting.add(task_id)
        for dependency in task_map[task_id].depends_on:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in task_ids:
        visit(task_id)


def validate_context_budget(task: TaskSnapshot, limit: int = LOCAL_CONTEXT_LIMIT) -> None:
    estimate = task.token_estimate
    usable = task.usable_input_tokens or limit
    if estimate is None:
        raise ValueError(f"Missing context budget estimate for task {task.task_id}.")
    if task.usable_input_tokens is None:
        raise ValueError(f"Missing usable input budget for task {task.task_id}.")
    if estimate > usable:
        raise ValueError(f"Task {task.task_id} exceeds the local context limit.")
    if usable > limit:
        raise ValueError(f"Task {task.task_id} exceeds the configured local context limit.")


def validate_requirement_coverage(
    source_task: TaskSnapshot,
    proposed_tasks: list[TaskSnapshot],
    required_requirement_ids: list[str],
) -> None:
    proposed_requirement_ids = sorted({item for task in proposed_tasks for item in task.requirement_ids})
    missing = [requirement for requirement in required_requirement_ids if requirement not in proposed_requirement_ids]
    if missing:
        raise ValueError(f"Missing applicable requirements: {', '.join(missing)}")
    if source_task.requirement_ids and not set(source_task.requirement_ids).issubset(proposed_requirement_ids):
        raise ValueError("Source-task coverage was dropped.")


def validate_path_overlap(tasks: list[TaskSnapshot]) -> None:
    paths: list[str] = []
    for task in tasks:
        for path in task.writable_paths:
            normalized = normalize_relative_path(path)
            for existing in paths:
                if path_overlap(existing, normalized):
                    raise ValueError(f"Unsafe overlapping writes detected: {existing} and {normalized}")
            paths.append(normalized)


def path_overlap(left: str, right: str) -> bool:
    left_parts = PurePosixPath(left).parts
    right_parts = PurePosixPath(right).parts
    shortest = min(len(left_parts), len(right_parts))
    return left_parts[:shortest] == right_parts[:shortest]


def validate_requirement_drift(
    current_requirements: list[str],
    imported_requirements: list[str],
) -> None:
    if sorted(current_requirements) != sorted(imported_requirements):
        raise ValueError("Requirement drift detected since import.")


def validate_no_canonical_mutation(plan: ApplicationPlan) -> None:
    if not plan.source_task_snapshot.task_id:
        raise ValueError("Source task snapshot is missing a task ID.")


def validate_approval_scope(
    approval_record: dict[str, Any],
    proposed_paths: list[str],
    proposed_requirements: list[str],
) -> None:
    approved_paths = [normalize_relative_path(str(item)) for item in approval_record.get("approved_writable_paths", []) or []]
    approved_requirements = [str(item) for item in approval_record.get("approved_requirements", []) or []]
    if approved_paths and sorted(approved_paths) != sorted(proposed_paths):
        raise ValueError("Approved writable paths do not exactly match the proposed application.")
    if approved_requirements and sorted(approved_requirements) != sorted(proposed_requirements):
        raise ValueError("Approved scope does not exactly match the proposed application.")


def validate_active_pointer(pointer: ActiveRevisionPointer, expected_revision_id: str, expected_revision_checksum: str) -> None:
    if pointer.active_revision_id != expected_revision_id:
        raise ValueError("Active revision pointer does not match the expected revision.")
    if pointer.active_revision_checksum != expected_revision_checksum:
        raise ValueError("Active revision pointer checksum does not match the expected revision.")


def _yaml_dump(payload: Any) -> str:
    import yaml

    return yaml.safe_dump(payload, sort_keys=True)
