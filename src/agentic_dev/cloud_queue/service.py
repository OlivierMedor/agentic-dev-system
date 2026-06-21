from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agentic_dev.cloud_queue.approvals import record_approval
from agentic_dev.cloud_queue.classification import APPROVAL_REQUIRED, CLASSIFIED_SAFE
from agentic_dev.cloud_queue.export import export_requests
from agentic_dev.cloud_queue.importers import import_response_file
from agentic_dev.cloud_queue.models import (
    CloudQueueAuditEvent,
    CloudQueueExportResult,
    CloudQueueImportResult,
    CloudQueueRequest,
    CloudQueueStatusResult,
)
from agentic_dev.cloud_queue.persistence import (
    append_audit_event,
    ensure_cloud_queue_dirs,
    event_id_for,
    load_requests,
    move_request,
    now_iso,
    request_state_path,
    save_request,
)
from agentic_dev.cloud_queue.state_machine import is_terminal_state, validate_transition
from agentic_dev.cloud_queue.validation import normalize_request_id, normalize_relative_path, normalize_writable_paths


REQUEST_ID_PREFIX = "CQ"
DEFAULT_BLOCKER_TYPE = "local_blocker"
READY_EXPORT_STATES = {"ready"}
EXPORTABLE_STATES = {"ready"}


@dataclass(frozen=True)
class CloudQueueCreateResult:
    request: CloudQueueRequest
    request_path: Path
    created_at: str
    audit_event_id: str


@dataclass(frozen=True)
class CloudQueueShowResult:
    request: CloudQueueRequest
    request_path: Path


@dataclass(frozen=True)
class CloudQueueListResult:
    requests: list[CloudQueueRequest]
    counts_by_state: dict[str, int]


@dataclass(frozen=True)
class CloudQueueDecisionResult:
    request: CloudQueueRequest
    request_path: Path
    audit_event_id: str
    decision: str
    note: str


def create_cloud_queue_request(
    project_path: Path,
    story: str,
    title: str,
    details: str,
    blocker_type: str = DEFAULT_BLOCKER_TYPE,
    requirements: list[str] | None = None,
    writable_paths: list[str] | None = None,
    dependencies: list[str] | None = None,
    context_files: list[str] | None = None,
    notes: list[str] | None = None,
    source_task_id: str = "",
    source_plan_revision: str = "",
    request_id_factory: Callable[[], str] | None = None,
    batch_id_factory: Callable[[], str] | None = None,
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueCreateResult:
    ensure_cloud_queue_dirs(project_path)
    request_id = normalize_request_id(
        request_id_factory() if request_id_factory else generate_request_id(project_path),
    )
    batch_id = batch_id_factory() if batch_id_factory else f"batch-{now_iso().replace(':', '').replace('+', '-')}"
    request = CloudQueueRequest(
        request_id=request_id,
        story=story,
        title=title,
        blocker_type=blocker_type,
        details=details,
        state="ready",
        prior_state="new",
        batch_id=batch_id,
        request_count=1,
        requirements=list(requirements or []),
        writable_paths=normalize_writable_paths(list(writable_paths or [])),
        dependencies=[normalize_request_id(item) for item in (dependencies or [])],
        context_files=[normalize_relative_path(item) for item in (context_files or [])],
        created_at=now_iso(),
        updated_at=now_iso(),
        source_task_id=source_task_id,
        source_plan_revision=source_plan_revision,
        notes=list(notes or []),
        next_action="Ready to export.",
    )
    save_request(project_path, request, allow_overwrite=False)
    event = CloudQueueAuditEvent(
        event_id="",
        event_type="create",
        request_id=request.request_id,
        batch_id=batch_id,
        prior_state="new",
        new_state="ready",
        packet_checksum="",
        request_count=1,
        timestamp=now_iso(),
        details={
            "story": story,
            "blocker_type": blocker_type,
            "requirements": list(request.requirements),
            "writable_paths": list(request.writable_paths),
            "dependencies": list(request.dependencies),
            "context_files": list(request.context_files),
        },
    )
    event = CloudQueueAuditEvent(**{**event.to_dict(), "event_id": event_id_for(event, event_id_factory)})
    append_audit_event(project_path, event)
    request = CloudQueueRequest.from_dict(
        {
            **request.to_dict(),
            "audit_event_ids": [event.event_id],
        },
    )
    save_request(project_path, request, allow_overwrite=True)
    return CloudQueueCreateResult(
        request=request,
        request_path=request_state_path(project_path, request.request_id, request.state),
        created_at=request.created_at,
        audit_event_id=event.event_id,
    )


def list_cloud_queue_requests(
    project_path: Path,
    state: str | None = None,
) -> CloudQueueListResult:
    loaded = [request for _path, request in load_requests(project_path)]
    if state:
        loaded = [request for request in loaded if request.state == state]
    counts = Counter(request.state for request in loaded)
    return CloudQueueListResult(requests=loaded, counts_by_state=dict(counts))


def show_cloud_queue_request(project_path: Path, request_id: str) -> CloudQueueShowResult:
    request, path = locate_request(project_path, request_id)
    return CloudQueueShowResult(request=request, request_path=path)


def cloud_queue_status(project_path: Path) -> CloudQueueStatusResult:
    requests = [request for _path, request in load_requests(project_path)]
    counts = Counter(request.state for request in requests)
    terminal_count = sum(1 for request in requests if is_terminal_state(request.state))
    return CloudQueueStatusResult(
        request_count=len(requests),
        counts_by_state=dict(counts),
        requests=requests,
        terminal_count=terminal_count,
    )


def export_cloud_queue_request(
    project_path: Path,
    request_id: str | None = None,
    all_ready: bool = False,
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueExportResult:
    requests = [request for _path, request in load_requests(project_path)]
    if request_id is not None:
        request, _path = locate_request(project_path, request_id)
        if request.state not in EXPORTABLE_STATES or not dependencies_resolved(project_path, request):
            raise ValueError("Request is not ready for export.")
        requests = [request]
    elif all_ready:
        requests = [request for request in requests if request.state in EXPORTABLE_STATES and dependencies_resolved(project_path, request)]
    else:
        raise ValueError("Either request_id or all_ready must be selected for export.")

    if not requests:
        raise ValueError("No ready requests were available for export.")

    batch_id = requests[0].batch_id or f"batch-{now_iso().replace(':', '').replace('+', '-')}"
    return export_requests(project_path, requests, batch_id=batch_id, event_id_factory=event_id_factory)


def import_cloud_queue_response(
    project_path: Path,
    file_path: Path,
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueImportResult:
    return import_response_file(project_path, file_path, event_id_factory=event_id_factory)


def approve_cloud_queue_request(
    project_path: Path,
    request_id: str,
    normalized_response_checksum_value: str | None = None,
    operator_note: str = "",
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueDecisionResult:
    request, request_path = locate_request(project_path, request_id)
    if request.state != APPROVAL_REQUIRED:
        raise ValueError("Approval is only allowed from approval_required.")

    expected_checksum = request.approval_checksum or request.normalized_response_checksum
    actual_checksum = normalized_response_checksum_value or expected_checksum
    if expected_checksum and actual_checksum and expected_checksum != actual_checksum:
        raise ValueError("Approval checksum does not match the normalized response checksum.")

    validate_transition(request.state, "approved")
    updated = CloudQueueRequest.from_dict(
        {
            **request.to_dict(),
            "prior_state": request.state,
            "state": "approved",
            "updated_at": now_iso(),
            "next_action": "Approved response is recorded but not applied automatically.",
            "classification": CLASSIFIED_SAFE,
        },
    )
    move_request(project_path, updated, "approved", allow_overwrite=True)
    record_approval(
        project_path,
        updated,
        normalized_response_checksum=actual_checksum or expected_checksum,
        approved=True,
        operator_note=operator_note,
        recorded_at=now_iso(),
    )
    event = CloudQueueAuditEvent(
        event_id="",
        event_type="approve",
        request_id=request_id,
        batch_id=request.batch_id,
        prior_state=request.state,
        new_state="approved",
        packet_checksum=request.packet_checksum,
        request_count=request.request_count,
        timestamp=now_iso(),
        details={"normalized_response_checksum": actual_checksum or expected_checksum, "operator_note": operator_note},
    )
    event = CloudQueueAuditEvent(**{**event.to_dict(), "event_id": event_id_for(event, event_id_factory)})
    append_audit_event(project_path, event)
    return CloudQueueDecisionResult(
        request=updated,
        request_path=request_state_path(project_path, request_id, "approved"),
        audit_event_id=event.event_id,
        decision="approved",
        note=operator_note,
    )


def reject_cloud_queue_request(
    project_path: Path,
    request_id: str,
    operator_note: str = "",
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueDecisionResult:
    request, _path = locate_request(project_path, request_id)
    if request.state in {"approved", "rejected", "canceled", "failed"}:
        raise ValueError(f"Request is already terminal: {request.state}")
    validate_transition(request.state, "rejected")
    updated = CloudQueueRequest.from_dict(
        {
            **request.to_dict(),
            "prior_state": request.state,
            "state": "rejected",
            "updated_at": now_iso(),
            "next_action": "Rejected by operator.",
        },
    )
    move_request(project_path, updated, "rejected", allow_overwrite=True)
    event = CloudQueueAuditEvent(
        event_id="",
        event_type="reject",
        request_id=request_id,
        batch_id=request.batch_id,
        prior_state=request.state,
        new_state="rejected",
        packet_checksum=request.packet_checksum,
        request_count=request.request_count,
        timestamp=now_iso(),
        details={"rejection_reason": operator_note},
    )
    event = CloudQueueAuditEvent(**{**event.to_dict(), "event_id": event_id_for(event, event_id_factory)})
    append_audit_event(project_path, event)
    return CloudQueueDecisionResult(
        request=updated,
        request_path=request_state_path(project_path, request_id, "rejected"),
        audit_event_id=event.event_id,
        decision="rejected",
        note=operator_note,
    )


def cancel_cloud_queue_request(
    project_path: Path,
    request_id: str,
    reason: str = "",
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueDecisionResult:
    request, _path = locate_request(project_path, request_id)
    if is_terminal_state(request.state):
        raise ValueError(f"Request is already terminal: {request.state}")
    validate_transition(request.state, "canceled")
    updated = CloudQueueRequest.from_dict(
        {
            **request.to_dict(),
            "prior_state": request.state,
            "state": "canceled",
            "updated_at": now_iso(),
            "next_action": "Canceled by operator.",
        },
    )
    move_request(project_path, updated, "canceled", allow_overwrite=True)
    event = CloudQueueAuditEvent(
        event_id="",
        event_type="cancel",
        request_id=request_id,
        batch_id=request.batch_id,
        prior_state=request.state,
        new_state="canceled",
        packet_checksum=request.packet_checksum,
        request_count=request.request_count,
        timestamp=now_iso(),
        details={"reason": reason},
    )
    event = CloudQueueAuditEvent(**{**event.to_dict(), "event_id": event_id_for(event, event_id_factory)})
    append_audit_event(project_path, event)
    return CloudQueueDecisionResult(
        request=updated,
        request_path=request_state_path(project_path, request_id, "canceled"),
        audit_event_id=event.event_id,
        decision="canceled",
        note=reason,
    )


def fail_cloud_queue_request(
    project_path: Path,
    request_id: str,
    reason: str,
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueDecisionResult:
    request, _path = locate_request(project_path, request_id)
    if is_terminal_state(request.state):
        raise ValueError(f"Request is already terminal: {request.state}")
    validate_transition(request.state, "failed")
    updated = CloudQueueRequest.from_dict(
        {
            **request.to_dict(),
            "prior_state": request.state,
            "state": "failed",
            "updated_at": now_iso(),
            "next_action": reason,
        },
    )
    move_request(project_path, updated, "failed", allow_overwrite=True)
    event = CloudQueueAuditEvent(
        event_id="",
        event_type="failure",
        request_id=request_id,
        batch_id=request.batch_id,
        prior_state=request.state,
        new_state="failed",
        packet_checksum=request.packet_checksum,
        request_count=request.request_count,
        timestamp=now_iso(),
        details={"reason": reason},
    )
    event = CloudQueueAuditEvent(**{**event.to_dict(), "event_id": event_id_for(event, event_id_factory)})
    append_audit_event(project_path, event)
    return CloudQueueDecisionResult(
        request=updated,
        request_path=request_state_path(project_path, request_id, "failed"),
        audit_event_id=event.event_id,
        decision="failed",
        note=reason,
    )


def classify_imported_response(project_path: Path, request_id: str) -> CloudQueueRequest:
    request, _path = locate_request(project_path, request_id)
    return request


def dependencies_resolved(project_path: Path, request: CloudQueueRequest) -> bool:
    if not request.dependencies:
        return True
    for dependency_id in request.dependencies:
        try:
            dependency, _ = locate_request(project_path, dependency_id)
        except FileNotFoundError:
            return False
        if dependency.state not in {"validated_safe", "approved"}:
            return False
    return True


def locate_request(project_path: Path, request_id: str) -> tuple[CloudQueueRequest, Path]:
    normalized = normalize_request_id(request_id)
    for path, request in load_requests(project_path):
        if request.request_id == normalized:
            return request, path
    raise FileNotFoundError(f"Cloud queue request was not found: {request_id}")


def generate_request_id(project_path: Path) -> str:
    existing = [request.request_id for _path, request in load_requests(project_path)]
    counter = len(existing) + 1
    return f"{REQUEST_ID_PREFIX}-{now_iso().replace(':', '').replace('+', '-')}-{counter:03d}"
