from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUEST_SCHEMA_VERSION = 1
RESPONSE_SCHEMA_VERSION = 1

QUEUE_STATES = (
    "new",
    "ready",
    "exported",
    "imported",
    "classified_safe",
    "approval_required",
    "validated_safe",
    "validated_failed",
    "approved",
    "rejected",
    "canceled",
    "failed",
)

TERMINAL_QUEUE_STATES = ("approved", "rejected", "canceled", "failed")

REQUEST_PACKET_FILENAME = "cloud_queue_request.yaml"
REQUEST_PACKET_EXPORT_FILENAME = "cloud_queue_export.md"
REQUEST_PACKET_MANIFEST_FILENAME = "manifest.yaml"
REQUEST_PACKET_TEMPLATE_FILENAME = "response_template.yaml"
REQUEST_PACKET_CONTEXT_FILENAME = "context.md"

DEFAULT_PACKET_VERSION = 1


@dataclass(frozen=True)
class CloudQueueRequest:
    request_id: str
    story: str
    title: str
    blocker_type: str
    details: str
    state: str
    prior_state: str
    batch_id: str
    request_count: int
    request_schema_version: int = REQUEST_SCHEMA_VERSION
    response_schema_version: int = RESPONSE_SCHEMA_VERSION
    requirements: list[str] = field(default_factory=list)
    writable_paths: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    context_files: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    source_task_id: str = ""
    source_plan_revision: str = ""
    packet_checksum: str = ""
    normalized_response_checksum: str = ""
    approval_checksum: str = ""
    raw_response_checksum: str = ""
    classification: str = ""
    next_action: str = ""
    redaction_summary: dict[str, int] = field(default_factory=dict)
    audit_event_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "story": self.story,
            "title": self.title,
            "blocker_type": self.blocker_type,
            "details": self.details,
            "state": self.state,
            "prior_state": self.prior_state,
            "batch_id": self.batch_id,
            "request_count": self.request_count,
            "request_schema_version": self.request_schema_version,
            "response_schema_version": self.response_schema_version,
            "requirements": list(self.requirements),
            "writable_paths": list(self.writable_paths),
            "dependencies": list(self.dependencies),
            "context_files": list(self.context_files),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_task_id": self.source_task_id,
            "source_plan_revision": self.source_plan_revision,
            "packet_checksum": self.packet_checksum,
            "normalized_response_checksum": self.normalized_response_checksum,
            "approval_checksum": self.approval_checksum,
            "raw_response_checksum": self.raw_response_checksum,
            "classification": self.classification,
            "next_action": self.next_action,
            "redaction_summary": dict(self.redaction_summary),
            "audit_event_ids": list(self.audit_event_ids),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CloudQueueRequest":
        return cls(
            request_id=str(data.get("request_id", "")),
            story=str(data.get("story", "")),
            title=str(data.get("title", "")),
            blocker_type=str(data.get("blocker_type", "")),
            details=str(data.get("details", "")),
            state=str(data.get("state", "")),
            prior_state=str(data.get("prior_state", "")),
            batch_id=str(data.get("batch_id", "")),
            request_count=int(data.get("request_count", 1) or 1),
            request_schema_version=int(data.get("request_schema_version", REQUEST_SCHEMA_VERSION)),
            response_schema_version=int(
                data.get("response_schema_version", RESPONSE_SCHEMA_VERSION),
            ),
            requirements=list(data.get("requirements", []) or []),
            writable_paths=list(data.get("writable_paths", []) or []),
            dependencies=list(data.get("dependencies", []) or []),
            context_files=list(data.get("context_files", []) or []),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            source_task_id=str(data.get("source_task_id", "")),
            source_plan_revision=str(data.get("source_plan_revision", "")),
            packet_checksum=str(data.get("packet_checksum", "")),
            normalized_response_checksum=str(data.get("normalized_response_checksum", "")),
            approval_checksum=str(data.get("approval_checksum", "")),
            raw_response_checksum=str(data.get("raw_response_checksum", "")),
            classification=str(data.get("classification", "")),
            next_action=str(data.get("next_action", "")),
            redaction_summary=dict(data.get("redaction_summary", {}) or {}),
            audit_event_ids=list(data.get("audit_event_ids", []) or []),
            notes=list(data.get("notes", []) or []),
        )


@dataclass(frozen=True)
class CloudQueueResponse:
    response_id: str
    request_id: str
    batch_id: str
    response_schema_version: int
    normalized_response: dict[str, Any]
    raw_response: str
    checksum: str
    decision: str
    claims: dict[str, Any]
    adapter: str
    source_file: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "response_id": self.response_id,
            "request_id": self.request_id,
            "batch_id": self.batch_id,
            "response_schema_version": self.response_schema_version,
            "normalized_response": self.normalized_response,
            "raw_response": self.raw_response,
            "checksum": self.checksum,
            "decision": self.decision,
            "claims": self.claims,
            "adapter": self.adapter,
            "source_file": str(self.source_file) if self.source_file else "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], source_file: Path | None = None) -> "CloudQueueResponse":
        return cls(
            response_id=str(data.get("response_id", "")),
            request_id=str(data.get("request_id", "")),
            batch_id=str(data.get("batch_id", "")),
            response_schema_version=int(
                data.get("response_schema_version", RESPONSE_SCHEMA_VERSION),
            ),
            normalized_response=dict(data.get("normalized_response", {}) or {}),
            raw_response=str(data.get("raw_response", "")),
            checksum=str(data.get("checksum", "")),
            decision=str(data.get("decision", "")),
            claims=dict(data.get("claims", {}) or {}),
            adapter=str(data.get("adapter", "")),
            source_file=source_file,
        )


@dataclass(frozen=True)
class CloudQueueAuditEvent:
    event_id: str
    event_type: str
    request_id: str
    batch_id: str
    prior_state: str
    new_state: str
    packet_checksum: str
    request_count: int
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "request_id": self.request_id,
            "batch_id": self.batch_id,
            "prior_state": self.prior_state,
            "new_state": self.new_state,
            "packet_checksum": self.packet_checksum,
            "request_count": self.request_count,
            "timestamp": self.timestamp,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class CloudQueueExportResult:
    export_path: Path
    export_markdown_path: Path
    manifest_path: Path
    packet_checksum: str
    request_ids: list[str]
    request_count: int
    generated_files: list[Path]


@dataclass(frozen=True)
class CloudQueueImportResult:
    imported_count: int
    valid_count: int
    invalid_count: int
    skipped_count: int
    request_ids: list[str]
    audit_event_ids: list[str]
    imported_paths: list[Path]
    failed_paths: list[Path]


@dataclass(frozen=True)
class CloudQueueStatusResult:
    request_count: int
    counts_by_state: dict[str, int]
    requests: list[CloudQueueRequest]
    terminal_count: int

