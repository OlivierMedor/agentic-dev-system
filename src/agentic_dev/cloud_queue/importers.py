from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from agentic_dev.cloud_queue.approvals import approval_checksum
from agentic_dev.cloud_queue.classification import (
    APPROVAL_REQUIRED,
    CLASSIFIED_SAFE,
    VALIDATED_FAILED,
    VALIDATED_SAFE,
    classify_response,
)
from agentic_dev.cloud_queue.imports import save_imported_response
from agentic_dev.cloud_queue.models import (
    CloudQueueAuditEvent,
    CloudQueueImportResult,
    CloudQueueRequest,
    CloudQueueResponse,
)
from agentic_dev.cloud_queue.persistence import (
    append_audit_event,
    checksum_bytes,
    checksum_text,
    event_id_for,
    ensure_cloud_queue_dirs,
    load_request,
    move_request,
    now_iso,
)
from agentic_dev.cloud_queue.state_machine import validate_transition
from agentic_dev.cloud_queue.validation import (
    ensure_json_or_yaml_text,
    load_json_mapping,
    load_mapping_text,
    validate_archive,
)


def import_response_file(
    project_path: Path,
    file_path: Path,
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueImportResult:
    ensure_cloud_queue_dirs(project_path)
    file_path = file_path.resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Import file does not exist: {file_path}")

    if file_path.suffix.lower() == ".zip":
        validate_archive(file_path)
        return import_response_bundle(project_path, file_path, event_id_factory=event_id_factory)

    raw_bytes = file_path.read_bytes()
    raw_text = ensure_json_or_yaml_text(raw_bytes)
    mapping = load_json_mapping(raw_text) if file_path.suffix.lower() == ".json" else load_mapping_text(raw_text)
    return import_single_response(
        project_path,
        response_data=mapping,
        raw_text=raw_text,
        source_file=file_path,
        event_id_factory=event_id_factory,
    )


def import_response_bundle(
    project_path: Path,
    bundle_path: Path,
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueImportResult:
    ensure_cloud_queue_dirs(project_path)
    imported_count = 0
    valid_count = 0
    invalid_count = 0
    skipped_count = 0
    request_ids: list[str] = []
    audit_event_ids: list[str] = []
    imported_paths: list[Path] = []
    failed_paths: list[Path] = []
    seen_request_ids: set[str] = set()

    with ZipFile(bundle_path) as archive:
        for member in sorted(archive.infolist(), key=lambda item: item.filename):
            if member.is_dir() or member.filename.endswith("manifest.yaml"):
                continue

            imported_count += 1
            raw_bytes = archive.read(member)
            try:
                raw_text = ensure_json_or_yaml_text(raw_bytes)
                if member.filename.lower().endswith(".json"):
                    payload = load_json_mapping(raw_text)
                else:
                    payload = load_mapping_text(raw_text)
                request_id = str(payload.get("request_id", "")).strip() or request_id_from_filename(member.filename)
                if request_id in seen_request_ids:
                    raise ValueError(f"Duplicate request ID within one bundle: {request_id}")
                seen_request_ids.add(request_id)
                single_result = import_single_response(
                    project_path,
                    response_data=payload,
                    raw_text=raw_text,
                    source_file=Path(member.filename),
                    event_id_factory=event_id_factory,
                )
                valid_count += single_result.valid_count
                invalid_count += single_result.invalid_count
                skipped_count += single_result.skipped_count
                request_ids.extend(single_result.request_ids)
                imported_paths.extend(single_result.imported_paths)
                failed_paths.extend(single_result.failed_paths)
                audit_event_ids.extend(single_result.audit_event_ids)
            except Exception:
                invalid_count += 1
                failed_paths.append(Path(member.filename))
                request_id = request_id_from_filename(member.filename)
                if request_id:
                    audit_event_ids.append(
                        append_failed_import_audit(
                            project_path,
                            request_id=request_id,
                            batch_id="",
                            packet_checksum=checksum_bytes(raw_bytes),
                            event_id_factory=event_id_factory,
                            reason="malformed bundle member",
                        ),
                    )

    return CloudQueueImportResult(
        imported_count=imported_count,
        valid_count=valid_count,
        invalid_count=invalid_count,
        skipped_count=skipped_count,
        request_ids=request_ids,
        audit_event_ids=audit_event_ids,
        imported_paths=imported_paths,
        failed_paths=failed_paths,
    )


def import_single_response(
    project_path: Path,
    response_data: dict[str, Any],
    raw_text: str,
    source_file: Path,
    event_id_factory: Callable[[], str] | None = None,
) -> CloudQueueImportResult:
    response = CloudQueueResponse.from_dict(response_data, source_file=source_file)
    request_id = response.request_id or request_id_from_filename(source_file.name)
    if not request_id:
        raise ValueError("Could not determine a request ID from the imported response.")

    request_path_candidates = list_request_paths(project_path, request_id)
    if not request_path_candidates:
        raise FileNotFoundError(f"Request not found for imported response: {request_id}")

    request_path = request_path_candidates[0]
    request = load_request(request_path)
    comparison = classify_response(request, response)
    normalized_checksum = checksum_text(json.dumps(response.normalized_response, sort_keys=True))
    approval_binding = approval_checksum(response.normalized_response)
    packet_checksum = response.checksum or checksum_text(raw_text)
    save_imported_response(project_path, response)

    imported_request = CloudQueueRequest.from_dict(
        {
            **request.to_dict(),
            "prior_state": request.state,
            "state": "imported",
            "source_task_id": str(response.claims.get("source_task_id", request.source_task_id) or request.source_task_id),
            "source_plan_revision": str(response.claims.get("source_plan_revision", request.source_plan_revision) or request.source_plan_revision),
            "normalized_response_checksum": normalized_checksum,
            "approval_checksum": approval_binding,
            "raw_response_checksum": checksum_text(raw_text),
            "packet_checksum": packet_checksum,
            "updated_at": now_iso(),
            "next_action": "Response imported and awaiting independent classification.",
        },
    )
    validate_transition(request.state, "imported")
    move_request(project_path, imported_request, "imported", allow_overwrite=True)

    import_event = CloudQueueAuditEvent(
        event_id="",
        event_type="import",
        request_id=request_id,
        batch_id=response.batch_id or request.batch_id,
        prior_state=request.state,
        new_state="imported",
        packet_checksum=packet_checksum,
        request_count=1,
        timestamp=now_iso(),
        details={
            "response_source": str(source_file),
            "invalid_count": 0,
        },
    )
    import_event = CloudQueueAuditEvent(
        **{**import_event.to_dict(), "event_id": event_id_for(import_event, event_id_factory)},
    )
    append_audit_event(project_path, import_event)

    if comparison.classification == CLASSIFIED_SAFE:
        final_state = VALIDATED_SAFE
    elif comparison.classification == APPROVAL_REQUIRED:
        final_state = APPROVAL_REQUIRED
    else:
        final_state = VALIDATED_FAILED

    validate_transition("imported", final_state)
    classified_request = CloudQueueRequest.from_dict(
        {
            **imported_request.to_dict(),
            "prior_state": "imported",
            "state": final_state,
            "classification": comparison.classification,
            "updated_at": now_iso(),
            "next_action": comparison.reason,
        },
    )
    move_request(project_path, classified_request, final_state, allow_overwrite=True)

    classify_event = CloudQueueAuditEvent(
        event_id="",
        event_type="classify",
        request_id=request_id,
        batch_id=response.batch_id or request.batch_id,
        prior_state="imported",
        new_state=final_state,
        packet_checksum=packet_checksum,
        request_count=1,
        timestamp=now_iso(),
        details={
            "classification": comparison.classification,
            "safe_to_apply": comparison.safe_to_apply,
            "approval_required": comparison.approval_required,
            "validation_failed": comparison.validation_failed,
            "response_source": str(source_file),
        },
    )
    classify_event = CloudQueueAuditEvent(
        **{**classify_event.to_dict(), "event_id": event_id_for(classify_event, event_id_factory)},
    )
    append_audit_event(project_path, classify_event)

    return CloudQueueImportResult(
        imported_count=1,
        valid_count=0 if comparison.validation_failed else 1,
        invalid_count=1 if comparison.validation_failed else 0,
        skipped_count=0,
        request_ids=[request_id],
        audit_event_ids=[import_event.event_id, classify_event.event_id],
        imported_paths=[source_file],
        failed_paths=[],
    )


def append_failed_import_audit(
    project_path: Path,
    request_id: str,
    batch_id: str,
    packet_checksum: str,
    event_id_factory: Callable[[], str] | None,
    reason: str,
) -> str:
    event = CloudQueueAuditEvent(
        event_id="",
        event_type="failed_import",
        request_id=request_id,
        batch_id=batch_id,
        prior_state="imported",
        new_state="failed",
        packet_checksum=packet_checksum,
        request_count=1,
        timestamp=now_iso(),
        details={"reason": reason},
    )
    event = CloudQueueAuditEvent(
        **{**event.to_dict(), "event_id": event_id_for(event, event_id_factory)},
    )
    append_audit_event(project_path, event)
    return event.event_id


def list_request_paths(project_path: Path, request_id: str) -> list[Path]:
    requests_root = ensure_cloud_queue_dirs(project_path).requests
    matches: list[Path] = []
    for state_dir in requests_root.iterdir():
        if state_dir.is_dir():
            candidate = state_dir / f"{request_id}.yaml"
            if candidate.exists():
                matches.append(candidate)
    return matches


def request_id_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    if stem and stem != filename:
        return stem
    return ""
