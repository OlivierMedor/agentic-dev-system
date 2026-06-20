from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.cloud_queue.models import CloudQueueRequest
from agentic_dev.cloud_queue.persistence import checksum_text


@dataclass(frozen=True)
class ApprovalRecord:
    request_id: str
    normalized_response_checksum: str
    approved: bool
    operator_note: str
    recorded_at: str
    record_path: Path


def approval_record_path(project_path: Path, request_id: str) -> Path:
    return project_path.resolve() / ".agentic" / "cloud_queue" / "approvals" / f"{request_id}.yaml"


def record_approval(
    project_path: Path,
    request: CloudQueueRequest,
    normalized_response_checksum: str,
    approved: bool,
    operator_note: str,
    recorded_at: str,
) -> ApprovalRecord:
    path = approval_record_path(project_path, request.request_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_id": request.request_id,
        "normalized_response_checksum": normalized_response_checksum,
        "approved": approved,
        "operator_note": operator_note,
        "recorded_at": recorded_at,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return ApprovalRecord(
        request_id=request.request_id,
        normalized_response_checksum=normalized_response_checksum,
        approved=approved,
        operator_note=operator_note,
        recorded_at=recorded_at,
        record_path=path,
    )


def load_approval_record(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Approval record must be a YAML mapping: {path}")
    return loaded


def approval_checksum(normalized_response: dict[str, Any] | str) -> str:
    if isinstance(normalized_response, str):
        payload = normalized_response
    else:
        payload = yaml.safe_dump(normalized_response, sort_keys=True)
    return checksum_text(payload)

