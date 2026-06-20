from __future__ import annotations

import json
from dataclasses import asdict

from agentic_dev.cloud_queue.classification import ComparisonResult
from agentic_dev.cloud_queue.models import (
    CloudQueueImportResult,
    CloudQueueRequest,
    CloudQueueStatusResult,
)


def format_request(request: CloudQueueRequest) -> str:
    lines = [
        f"Cloud queue request: {request.request_id}",
        f"Story: {request.story}",
        f"State: {request.state}",
        f"Prior state: {request.prior_state}",
        f"Batch: {request.batch_id}",
        f"Title: {request.title}",
        f"Blocker type: {request.blocker_type}",
        "",
        "Details:",
        request.details or "none",
        "",
        "Requirements:",
        format_bullets(request.requirements),
        "",
        "Writable paths:",
        format_bullets(request.writable_paths),
        "",
        "Dependencies:",
        format_bullets(request.dependencies),
    ]
    if request.classification:
        lines.extend(["", f"Classification: {request.classification}"])
    if request.next_action:
        lines.extend(["", f"Next action: {request.next_action}"])
    return "\n".join(lines)


def format_request_list(requests: list[CloudQueueRequest]) -> str:
    if not requests:
        return "No cloud queue requests found.\n"
    lines = ["Cloud queue requests:"]
    for request in requests:
        lines.append(
            f"- {request.request_id} | state={request.state} | story={request.story} | title={request.title}"
        )
    return "\n".join(lines) + "\n"


def format_status(result: CloudQueueStatusResult) -> str:
    lines = [
        "Cloud queue status:",
        f"Total requests: {result.request_count}",
        f"Terminal requests: {result.terminal_count}",
        "",
        "By state:",
    ]
    for state, count in result.counts_by_state.items():
        lines.append(f"- {state}: {count}")
    return "\n".join(lines) + "\n"


def format_classification(result: ComparisonResult) -> str:
    payload = asdict(result)
    lines = [
        f"Request: {result.request_id}",
        f"Classification: {result.classification}",
        f"Requirement status: {result.requirement_status}",
        f"Writable path status: {result.writable_path_status}",
        f"Scope status: {result.scope_status}",
        f"Dependency status: {result.dependency_status}",
        f"Safe to apply: {result.safe_to_apply}",
        f"Approval required: {result.approval_required}",
        f"Validation failed: {result.validation_failed}",
        f"Reason: {result.reason}",
        "",
        json.dumps(payload, sort_keys=True),
    ]
    return "\n".join(lines) + "\n"


def format_import_result(result: CloudQueueImportResult) -> str:
    lines = [
        "Cloud queue import complete:",
        f"Imported: {result.imported_count}",
        f"Valid: {result.valid_count}",
        f"Invalid: {result.invalid_count}",
        f"Skipped: {result.skipped_count}",
    ]
    if result.request_ids:
        lines.extend(["", "Request IDs:"] + [f"- {request_id}" for request_id in result.request_ids])
    return "\n".join(lines) + "\n"


def format_bullets(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)
