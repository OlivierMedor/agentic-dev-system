from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

import yaml

from agentic_dev.story_blueprint import load_blueprint_story


CLOUD_QUEUE_SCHEMA_VERSION = 1
CLOUD_RESPONSE_SCHEMA_VERSION = 1
CLOUD_QUEUE_PROVIDER = "manual"
REQUEST_TYPES = (
    "task_redecomposition",
    "architecture_decision",
    "requirement_clarification",
    "failure_analysis",
    "security_review",
    "final_cloud_review",
)
REQUEST_STATUSES = (
    "queued",
    "ready_for_export",
    "exported",
    "awaiting_response",
    "response_imported",
    "validation_failed",
    "validated_safe",
    "approval_required",
    "approved",
    "rejected",
    "applied",
    "failed",
    "cancelled",
)
RESOLVED_DEPENDENCY_STATUSES = {"validated_safe", "approved"}
TRANSITION_MAP = {
    "queued": {"ready_for_export", "cancelled", "failed"},
    "ready_for_export": {"exported", "cancelled", "failed"},
    "exported": {"awaiting_response", "cancelled", "failed"},
    "awaiting_response": {"response_imported", "cancelled", "failed"},
    "response_imported": {"validated_safe", "approval_required", "validation_failed", "failed"},
    "validation_failed": {"cancelled", "failed"},
    "validated_safe": {"approved", "rejected", "applied", "failed", "cancelled"},
    "approval_required": {"approved", "rejected", "failed", "cancelled"},
    "approved": {"rejected", "applied", "failed"},
    "rejected": set(),
    "applied": set(),
    "failed": set(),
    "cancelled": set(),
}
SENSITIVE_PATH_PARTS = {
    ".env",
    ".aws",
    ".ssh",
    "credentials",
    "credential",
    "secrets",
    "secret",
    "token",
    "password",
    "passwd",
    "private",
    "wallet",
    "seed",
}
SENSITIVE_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".netrc",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}
DEFAULT_PACKET_LIMITS = {
    "total_packet_bytes": 1_000_000,
    "total_response_bytes": 250_000,
    "max_files": 20,
    "max_file_size": 120_000,
    "max_request_count_per_batch": 10,
    "max_archive_entries": 40,
    "max_expanded_archive_size": 2_000_000,
    "max_path_length": 180,
}
FUTURE_PROVIDER_NAMES = (
    "OpenAIAdapter",
    "GeminiAdapter",
    "AnthropicAdapter",
    "BedrockAdapter",
    "OpenAICompatibleAdapter",
)


class CloudProviderAdapter(Protocol):
    provider_name: str

    def prepare_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Prepare a provider-neutral cloud packet request."""

    def normalize_response(self, raw_response: bytes, *, request_id: str) -> dict[str, Any]:
        """Normalize a provider response into the canonical internal response model."""


@dataclass(frozen=True)
class ManualPacketAdapter:
    provider_name: str = CLOUD_QUEUE_PROVIDER

    def prepare_request(self, request: dict[str, Any]) -> dict[str, Any]:
        return request

    def normalize_response(self, raw_response: bytes, *, request_id: str) -> dict[str, Any]:
        parsed = load_response_document(raw_response)
        if "response_id" not in parsed or not isinstance(parsed.get("response_id"), str):
            parsed["response_id"] = request_id
        return parsed


@dataclass(frozen=True)
class CloudQueueRequest:
    schema_version: int
    request_id: str
    request_type: str
    story_id: str | int
    story_slug: str
    task_id: str | None
    created_at: str
    status: str
    reason: dict[str, Any]
    requested_action: dict[str, Any]
    requirements: dict[str, list[str]]
    task: dict[str, Any]
    context: dict[str, Any]
    constraints: dict[str, Any]
    response_contract: dict[str, Any]
    dependencies: list[str]
    export_batch_ids: list[str]
    last_export_id: str | None = None
    response_status: str | None = None
    approval_state: str | None = None
    classification: dict[str, Any] | None = None
    validation_result: dict[str, Any] | None = None
    response_checksum: str | None = None
    response_imported_at: str | None = None
    approved_at: str | None = None
    rejected_at: str | None = None
    rejected_reason: str | None = None
    cancelled_at: str | None = None
    failed_at: str | None = None
    applied_at: str | None = None
    next_action: str | None = None
    history: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "request_type": self.request_type,
            "story_id": self.story_id,
            "story_slug": self.story_slug,
            "task_id": self.task_id,
            "created_at": self.created_at,
            "status": self.status,
            "reason": self.reason,
            "requested_action": self.requested_action,
            "requirements": self.requirements,
            "task": self.task,
            "context": self.context,
            "constraints": self.constraints,
            "response_contract": self.response_contract,
            "dependencies": self.dependencies,
            "export_batch_ids": self.export_batch_ids,
            "next_action": self.next_action,
        }
        optional = {
            "last_export_id": self.last_export_id,
            "response_status": self.response_status,
            "approval_state": self.approval_state,
            "classification": self.classification,
            "validation_result": self.validation_result,
            "response_checksum": self.response_checksum,
            "response_imported_at": self.response_imported_at,
            "approved_at": self.approved_at,
            "rejected_at": self.rejected_at,
            "rejected_reason": self.rejected_reason,
            "cancelled_at": self.cancelled_at,
            "failed_at": self.failed_at,
            "applied_at": self.applied_at,
            "history": self.history,
        }
        for key, value in optional.items():
            if value is not None:
                data[key] = value
        return data


@dataclass(frozen=True)
class CloudQueueResponse:
    schema_version: int
    request_id: str
    response_type: str
    status: str
    summary: str
    requirement_preservation: dict[str, list[str]]
    proposed_changes: dict[str, Any]
    risk_classification: dict[str, Any]
    handoff: dict[str, Any]
    response_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "response_type": self.response_type,
            "status": self.status,
            "summary": self.summary,
            "requirement_preservation": self.requirement_preservation,
            "proposed_changes": self.proposed_changes,
            "risk_classification": self.risk_classification,
            "handoff": self.handoff,
        }
        if self.response_id is not None:
            data["response_id"] = self.response_id
        return data


@dataclass(frozen=True)
class CloudQueueValidationResult:
    request_id: str
    passed: bool
    issues: list[str]


@dataclass(frozen=True)
class CloudQueueClassificationResult:
    request_id: str
    classification: str
    reasons: list[str]
    validation: CloudQueueValidationResult


@dataclass(frozen=True)
class CloudQueueExportResult:
    batch_id: str
    request_ids: list[str]
    export_path: Path
    manifest_path: Path
    packet_path: Path
    created_at: str
    request_count: int
    redaction_summary: dict[str, int]
    checksums: dict[str, str]
    reused_existing_export: bool = False


@dataclass(frozen=True)
class CloudQueueImportItemResult:
    request_id: str
    source_path: Path
    raw_path: Path
    normalized_path: Path
    validation_path: Path
    classification_path: Path
    status: str
    classification: str | None
    issues: list[str]
    checksums: dict[str, str]


@dataclass(frozen=True)
class CloudQueueImportBatchResult:
    source_path: Path
    items: list[CloudQueueImportItemResult]
    total_count: int
    valid_count: int
    invalid_count: int
    summary: str


@dataclass(frozen=True)
class CloudQueueListItem:
    request_id: str
    request_type: str
    story_id: str | int
    story_slug: str
    task_id: str | None
    status: str
    blocker_reason: str
    dependencies: list[str]
    export_batch_ids: list[str]
    response_status: str | None
    classification: str | None
    approval_state: str | None
    created_at: str
    updated_at: str | None
    next_action: str | None


@dataclass(frozen=True)
class CloudQueueListResult:
    items: list[CloudQueueListItem]


@dataclass(frozen=True)
class CloudQueueShowResult:
    request: dict[str, Any]
    request_path: Path
    raw_response_path: Path | None
    normalized_response_path: Path | None
    validation_path: Path | None
    classification_path: Path | None
    decision_path: Path | None
    export_paths: list[Path]
    audit_paths: list[Path]


@dataclass(frozen=True)
class CloudQueueStatusResult:
    total_requests: int
    counts_by_status: dict[str, int]
    counts_by_request_type: dict[str, int]
    pending_exports: int
    awaiting_response: int
    approval_required: int
    validated_safe: int
    failed: int
    report_path: Path
    next_action: str


@dataclass(frozen=True)
class CloudQueueApprovalResult:
    request_id: str
    previous_status: str
    new_status: str
    request_path: Path
    decision_path: Path
    checksum: str
    timestamp: str


@dataclass(frozen=True)
class CloudQueueRejectResult:
    request_id: str
    previous_status: str
    new_status: str
    request_path: Path
    decision_path: Path
    reason: str
    timestamp: str


@dataclass(frozen=True)
class CloudQueueImportRecord:
    request_id: str
    source_path: Path
    raw_bytes: bytes
    raw_checksum: str
    normalized: dict[str, Any]


@dataclass(frozen=True)
class CloudQueueService:
    project_path: Path
    adapter: CloudProviderAdapter
    now_fn: Any
    request_id_factory: Any
    batch_id_factory: Any
    event_id_factory: Any
    packet_limits: dict[str, int]

    @property
    def root(self) -> Path:
        return cloud_queue_root(self.project_path)

    def create_request(
        self,
        *,
        request_type: str,
        story_id: str | int,
        story_slug: str,
        reason_code: str,
        reason_summary: str,
        requested_action_summary: str,
        task_id: str | None = None,
        task_title: str = "",
        role: str = "developer",
        dependencies: list[str] | None = None,
        writable_paths: list[str] | None = None,
        expected_outputs: list[str] | None = None,
        validation: list[str] | None = None,
        story_goal: str = "",
        acceptance_criteria: list[str] | None = None,
        architecture_decisions: list[str] | None = None,
        dependency_handoffs: list[str] | None = None,
        local_failure_summary: str = "",
        relevant_files: list[str] | None = None,
        file_summaries: list[dict[str, Any]] | None = None,
        token_estimate: int = 0,
        usable_token_limit: int = 0,
        preserve_requirements: bool = True,
        may_expand_writable_paths: bool = False,
        may_add_external_services: bool = False,
        may_change_architecture: bool = False,
        may_execute_code: bool = False,
        requirement_ids: list[str] | None = None,
        immutable_requirement_ids: list[str] | None = None,
    ) -> CloudQueueRequest:
        self.ensure_storage()
        request_id = self.next_request_id()
        created_at = self.now()
        request = CloudQueueRequest(
            schema_version=CLOUD_QUEUE_SCHEMA_VERSION,
            request_id=request_id,
            request_type=request_type,
            story_id=story_id,
            story_slug=story_slug,
            task_id=task_id,
            created_at=created_at,
            status="queued",
            reason={
                "code": reason_code,
                "summary": reason_summary,
            },
            requested_action={"summary": requested_action_summary},
            requirements={
                "applicable_requirement_ids": requirement_ids or [],
                "immutable_requirement_ids": immutable_requirement_ids or [],
            },
            task={
                "title": task_title,
                "role": role,
                "dependencies": dependencies or [],
                "writable_paths": writable_paths or [],
                "expected_outputs": expected_outputs or [],
                "validation": validation or [],
            },
            context={
                "story_goal": story_goal,
                "acceptance_criteria": acceptance_criteria or [],
                "architecture_decisions": architecture_decisions or [],
                "dependency_handoffs": dependency_handoffs or [],
                "local_failure_summary": local_failure_summary,
                "relevant_files": relevant_files or [],
                "file_summaries": file_summaries or [],
                "token_estimate": token_estimate,
                "usable_token_limit": usable_token_limit,
            },
            constraints={
                "preserve_requirements": preserve_requirements,
                "may_expand_writable_paths": may_expand_writable_paths,
                "may_add_external_services": may_add_external_services,
                "may_change_architecture": may_change_architecture,
                "may_execute_code": may_execute_code,
            },
            response_contract={
                "format": "yaml",
                "schema_version": CLOUD_RESPONSE_SCHEMA_VERSION,
            },
            dependencies=dependencies or [],
            export_batch_ids=[],
            next_action="Mark ready for export once the request is complete and dependency-safe.",
            history=[],
        )
        validate_request_dict(request.to_dict())
        self.save_request(request)
        self.write_audit_event(
            request.request_id,
            event_type="request_creation",
            prior_state=None,
            new_state=request.status,
            summary=f"Created {request.request_type} request from {request.reason['code']}.",
            metadata={
                "story_id": request.story_id,
                "story_slug": request.story_slug,
                "task_id": request.task_id,
            },
        )
        self.transition_request(request.request_id, "ready_for_export", "Request is ready for export.")
        return self.load_request_object(request.request_id)

    def create_request_from_local_blocker(
        self,
        *,
        story: str,
        blocker_type: str,
        story_goal: str,
        acceptance_criteria: list[str],
        blocker_summary: str,
        task_id: str | None = None,
        requirement_ids: list[str] | None = None,
        immutable_requirement_ids: list[str] | None = None,
        dependencies: list[str] | None = None,
        writable_paths: list[str] | None = None,
        expected_outputs: list[str] | None = None,
        validation: list[str] | None = None,
        architecture_decisions: list[str] | None = None,
        dependency_handoffs: list[str] | None = None,
        relevant_files: list[str] | None = None,
        file_summaries: list[dict[str, Any]] | None = None,
        token_estimate: int = 0,
        usable_token_limit: int = 0,
        local_failure_summary: str = "",
    ) -> CloudQueueRequest:
        request_type, reason_code, requested_action_summary = blocker_to_request_type(blocker_type)
        story_slug = story_slug_from_story_name(story)
        return self.create_request(
            request_type=request_type,
            story_id=story_id_from_reference(story),
            story_slug=story_slug,
            task_id=task_id,
            reason_code=reason_code,
            reason_summary=blocker_summary,
            requested_action_summary=requested_action_summary,
            task_title=task_id or "",
            dependencies=dependencies or [],
            writable_paths=writable_paths or [],
            expected_outputs=expected_outputs or [],
            validation=validation or [],
            story_goal=story_goal,
            acceptance_criteria=acceptance_criteria,
            architecture_decisions=architecture_decisions or [],
            dependency_handoffs=dependency_handoffs or [],
            local_failure_summary=local_failure_summary or blocker_summary,
            relevant_files=relevant_files or [],
            file_summaries=file_summaries or [],
            token_estimate=token_estimate,
            usable_token_limit=usable_token_limit,
            requirement_ids=requirement_ids or [],
            immutable_requirement_ids=immutable_requirement_ids or [],
        )

    def list_requests(self) -> CloudQueueListResult:
        self.ensure_storage()
        items: list[CloudQueueListItem] = []
        for request in sorted(self.load_request_dicts(), key=lambda data: str(data["request_id"])):
            items.append(summarize_request(request))
        return CloudQueueListResult(items=items)

    def show_request(self, request_id: str) -> CloudQueueShowResult:
        request_path = self.request_path(request_id)
        request = self.load_request_dict(request_id)
        return CloudQueueShowResult(
            request=request,
            request_path=request_path,
            raw_response_path=self.request_dir(request_id) / "response.raw",
            normalized_response_path=self.request_dir(request_id) / "response.normalized.yaml",
            validation_path=self.request_dir(request_id) / "validation.yaml",
            classification_path=self.request_dir(request_id) / "classification.yaml",
            decision_path=self.request_dir(request_id) / "decision.yaml",
            export_paths=sorted((self.request_dir(request_id) / "exports").glob("*")),
            audit_paths=sorted((self.request_dir(request_id) / "audit").glob("*.yaml")),
        )

    def status(self) -> CloudQueueStatusResult:
        requests = self.load_request_dicts()
        counts_by_status: dict[str, int] = {status: 0 for status in REQUEST_STATUSES}
        counts_by_request_type: dict[str, int] = {request_type: 0 for request_type in REQUEST_TYPES}
        for request in requests:
            counts_by_status[str(request["status"])] = counts_by_status.get(str(request["status"]), 0) + 1
            counts_by_request_type[str(request["request_type"])] = counts_by_request_type.get(
                str(request["request_type"]),
                0,
            ) + 1

        report_path = self.root / "status_report.md"
        result = CloudQueueStatusResult(
            total_requests=len(requests),
            counts_by_status=counts_by_status,
            counts_by_request_type=counts_by_request_type,
            pending_exports=counts_by_status.get("ready_for_export", 0),
            awaiting_response=counts_by_status.get("awaiting_response", 0),
            approval_required=counts_by_status.get("approval_required", 0),
            validated_safe=counts_by_status.get("validated_safe", 0),
            failed=counts_by_status.get("failed", 0),
            report_path=report_path,
            next_action=self.status_next_action(counts_by_status),
        )
        report_path.write_text(format_status_report(result), encoding="utf-8")
        return result

    def export_request(self, request_id: str) -> CloudQueueExportResult:
        request = self.load_request_dict(request_id)
        if request["status"] in {"exported", "awaiting_response"} and request.get("last_export_id"):
            batch_id = str(request["last_export_id"])
            export_dir = self.batch_dir(batch_id)
            manifest_path = export_dir / "manifest.yaml"
            packet_path = export_dir / "cloud_queue_packet.zip"
            checksums = load_checksums(export_dir / "checksums.yaml")
            return CloudQueueExportResult(
                batch_id=batch_id,
                request_ids=[request_id],
                export_path=export_dir,
                manifest_path=manifest_path,
                packet_path=packet_path,
                created_at=str(request.get("last_exported_at", request["created_at"])),
                request_count=1,
                redaction_summary=load_redaction_summary(manifest_path),
                checksums=checksums,
                reused_existing_export=True,
            )

        if request["status"] != "ready_for_export":
            raise ValueError(
                f"Request {request_id} is not ready for export. Current status: {request['status']}.",
            )

        if unresolved_dependency_ids(self, request):
            raise ValueError(
                f"Request {request_id} is blocked by unresolved dependencies: "
                f"{', '.join(unresolved_dependency_ids(self, request))}.",
            )

        batch_id = self.next_batch_id()
        export_dir = self.batch_dir(batch_id)
        export_dir.mkdir(parents=True, exist_ok=True)
        request_dir = self.request_dir(request_id)
        export_dir.mkdir(parents=True, exist_ok=True)
        request_export_dir = request_dir / "exports" / batch_id
        request_export_dir.mkdir(parents=True, exist_ok=True)

        redaction_summary = {"files_included": 0, "files_redacted": 0, "files_skipped": 0}
        context_bundle, request_packet, request_checksum_map = self.build_export_bundle(
            request,
            batch_id=batch_id,
            redaction_summary=redaction_summary,
        )
        packet_path = export_dir / "cloud_queue_packet.zip"
        packet_bytes = build_zip_bytes(context_bundle)
        if len(packet_bytes) > self.packet_limits["total_packet_bytes"]:
            raise ValueError(
                "Cloud packet exceeds the configured total packet byte limit: "
                f"{len(packet_bytes)} > {self.packet_limits['total_packet_bytes']}.",
            )
        atomic_write_bytes(packet_path, packet_bytes)

        manifest = {
            "schema_version": CLOUD_QUEUE_SCHEMA_VERSION,
            "batch_id": batch_id,
            "request_ids": [request_id],
            "request_count": 1,
            "created_at": self.now(),
            "exported_request": request_packet,
            "packet_path": packet_path.name,
            "redaction_summary": redaction_summary,
            "checksums": request_checksum_map,
        }
        manifest_path = export_dir / "manifest.yaml"
        atomic_write_text(manifest_path, yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        atomic_write_text(
            export_dir / "instructions.md",
            build_export_instructions([request_packet]),
            encoding="utf-8",
        )
        atomic_write_text(
            export_dir / "response_schema.yaml",
            yaml.safe_dump(CLOUD_RESPONSE_SCHEMA, sort_keys=False),
            encoding="utf-8",
        )
        atomic_write_text(
            export_dir / "checksums.yaml",
            yaml.safe_dump(request_checksum_map, sort_keys=False),
            encoding="utf-8",
        )
        atomic_write_text(
            request_export_dir / "manifest.yaml",
            yaml.safe_dump(manifest, sort_keys=False),
            encoding="utf-8",
        )
        atomic_write_text(request_export_dir / "packet.zip", packet_bytes, binary=True)
        update_request_fields(
            self.project_path,
            request_id,
            {
                "status": "exported",
                "last_export_id": batch_id,
                "last_exported_at": self.now(),
                "export_batch_ids": append_unique(request.get("export_batch_ids", []), batch_id),
                "next_action": "Upload the packet to a cloud model or share it with an operator.",
            },
        )
        self.transition_request(request_id, "awaiting_response", "Request packet exported and awaiting a response.")
        self.write_audit_event(
            request_id,
            event_type="export_creation",
            prior_state="exported",
            new_state="awaiting_response",
            summary=f"Exported request {request_id} as batch {batch_id}.",
            batch_id=batch_id,
            metadata={"request_count": 1, "packet_sha256": sha256_hex(packet_bytes)},
        )
        return CloudQueueExportResult(
            batch_id=batch_id,
            request_ids=[request_id],
            export_path=export_dir,
            manifest_path=manifest_path,
            packet_path=packet_path,
            created_at=manifest["created_at"],
            request_count=1,
            redaction_summary=redaction_summary,
            checksums=request_checksum_map,
        )

    def export_ready_requests(self) -> CloudQueueExportResult:
        requests = [
            request
            for request in sorted(self.load_request_dicts(), key=lambda data: str(data["request_id"]))
            if request_ready_for_batch_export(request, self)
        ]
        if not requests:
            raise ValueError("No ready requests are available for batch export.")
        if len(requests) > self.packet_limits["max_request_count_per_batch"]:
            raise ValueError(
                "Ready request count exceeds the configured batch limit: "
                f"{len(requests)} > {self.packet_limits['max_request_count_per_batch']}.",
            )
        batch_id = self.next_batch_id()
        export_dir = self.batch_dir(batch_id)
        export_dir.mkdir(parents=True, exist_ok=True)
        packet_bytes, manifest, checksums = self.build_batch_export(requests, batch_id, export_dir)
        packet_path = export_dir / "cloud_queue_packet.zip"
        atomic_write_bytes(packet_path, packet_bytes)
        manifest_path = export_dir / "manifest.yaml"
        atomic_write_text(manifest_path, yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        atomic_write_text(
            export_dir / "instructions.md",
            build_export_instructions(manifest["requests"]),
            encoding="utf-8",
        )
        atomic_write_text(
            export_dir / "response_schema.yaml",
            yaml.safe_dump(CLOUD_RESPONSE_SCHEMA, sort_keys=False),
            encoding="utf-8",
        )
        atomic_write_text(
            export_dir / "checksums.yaml",
            yaml.safe_dump(checksums, sort_keys=False),
            encoding="utf-8",
        )
        for request_packet in manifest["requests"]:
            request_id = str(request_packet["request_id"])
            request_dir = self.request_dir(request_id)
            request_export_dir = request_dir / "exports" / batch_id
            request_export_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_text(
                request_export_dir / "manifest.yaml",
                yaml.safe_dump(manifest, sort_keys=False),
                encoding="utf-8",
            )
            atomic_write_bytes(request_export_dir / "packet.zip", packet_bytes)
            request = self.load_request_dict(request_id)
            update_request_fields(
                self.project_path,
                request_id,
                {
                    "status": "exported",
                    "last_export_id": batch_id,
                    "last_exported_at": manifest["created_at"],
                    "export_batch_ids": append_unique(request.get("export_batch_ids", []), batch_id),
                    "next_action": "Upload the batch packet to a cloud model or operator.",
                },
            )
            self.transition_request(
                request_id,
                "awaiting_response",
                f"Included in batch export {batch_id} and awaiting a response.",
            )
        self.write_audit_event(
            manifest["request_ids"][0],
            event_type="export_creation",
            prior_state="ready_for_export",
            new_state="awaiting_response",
            summary=f"Exported {len(manifest['request_ids'])} request(s) as batch {batch_id}.",
            batch_id=batch_id,
            metadata={"request_count": len(manifest["request_ids"]), "packet_sha256": sha256_hex(packet_bytes)},
        )
        return CloudQueueExportResult(
            batch_id=batch_id,
            request_ids=manifest["request_ids"],
            export_path=export_dir,
            manifest_path=manifest_path,
            packet_path=packet_path,
            created_at=manifest["created_at"],
            request_count=len(manifest["request_ids"]),
            redaction_summary=manifest["redaction_summary"],
            checksums=checksums,
        )

    def build_export_bundle(
        self,
        request: dict[str, Any],
        *,
        batch_id: str,
        redaction_summary: dict[str, int],
    ) -> tuple[dict[str, bytes], dict[str, Any], dict[str, str]]:
        request_packet = self.build_request_packet(request)
        packet_files: dict[str, bytes] = {}

        request_yaml = yaml.safe_dump(request_packet, sort_keys=False)
        packet_files[f"requests/{request['request_id']}.yaml"] = request_yaml.encode("utf-8")
        packet_files["manifest.yaml"] = yaml.safe_dump(
            {
                "schema_version": CLOUD_QUEUE_SCHEMA_VERSION,
                "batch_id": batch_id,
                "request_ids": [request["request_id"]],
                "request_count": 1,
                "created_at": self.now(),
                "redaction_summary": redaction_summary,
            },
            sort_keys=False,
        ).encode("utf-8")

        for relative_path, content in build_request_context_entries(self.project_path, request):
            packet_files[f"context/{relative_path}"] = content
            redaction_summary["files_included"] += 1

        packet_files["instructions.md"] = build_export_instructions([request_packet]).encode("utf-8")
        packet_files["response_schema.yaml"] = yaml.safe_dump(
            CLOUD_RESPONSE_SCHEMA,
            sort_keys=False,
        ).encode("utf-8")

        checksums = {name: sha256_hex(content) for name, content in packet_files.items()}
        return packet_files, request_packet, checksums

    def build_batch_export(
        self,
        requests: list[dict[str, Any]],
        batch_id: str,
        export_dir: Path,
    ) -> tuple[bytes, dict[str, Any], dict[str, str]]:
        packet_files: dict[str, bytes] = {}
        request_packets: list[dict[str, Any]] = []
        redaction_summary = {"files_included": 0, "files_redacted": 0, "files_skipped": 0}
        for request in requests:
            request_packet = self.build_request_packet(request)
            request_packets.append(request_packet)
            packet_files[f"requests/{request['request_id']}.yaml"] = yaml.safe_dump(
                request_packet,
                sort_keys=False,
            ).encode("utf-8")
            for relative_path, content in build_request_context_entries(self.project_path, request):
                packet_files[f"context/{request['request_id']}/{relative_path}"] = content
                redaction_summary["files_included"] += 1
        packet_files["instructions.md"] = build_export_instructions(request_packets).encode("utf-8")
        packet_files["response_schema.yaml"] = yaml.safe_dump(
            CLOUD_RESPONSE_SCHEMA,
            sort_keys=False,
        ).encode("utf-8")
        checksums = {name: sha256_hex(content) for name, content in packet_files.items()}
        manifest = {
            "schema_version": CLOUD_QUEUE_SCHEMA_VERSION,
            "batch_id": batch_id,
            "request_ids": [request["request_id"] for request in requests],
            "request_count": len(requests),
            "created_at": self.now(),
            "redaction_summary": redaction_summary,
            "checksums": checksums,
            "requests": request_packets,
        }
        packet_files["manifest.yaml"] = yaml.safe_dump(manifest, sort_keys=False).encode("utf-8")
        packet_bytes = build_zip_bytes(packet_files)
        if len(packet_bytes) > self.packet_limits["total_packet_bytes"]:
            raise ValueError(
                "Cloud packet exceeds the configured total packet byte limit: "
                f"{len(packet_bytes)} > {self.packet_limits['total_packet_bytes']}.",
            )
        return packet_bytes, manifest, checksums

    def build_request_packet(self, request: dict[str, Any]) -> dict[str, Any]:
        packet = dict(request)
        packet["status"] = "queued"
        packet["history"] = request.get("history", [])
        return packet

    def import_response_bundle(self, source_path: Path) -> CloudQueueImportBatchResult:
        records = load_import_records(source_path, self.packet_limits)
        items: list[CloudQueueImportItemResult] = []
        valid_count = 0
        invalid_count = 0
        for record in records:
            try:
                item = self.import_response_record(record)
            except (FileNotFoundError, ValueError) as error:
                invalid_count += 1
                items.append(
                    CloudQueueImportItemResult(
                        request_id=record.request_id,
                        source_path=record.source_path,
                        raw_path=Path(),
                        normalized_path=Path(),
                        validation_path=Path(),
                        classification_path=Path(),
                        status="invalid",
                        classification=None,
                        issues=[str(error)],
                        checksums={"raw_sha256": record.raw_checksum},
                    ),
                )
                continue
            valid_count += 1
            items.append(item)
        summary = (
            f"Imported {valid_count} valid response(s) and {invalid_count} invalid response(s) "
            f"from {source_path}."
        )
        return CloudQueueImportBatchResult(
            source_path=source_path,
            items=items,
            total_count=len(records),
            valid_count=valid_count,
            invalid_count=invalid_count,
            summary=summary,
        )

    def import_response_record(self, record: CloudQueueImportRecord) -> CloudQueueImportItemResult:
        request = self.load_request_dict(record.request_id)
        if request["request_id"] != record.request_id:
            raise ValueError(f"Unknown request ID: {record.request_id}.")
        if request["status"] not in {"exported", "awaiting_response", "response_imported"}:
            raise ValueError(
                f"Request {record.request_id} was not exported and cannot accept a response. "
                f"Current status: {request['status']}.",
            )
        if request.get("response_checksum"):
            raise ValueError(f"Duplicate response ID or already imported response for {record.request_id}.")

        normalized_response = self.adapter.normalize_response(record.raw_bytes, request_id=record.request_id)
        validate_response_dict(normalized_response)
        if str(normalized_response["request_id"]) != record.request_id:
            raise ValueError(
                f"Response request_id does not match exported request {record.request_id}: "
                f"{normalized_response['request_id']}.",
            )
        if str(normalized_response["response_type"]) != str(request["request_type"]):
            raise ValueError(
                f"Response type {normalized_response['response_type']} does not match request type "
                f"{request['request_type']}.",
            )
        validation = validate_response_against_request(request, normalized_response)
        classification = classify_response(request, normalized_response, validation)

        request_dir = self.request_dir(record.request_id)
        raw_path = request_dir / "response.raw"
        normalized_path = request_dir / "response.normalized.yaml"
        validation_path = request_dir / "validation.yaml"
        classification_path = request_dir / "classification.yaml"
        decision_path = request_dir / "decision.yaml"

        atomic_write_bytes(raw_path, record.raw_bytes)
        atomic_write_text(normalized_path, yaml.safe_dump(normalized_response, sort_keys=False), encoding="utf-8")
        atomic_write_text(
            validation_path,
            yaml.safe_dump(
                {
                    "request_id": validation.request_id,
                    "passed": validation.passed,
                    "issues": validation.issues,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        atomic_write_text(
            classification_path,
            yaml.safe_dump(
                {
                    "request_id": classification.request_id,
                    "classification": classification.classification,
                    "reasons": classification.reasons,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        atomic_write_text(
            decision_path,
            yaml.safe_dump(
                {
                    "request_id": record.request_id,
                    "classification": classification.classification,
                    "decided_at": self.now(),
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        update_request_fields(
            self.project_path,
            record.request_id,
            {
                "status": "response_imported",
                "response_status": "response_imported",
                "response_checksum": record.raw_checksum,
                "response_imported_at": self.now(),
                "classification": {
                    "classification": classification.classification,
                    "reasons": classification.reasons,
                },
                "validation_result": {
                    "passed": validation.passed,
                    "issues": validation.issues,
                },
                "next_action": next_action_for_classification(classification.classification),
            },
        )
        self.transition_request(
            record.request_id,
            classify_to_status(classification.classification),
            "; ".join(classification.reasons),
        )
        self.write_audit_event(
            record.request_id,
            event_type="import_attempt",
            prior_state=request["status"],
            new_state=classify_to_status(classification.classification),
            summary=f"Imported response for {record.request_id} and classified it as {classification.classification}.",
            metadata={
                "raw_sha256": record.raw_checksum,
                "normalized_sha256": sha256_hex(yaml.safe_dump(normalized_response, sort_keys=False).encode("utf-8")),
            },
        )

        request_after = self.load_request_dict(record.request_id)
        return CloudQueueImportItemResult(
            request_id=record.request_id,
            source_path=record.source_path,
            raw_path=raw_path,
            normalized_path=normalized_path,
            validation_path=validation_path,
            classification_path=classification_path,
            status=str(request_after["status"]),
            classification=classification.classification,
            issues=classification.reasons,
            checksums={
                "raw_sha256": record.raw_checksum,
                "normalized_sha256": sha256_hex(yaml.safe_dump(normalized_response, sort_keys=False).encode("utf-8")),
            },
        )

    def approve_request(self, request_id: str) -> CloudQueueApprovalResult:
        request = self.load_request_dict(request_id)
        if request["status"] != "approval_required":
            raise ValueError(
                f"Request {request_id} cannot be approved from status {request['status']}. "
                "Approval is only valid after approval_required classification.",
            )
        if not request.get("response_checksum"):
            raise ValueError(f"Request {request_id} does not yet have an imported response.")
        decision_path = self.request_dir(request_id) / "decision.yaml"
        existing_checksum = sha256_hex((self.request_dir(request_id) / "response.raw").read_bytes())
        if existing_checksum != str(request["response_checksum"]):
            raise ValueError(
                f"Imported response changed since classification for {request_id}; approval refused.",
            )
        timestamp = self.now()
        self.transition_request(request_id, "approved", "Operator approved the classified response.")
        update_request_fields(
            self.project_path,
            request_id,
            {
                "approval_state": "approved",
                "approved_at": timestamp,
                "next_action": "Approved response may be reviewed by the operator for application.",
            },
        )
        self.write_decision_record(
            decision_path,
            {
                "request_id": request_id,
                "decision": "approved",
                "approved_at": timestamp,
                "response_checksum": existing_checksum,
            },
        )
        return CloudQueueApprovalResult(
            request_id=request_id,
            previous_status=str(request["status"]),
            new_status="approved",
            request_path=self.request_path(request_id),
            decision_path=decision_path,
            checksum=existing_checksum,
            timestamp=timestamp,
        )

    def reject_request(self, request_id: str, reason: str) -> CloudQueueRejectResult:
        if not reason.strip():
            raise ValueError("Rejection reason must not be empty.")
        request = self.load_request_dict(request_id)
        if request["status"] not in {"approval_required", "validated_safe"}:
            raise ValueError(
                f"Request {request_id} cannot be rejected from status {request['status']}.",
        )
        timestamp = self.now()
        self.transition_request(request_id, "rejected", f"Operator rejected the response: {reason}")
        update_request_fields(
            self.project_path,
            request_id,
            {
                "approval_state": "rejected",
                "rejected_at": timestamp,
                "rejected_reason": reason,
                "next_action": "No further action is needed unless the operator reopens the request.",
            },
        )
        decision_path = self.request_dir(request_id) / "decision.yaml"
        self.write_decision_record(
            decision_path,
            {
                "request_id": request_id,
                "decision": "rejected",
                "reason": reason,
                "rejected_at": timestamp,
            },
        )
        return CloudQueueRejectResult(
            request_id=request_id,
            previous_status=str(request["status"]),
            new_status="rejected",
            request_path=self.request_path(request_id),
            decision_path=decision_path,
            reason=reason,
            timestamp=timestamp,
        )

    def cancel_request(self, request_id: str, reason: str) -> None:
        self.transition_request(request_id, "cancelled", reason)

    def failed_request(self, request_id: str, reason: str) -> None:
        self.transition_request(request_id, "failed", reason)

    def transition_request(self, request_id: str, new_status: str, summary: str) -> None:
        request = self.load_request_dict(request_id)
        prior_state = str(request["status"])
        if new_status not in TRANSITION_MAP.get(prior_state, set()):
            self.write_audit_event(
                request_id,
                event_type="state_transition_attempt",
                prior_state=prior_state,
                new_state=new_status,
                summary=f"Rejected invalid transition from {prior_state} to {new_status}: {summary}",
                metadata={"allowed_targets": sorted(TRANSITION_MAP.get(prior_state, set()))},
            )
            raise ValueError(
                f"Invalid state transition for {request_id}: {prior_state} -> {new_status}. "
                f"Allowed transitions: {', '.join(sorted(TRANSITION_MAP.get(prior_state, set())))}.",
            )
        timestamp = self.now()
        request["status"] = new_status
        request["next_action"] = next_action_for_status(new_status)
        request["history"] = append_history_entry(
            request.get("history", []),
            prior_state=prior_state,
            new_state=new_status,
            timestamp=timestamp,
            summary=summary,
        )
        state_field_map = {
            "approved": ("approved_at", timestamp),
            "rejected": ("rejected_at", timestamp),
            "cancelled": ("cancelled_at", timestamp),
            "failed": ("failed_at", timestamp),
            "applied": ("applied_at", timestamp),
        }
        if new_status in state_field_map:
            field_name, field_value = state_field_map[new_status]
            request[field_name] = field_value
        if new_status == "ready_for_export":
            request["response_status"] = None
        if new_status == "awaiting_response":
            request["response_status"] = "awaiting_response"
        update_request_dict(self.project_path, request_id, request)
        self.write_audit_event(
            request_id,
            event_type="state_transition_success",
            prior_state=prior_state,
            new_state=new_status,
            summary=summary,
        )

    def write_decision_record(self, path: Path, data: dict[str, Any]) -> None:
        atomic_write_text(path, yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def save_request(self, request: CloudQueueRequest) -> None:
        request_dir = self.request_dir(request.request_id)
        request_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            request_dir / "request.yaml",
            yaml.safe_dump(request.to_dict(), sort_keys=False),
            encoding="utf-8",
        )

    def load_request_object(self, request_id: str) -> CloudQueueRequest:
        return CloudQueueRequest(**self.load_request_dict(request_id))

    def load_request_dict(self, request_id: str) -> dict[str, Any]:
        request_path = self.request_path(request_id)
        if not request_path.exists():
            raise FileNotFoundError(f"Cloud queue request was not found: {request_id}")
        loaded = yaml.safe_load(request_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"Cloud queue request must be a YAML mapping: {request_path}")
        validate_request_dict(loaded)
        return loaded

    def load_request_dicts(self) -> list[dict[str, Any]]:
        requests_root = self.root / "requests"
        if not requests_root.exists():
            return []
        results: list[dict[str, Any]] = []
        for request_dir in sorted(path for path in requests_root.iterdir() if path.is_dir()):
            request_path = request_dir / "request.yaml"
            if not request_path.exists():
                continue
            try:
                loaded = yaml.safe_load(request_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    validate_request_dict(loaded)
                    results.append(loaded)
            except Exception:
                continue
        return results

    def request_path(self, request_id: str) -> Path:
        return self.request_dir(request_id) / "request.yaml"

    def request_dir(self, request_id: str) -> Path:
        return self.root / "requests" / request_id

    def batch_dir(self, batch_id: str) -> Path:
        return self.root / "exports" / batch_id

    def ensure_storage(self) -> None:
        for path in [
            self.root,
            self.root / "requests",
            self.root / "exports",
            self.root / "audit",
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def now(self) -> str:
        return self.now_fn()

    def next_request_id(self) -> str:
        return self.request_id_factory(self)

    def next_batch_id(self) -> str:
        return self.batch_id_factory(self)

    def next_event_id(self) -> str:
        return self.event_id_factory(self)

    def write_audit_event(
        self,
        request_id: str,
        *,
        event_type: str,
        prior_state: str | None,
        new_state: str | None,
        summary: str,
        batch_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        event_id = self.next_event_id()
        event_path = self.root / "audit" / f"{event_id}.yaml"
        event = {
            "event_id": event_id,
            "request_id": request_id,
            "batch_id": batch_id,
            "event_type": event_type,
            "timestamp": self.now(),
            "prior_state": prior_state,
            "new_state": new_state,
            "summary": summary,
            "metadata": metadata or {},
        }
        atomic_write_text(event_path, yaml.safe_dump(event, sort_keys=False), encoding="utf-8")
        return event_path

    def status_next_action(self, counts_by_status: dict[str, int]) -> str:
        if counts_by_status.get("approval_required", 0):
            return "Review and approve or reject responses requiring human approval."
        if counts_by_status.get("validated_safe", 0):
            return "Export validated-safe requests or approve as needed."
        if counts_by_status.get("ready_for_export", 0):
            return "Export ready requests."
        if counts_by_status.get("awaiting_response", 0):
            return "Wait for imported response bundles."
        return "Create a blocker-derived request to start the manual cloud workflow."

    def write_status_report(self) -> CloudQueueStatusResult:
        return self.status()


CLOUD_RESPONSE_SCHEMA = {
    "schema_version": CLOUD_RESPONSE_SCHEMA_VERSION,
    "request_id": "cloud-req-0001",
    "response_type": "task_redecomposition",
    "status": "completed",
    "summary": "",
    "requirement_preservation": {
        "preserved_requirement_ids": [],
        "removed_requirement_ids": [],
        "modified_requirement_ids": [],
    },
    "proposed_changes": {
        "subtasks": [],
        "architecture_decisions": [],
        "writable_paths": [],
        "external_services": [],
    },
    "risk_classification": {
        "claims_requirement_preserving": True,
    },
    "handoff": {
        "decisions": [],
        "risks": [],
        "follow_up_actions": [],
    },
}


def cloud_queue_root(project_path: Path) -> Path:
    return project_path.resolve() / ".agentic" / "cloud_queue"


def artifact_path(request_id: str, filename: str, *, must_exist: bool = False) -> Path:
    path = Path(".agentic") / "cloud_queue" / "requests" / request_id / filename
    if must_exist and not path.exists():
        raise FileNotFoundError(str(path))
    return path


def build_cloud_queue_service(
    project_path: Path,
    *,
    adapter: CloudProviderAdapter | None = None,
    now_fn: Any | None = None,
    request_id_factory: Any | None = None,
    batch_id_factory: Any | None = None,
    event_id_factory: Any | None = None,
    packet_limits: dict[str, int] | None = None,
) -> CloudQueueService:
    resolved_project_path = project_path.resolve()
    limits = dict(DEFAULT_PACKET_LIMITS)
    if packet_limits:
        limits.update(packet_limits)
    return CloudQueueService(
        project_path=resolved_project_path,
        adapter=adapter or ManualPacketAdapter(),
        now_fn=now_fn or utc_now,
        request_id_factory=request_id_factory or default_request_id_factory,
        batch_id_factory=batch_id_factory or default_batch_id_factory,
        event_id_factory=event_id_factory or default_event_id_factory,
        packet_limits=limits,
    )


def create_request_from_story_blocker(
    project_path: Path,
    story: str,
    *,
    blocker_type: str,
    blocker_summary: str,
    task_id: str | None = None,
    requirement_ids: list[str] | None = None,
    immutable_requirement_ids: list[str] | None = None,
    dependencies: list[str] | None = None,
    writable_paths: list[str] | None = None,
    expected_outputs: list[str] | None = None,
    validation: list[str] | None = None,
    local_failure_summary: str = "",
) -> CloudQueueRequest:
    story_path = project_path.resolve() / "stories" / story
    blueprint_story = load_blueprint_story(project_path, story_path)
    story_goal = str((blueprint_story or {}).get("goal", "")).strip()
    acceptance_criteria = (
        [str(item) for item in (blueprint_story or {}).get("acceptance_criteria", [])]
        if isinstance((blueprint_story or {}).get("acceptance_criteria"), list)
        else []
    )
    service = build_cloud_queue_service(project_path)
    request = service.create_request_from_local_blocker(
        story=story,
        blocker_type=blocker_type,
        story_goal=story_goal,
        acceptance_criteria=acceptance_criteria,
        blocker_summary=blocker_summary,
        task_id=task_id,
        requirement_ids=requirement_ids,
        immutable_requirement_ids=immutable_requirement_ids,
        dependencies=dependencies,
        writable_paths=writable_paths,
        expected_outputs=expected_outputs,
        validation=validation,
        local_failure_summary=local_failure_summary,
    )
    return request


def blocker_to_request_type(blocker_type: str) -> tuple[str, str, str]:
    mapping = {
        "context_limit": (
            "task_redecomposition",
            "context_limit_exceeded",
            "Split the task into context-safe subtasks.",
        ),
        "oversized_task": (
            "task_redecomposition",
            "context_limit_exceeded",
            "Split the oversized task into context-safe subtasks.",
        ),
        "repeated_local_failure": (
            "failure_analysis",
            "repeated_local_execution_failure",
            "Analyze the repeated local execution failure and propose a bounded fix.",
        ),
        "requirement_ambiguity": (
            "requirement_clarification",
            "requirement_ambiguity",
            "Clarify the ambiguous requirement before implementation continues.",
        ),
        "architecture_decision": (
            "architecture_decision",
            "architecture_decision_escalation",
            "Return the smallest safe architecture decision with tradeoffs.",
        ),
        "security_review": (
            "security_review",
            "security_review_escalation",
            "Review the request for secret, permission, or boundary risks.",
        ),
        "final_cloud_review": (
            "final_cloud_review",
            "final_cloud_review_prep",
            "Perform a final cloud review of the implementation packet.",
        ),
    }
    if blocker_type not in mapping:
        raise ValueError(f"Unsupported blocker type: {blocker_type}")
    return mapping[blocker_type]


def story_slug_from_story_name(story: str) -> str:
    return story.replace("_", "-")


def story_id_from_reference(story: str) -> str | int:
    match = re.search(r"(\d+)", story)
    if match:
        return int(match.group(1))
    return story


def summarize_request(request: dict[str, Any]) -> CloudQueueListItem:
    blocker_reason = str(request.get("reason", {}).get("summary", ""))
    return CloudQueueListItem(
        request_id=str(request["request_id"]),
        request_type=str(request["request_type"]),
        story_id=request.get("story_id", ""),
        story_slug=str(request.get("story_slug", "")),
        task_id=request.get("task_id"),
        status=str(request["status"]),
        blocker_reason=blocker_reason,
        dependencies=[str(item) for item in request.get("dependencies", [])],
        export_batch_ids=[str(item) for item in request.get("export_batch_ids", [])],
        response_status=request.get("response_status"),
        classification=classification_name(request.get("classification")),
        approval_state=request.get("approval_state"),
        created_at=str(request.get("created_at", "")),
        updated_at=latest_history_timestamp(request.get("history", [])),
        next_action=request.get("next_action"),
    )


def classification_name(classification: Any) -> str | None:
    if isinstance(classification, dict):
        value = classification.get("classification")
        if isinstance(value, str):
            return value
    if isinstance(classification, str):
        return classification
    return None


def latest_history_timestamp(history: Any) -> str | None:
    if not isinstance(history, list) or not history:
        return None
    last = history[-1]
    if isinstance(last, dict):
        value = last.get("timestamp")
        if isinstance(value, str):
            return value
    return None


def validate_request_dict(data: dict[str, Any]) -> None:
    errors = validate_request_errors(data)
    if errors:
        raise ValueError("Cloud queue request validation failed:\n- " + "\n- ".join(errors))


def validate_request_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_fields = [
        "schema_version",
        "request_id",
        "request_type",
        "story_id",
        "story_slug",
        "created_at",
        "status",
        "reason",
        "requested_action",
        "requirements",
        "task",
        "context",
        "constraints",
        "response_contract",
    ]
    for field_name in required_fields:
        if field_name not in data:
            errors.append(f"request.{field_name} is required.")
    if data.get("schema_version") != CLOUD_QUEUE_SCHEMA_VERSION:
        errors.append(
            f"request.schema_version must be {CLOUD_QUEUE_SCHEMA_VERSION}.",
        )
    if str(data.get("request_type", "")) not in REQUEST_TYPES:
        errors.append(f"Unsupported request type: {data.get('request_type')}.")
    if str(data.get("status", "")) not in REQUEST_STATUSES:
        errors.append(f"Unsupported queue status: {data.get('status')}.")
    if not isinstance(data.get("reason"), dict):
        errors.append("request.reason must be a mapping.")
    if not isinstance(data.get("requested_action"), dict):
        errors.append("request.requested_action must be a mapping.")
    if not isinstance(data.get("requirements"), dict):
        errors.append("request.requirements must be a mapping.")
    if not isinstance(data.get("task"), dict):
        errors.append("request.task must be a mapping.")
    if not isinstance(data.get("context"), dict):
        errors.append("request.context must be a mapping.")
    if not isinstance(data.get("constraints"), dict):
        errors.append("request.constraints must be a mapping.")
    if not isinstance(data.get("response_contract"), dict):
        errors.append("request.response_contract must be a mapping.")
    if data.get("response_contract", {}).get("schema_version") != CLOUD_RESPONSE_SCHEMA_VERSION:
        errors.append(
            f"request.response_contract.schema_version must be {CLOUD_RESPONSE_SCHEMA_VERSION}.",
        )
    if isinstance(data.get("dependencies"), list):
        for dependency in data["dependencies"]:
            if not isinstance(dependency, str) or not dependency.strip():
                errors.append("request.dependencies must contain non-empty strings.")
    else:
        errors.append("request.dependencies must be a list.")
    if data.get("status") == "queued" and not data.get("next_action"):
        errors.append("queued requests must declare next_action.")
    return errors


def validate_response_dict(data: dict[str, Any]) -> None:
    errors = validate_response_errors(data)
    if errors:
        raise ValueError("Cloud response validation failed:\n- " + "\n- ".join(errors))


def validate_response_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_fields = [
        "schema_version",
        "request_id",
        "response_type",
        "status",
        "summary",
        "requirement_preservation",
        "proposed_changes",
        "risk_classification",
        "handoff",
    ]
    for field_name in required_fields:
        if field_name not in data:
            errors.append(f"response.{field_name} is required.")
    if data.get("schema_version") != CLOUD_RESPONSE_SCHEMA_VERSION:
        errors.append(f"response.schema_version must be {CLOUD_RESPONSE_SCHEMA_VERSION}.")
    if str(data.get("response_type", "")) not in REQUEST_TYPES:
        errors.append(f"Unsupported response type: {data.get('response_type')}.")
    if not isinstance(data.get("requirement_preservation"), dict):
        errors.append("response.requirement_preservation must be a mapping.")
    if not isinstance(data.get("proposed_changes"), dict):
        errors.append("response.proposed_changes must be a mapping.")
    if not isinstance(data.get("risk_classification"), dict):
        errors.append("response.risk_classification must be a mapping.")
    if not isinstance(data.get("handoff"), dict):
        errors.append("response.handoff must be a mapping.")
    return errors


def validate_response_against_request(
    request: dict[str, Any],
    response: dict[str, Any],
) -> CloudQueueValidationResult:
    issues: list[str] = []
    request_requirement_ids = set(str(item) for item in request.get("requirements", {}).get("applicable_requirement_ids", []))
    immutable_ids = set(str(item) for item in request.get("requirements", {}).get("immutable_requirement_ids", []))
    response_preservation = response.get("requirement_preservation", {})
    preserved = {str(item) for item in response_preservation.get("preserved_requirement_ids", [])}
    removed = {str(item) for item in response_preservation.get("removed_requirement_ids", [])}
    modified = {str(item) for item in response_preservation.get("modified_requirement_ids", [])}

    missing_applicable = sorted(request_requirement_ids - preserved)
    if missing_applicable:
        issues.append("Missing applicable requirements: " + ", ".join(missing_applicable))

    missing_immutable = sorted(immutable_ids - preserved)
    if missing_immutable:
        issues.append("Missing immutable requirements: " + ", ".join(missing_immutable))

    if removed:
        issues.append("Removed requirements: " + ", ".join(sorted(removed)))
    if modified:
        issues.append("Modified requirements: " + ", ".join(sorted(modified)))
    issues.extend(compare_story_goal(request, response))
    issues.extend(compare_validation_constraints(request, response))
    issues.extend(compare_dependency_mapping(request, response))
    if request.get("request_type") == "task_redecomposition":
        issues.extend(validate_child_tasks(request, response))
    return CloudQueueValidationResult(
        request_id=str(request["request_id"]),
        passed=not issues,
        issues=issues,
    )


def compare_story_goal(request: dict[str, Any], response: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    request_goal = str(request.get("context", {}).get("story_goal", "")).strip()
    response_goal = str(response.get("handoff", {}).get("story_goal", "")).strip()
    if response_goal and request_goal and response_goal != request_goal:
        issues.append("Changed story goal detected.")
    return issues


def compare_validation_constraints(request: dict[str, Any], response: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    request_constraints = request.get("constraints", {})
    response_constraints = response.get("proposed_changes", {})
    if request_constraints.get("may_add_external_services") is False:
        if response_constraints.get("external_services"):
            issues.append("External service addition detected.")
    if request_constraints.get("may_change_architecture") is False:
        if response_constraints.get("architecture_decisions"):
            issues.append("Architecture change detected.")
    if request_constraints.get("may_execute_code") is False:
        if response.get("status") not in {"completed", "partial"}:
            issues.append("Response implies live execution or unsupported status.")
    return issues


def compare_dependency_mapping(request: dict[str, Any], response: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    requested_dependencies = {str(item) for item in request.get("task", {}).get("dependencies", [])}
    proposed_subtasks = response.get("proposed_changes", {}).get("subtasks", [])
    if request.get("request_type") == "task_redecomposition" and proposed_subtasks:
        proposed_dependency_targets: set[str] = set()
        for subtask in proposed_subtasks:
            if isinstance(subtask, dict):
                proposed_dependency_targets.update(str(item) for item in subtask.get("depends_on", []))
        if requested_dependencies and not proposed_dependency_targets.issuperset(requested_dependencies):
            issues.append("Child task dependency mapping is incomplete.")
    return issues


def compare_writable_paths(request: dict[str, Any], response: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    requested_paths = [str(item) for item in request.get("task", {}).get("writable_paths", [])]
    response_paths = [str(item) for item in response.get("proposed_changes", {}).get("writable_paths", [])]
    if not requested_paths and response_paths:
        issues.append("Writable path expansion detected.")
    if any(path_is_broadening(requested_paths, path) for path in response_paths):
        issues.append("Writable path expansion detected.")
    if any(PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts for path in response_paths):
        issues.append("Writable path traversal or absolute path detected.")
    if any(is_sensitive_writable_path(path) for path in response_paths):
        issues.append("Sensitive path access detected.")
    return issues


def compare_scope(request: dict[str, Any], response: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    proposed = response.get("proposed_changes", {})
    if proposed.get("external_services"):
        issues.append("External-service addition detected.")
    if request.get("constraints", {}).get("may_add_external_services") is False and proposed.get("external_services"):
        issues.append("Provider or external service addition requires approval.")
    if proposed.get("architecture_decisions") and request.get("constraints", {}).get("may_change_architecture") is False:
        issues.append("Architecture change requires approval.")
    if request.get("request_type") == "security_review" and proposed.get("external_services"):
        issues.append("Security review proposed external-service changes.")
    return issues


def validate_child_tasks(request: dict[str, Any], response: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    subtasks = response.get("proposed_changes", {}).get("subtasks", [])
    if not isinstance(subtasks, list) or not subtasks:
        issues.append("Task redecomposition must propose at least one child task.")
        return issues
    usable_limit = int(request.get("context", {}).get("usable_token_limit", 0))
    seen_ids: set[str] = set()
    for index, subtask in enumerate(subtasks, start=1):
        if not isinstance(subtask, dict):
            issues.append(f"Child task {index} must be a mapping.")
            continue
        required_keys = [
            "id",
            "title",
            "requirement_ids",
            "required_context",
            "depends_on",
            "writable_paths",
            "expected_outputs",
            "validation",
            "estimated_token_usage",
        ]
        missing = [key for key in required_keys if key not in subtask]
        if missing:
            issues.append(f"Child task {index} missing required fields: {', '.join(missing)}")
            continue
        task_id = str(subtask["id"])
        if task_id in seen_ids:
            issues.append(f"Duplicate child task id: {task_id}")
        seen_ids.add(task_id)
        estimated = int(subtask.get("estimated_token_usage", 0))
        if usable_limit and estimated > usable_limit:
            issues.append(f"Child task {task_id} exceeds usable token limit.")
        if not isinstance(subtask.get("requirement_ids"), list) or not subtask["requirement_ids"]:
            issues.append(f"Child task {task_id} must include requirement IDs.")
        if not isinstance(subtask.get("depends_on"), list):
            issues.append(f"Child task {task_id} depends_on must be a list.")
        if not isinstance(subtask.get("writable_paths"), list) or not subtask["writable_paths"]:
            issues.append(f"Child task {task_id} must include writable paths.")
        if not isinstance(subtask.get("expected_outputs"), list) or not subtask["expected_outputs"]:
            issues.append(f"Child task {task_id} must include expected outputs.")
        if not isinstance(subtask.get("validation"), list) or not subtask["validation"]:
            issues.append(f"Child task {task_id} must include validation steps.")
        if not isinstance(subtask.get("required_context"), dict):
            issues.append(f"Child task {task_id} required_context must be a mapping.")
    task_ids = {str(subtask.get("id", "")) for subtask in subtasks if isinstance(subtask, dict)}
    for subtask in subtasks:
        if not isinstance(subtask, dict):
            continue
        task_id = str(subtask.get("id", ""))
        depends_on = [str(item) for item in subtask.get("depends_on", []) if str(item).strip()]
        missing = [dependency for dependency in depends_on if dependency not in task_ids and dependency]
        if missing:
            issues.append(f"Child task {task_id} references unknown dependencies: {', '.join(missing)}")
    if has_task_dependency_cycle(subtasks):
        issues.append("Child task dependency cycle detected.")
    return issues


def classify_response(
    request: dict[str, Any],
    response: dict[str, Any],
    validation: CloudQueueValidationResult,
) -> CloudQueueClassificationResult:
    if not validation.passed:
        classification = "validation_failed"
        reasons = validation.issues
    else:
        reasons = []
        if request.get("request_type") == "task_redecomposition":
            if response.get("proposed_changes", {}).get("subtasks") is not None:
                reasons.append("Task decomposition is comprehensible.")
        issues = compare_scope(request, response) + compare_writable_paths(request, response)
        if issues:
            if comprehensible_scope_change(issues):
                classification = "approval_required"
                reasons.extend(issues)
            else:
                classification = "validation_failed"
                reasons.extend(issues)
        else:
            classification = "validated_safe"
            reasons.append("Response preserves requirements and stays within scope.")
    return CloudQueueClassificationResult(
        request_id=str(request["request_id"]),
        classification=classification,
        reasons=list(dict.fromkeys(reasons)),
        validation=validation,
    )


def comprehensible_scope_change(issues: list[str]) -> bool:
    if not issues:
        return False
    allowed = {
        "External-service addition detected.",
        "Provider or external service addition requires approval.",
        "Architecture change requires approval.",
        "Writable path expansion detected.",
        "Child task dependency mapping is incomplete.",
    }
    return any(issue in allowed for issue in issues)


def classify_to_status(classification: str) -> str:
    if classification == "validated_safe":
        return "validated_safe"
    if classification == "approval_required":
        return "approval_required"
    return "validation_failed"


def next_action_for_classification(classification: str) -> str:
    if classification == "validated_safe":
        return "Review the normalized response and export the next dependent request if needed."
    if classification == "approval_required":
        return "Review the scope change and approve or reject the response."
    return "Inspect the validation issues and decide whether to reject or revise the request."


def next_action_for_status(status: str) -> str | None:
    mapping = {
        "queued": "Complete request details and mark it ready for export.",
        "ready_for_export": "Export the request packet.",
        "exported": "Wait for a response bundle.",
        "awaiting_response": "Upload the exported packet to a cloud model.",
        "response_imported": "Review the validation result.",
        "validation_failed": "Reject, revise, or recreate the request.",
        "validated_safe": "Approve the response or continue to dependent requests.",
        "approval_required": "Approve or reject the response.",
        "approved": "Review before applying or discarding.",
        "rejected": "No further action required unless reopened.",
        "applied": "Record completion evidence if a safe non-mutating interpretation exists.",
        "failed": "Inspect the failure and decide whether to retry.",
        "cancelled": "No further action required.",
    }
    return mapping.get(status)


def request_ready_for_batch_export(request: dict[str, Any], service: CloudQueueService) -> bool:
    if request["status"] != "ready_for_export":
        return False
    if request.get("response_status") in {"awaiting_response", "response_imported"}:
        return False
    if request["status"] in {"cancelled", "failed"}:
        return False
    return not unresolved_dependency_ids(service, request)


def unresolved_dependency_ids(service: CloudQueueService, request: dict[str, Any]) -> list[str]:
    unresolved: list[str] = []
    for dependency_id in request.get("dependencies", []):
        try:
            dependency = service.load_request_dict(str(dependency_id))
        except FileNotFoundError:
            unresolved.append(str(dependency_id))
            continue
        if dependency.get("status") not in RESOLVED_DEPENDENCY_STATUSES:
            unresolved.append(str(dependency_id))
    return unresolved


def compare_request_response(
    request: dict[str, Any],
    response: dict[str, Any],
) -> CloudQueueValidationResult:
    return validate_response_against_request(request, response)


def load_response_document(raw_response: bytes) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(raw_response.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError("Response bytes were not valid UTF-8.") from error
    if not isinstance(loaded, dict):
        raise ValueError("Response document must be a YAML mapping.")
    return loaded


def load_import_records(source_path: Path, packet_limits: dict[str, int]) -> list[CloudQueueImportRecord]:
    resolved_path = source_path.resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Response bundle does not exist: {resolved_path}")
    if resolved_path.is_dir():
        raise ValueError(f"Response bundle must be a file: {resolved_path}")
    suffix = resolved_path.suffix.lower()
    if suffix in {".yaml", ".yml", ".json"}:
        raw_bytes = resolved_path.read_bytes()
        if len(raw_bytes) > packet_limits["total_response_bytes"]:
            raise ValueError("Response file exceeds configured size limits.")
        if suffix == ".json":
            try:
                loaded = json.loads(raw_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError(f"Malformed JSON response file: {resolved_path}") from error
            return normalize_response_document(loaded, raw_bytes, resolved_path)
        loaded = yaml.safe_load(raw_bytes.decode("utf-8"))
        return normalize_response_document(loaded, raw_bytes, resolved_path)
    if suffix == ".zip":
        return load_zip_import_records(resolved_path, packet_limits)
    raise ValueError(f"Unsupported response file type: {resolved_path.suffix}")


def normalize_response_document(
    loaded: Any,
    raw_bytes: bytes,
    source_path: Path,
) -> list[CloudQueueImportRecord]:
    if isinstance(loaded, dict) and isinstance(loaded.get("responses"), list):
        records: list[CloudQueueImportRecord] = []
        for index, item in enumerate(loaded["responses"], start=1):
            if isinstance(item, dict):
                request_id = str(item.get("request_id", "")).strip() or f"{source_path.stem}-{index}"
                record_bytes = yaml.safe_dump(item, sort_keys=False).encode("utf-8")
                normalized = item
            else:
                request_id = f"{source_path.stem}-{index}"
                record_bytes = yaml.safe_dump({"invalid_response": item}, sort_keys=False).encode("utf-8")
                normalized = {"invalid_response": item}
            records.append(
                CloudQueueImportRecord(
                    request_id=request_id,
                    source_path=source_path,
                    raw_bytes=record_bytes,
                    raw_checksum=sha256_hex(record_bytes),
                    normalized=normalized,
                ),
            )
        return records
    if not isinstance(loaded, dict):
        raise ValueError(f"Response document must be a mapping: {source_path}")
    request_id = str(loaded.get("request_id", ""))
    if not request_id:
        raise ValueError(f"Response document missing request_id: {source_path}")
    return [
        CloudQueueImportRecord(
            request_id=request_id,
            source_path=source_path,
            raw_bytes=raw_bytes,
            raw_checksum=sha256_hex(raw_bytes),
            normalized=loaded,
        ),
    ]


def load_zip_import_records(source_path: Path, packet_limits: dict[str, int]) -> list[CloudQueueImportRecord]:
    records: list[CloudQueueImportRecord] = []
    seen_names: set[str] = set()
    with zipfile.ZipFile(source_path) as archive:
        infos = archive.infolist()
        if len(infos) > packet_limits["max_archive_entries"]:
            raise ValueError("Archive contains too many entries.")
        expanded_size = 0
        for info in infos:
            name = normalize_zip_name(info.filename)
            if name in seen_names:
                raise ValueError(f"Duplicate archive path: {name}")
            seen_names.add(name)
            if not name:
                continue
            if is_unsafe_archive_name(name):
                raise ValueError(f"Unsafe archive entry path: {name}")
            if is_special_archive_entry(info):
                raise ValueError(f"Archive entry is not a regular file: {name}")
            if info.file_size > packet_limits["max_file_size"]:
                raise ValueError(f"Archive entry exceeds configured file size: {name}")
            if info.compress_size and info.file_size / max(info.compress_size, 1) > 100:
                raise ValueError(f"Archive entry compression ratio is excessive: {name}")
            expanded_size += info.file_size
            if expanded_size > packet_limits["max_expanded_archive_size"]:
                raise ValueError("Archive exceeds configured expanded size limit.")
            if Path(name).suffix.lower() not in {".yaml", ".yml", ".json"}:
                continue
            raw_bytes = archive.read(info)
            try:
                if Path(name).suffix.lower() == ".json":
                    loaded = json.loads(raw_bytes.decode("utf-8"))
                else:
                    loaded = yaml.safe_load(raw_bytes.decode("utf-8"))
                records.extend(normalize_response_document(loaded, raw_bytes, Path(name)))
            except Exception:
                records.append(
                    CloudQueueImportRecord(
                        request_id=Path(name).stem,
                        source_path=source_path,
                        raw_bytes=raw_bytes,
                        raw_checksum=sha256_hex(raw_bytes),
                        normalized={"invalid_response_file": name},
                    ),
                )
    if not records:
        raise ValueError(f"No response files found in archive: {source_path}")
    return records


def is_unsafe_archive_name(name: str) -> bool:
    pure = PurePosixPath(name)
    if pure.is_absolute():
        return True
    return any(part == ".." for part in pure.parts)


def is_special_archive_entry(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    if mode == 0:
        return False
    file_type = mode & 0o170000
    if file_type == 0:
        return False
    return file_type not in {0o100000, 0o040000}


def normalize_zip_name(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def build_zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            archive.writestr(name, entries[name])
    return buffer.getvalue()


def build_request_context_entries(project_path: Path, request: dict[str, Any]) -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = []
    redaction_notes: list[dict[str, Any]] = []
    context = request.get("context", {})
    relevant_files = [str(item) for item in context.get("relevant_files", [])]
    file_summaries = context.get("file_summaries", [])
    for relative_path in relevant_files:
        path = project_path / PurePosixPath(relative_path)
        if not path.exists() or not path.is_file():
            continue
        if is_sensitive_project_path(relative_path):
            redaction_notes.append({"path": relative_path, "action": "skipped_sensitive"})
            continue
        content = path.read_bytes()
        redacted_content, redactions = redact_bytes(content, relative_path)
        if len(redacted_content) > DEFAULT_PACKET_LIMITS["max_file_size"]:
            redacted_content = redacted_content[: DEFAULT_PACKET_LIMITS["max_file_size"]]
        entries.append((relative_path, redacted_content))
        if redactions:
            redaction_notes.append(
                {
                    "path": relative_path,
                    "action": "redacted",
                    "redactions": redactions,
                },
            )
    if file_summaries:
        entries.append(
            (
                "file_summaries.yaml",
                yaml.safe_dump(file_summaries, sort_keys=False).encode("utf-8"),
            ),
        )
    if redaction_notes:
        entries.append(
            (
                "redaction_notes.yaml",
                yaml.safe_dump(redaction_notes, sort_keys=False).encode("utf-8"),
            ),
        )
    max_body_entries = max(DEFAULT_PACKET_LIMITS["max_files"] - 1, 0)
    body_entries = entries[:max_body_entries]
    body_entries.append(("request.yaml", yaml.safe_dump(request, sort_keys=False).encode("utf-8")))
    return body_entries


def is_sensitive_project_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").strip("/")
    parts = normalized.split("/") if normalized else []
    filename = parts[-1].lower() if parts else normalized.lower()
    if filename in SENSITIVE_FILENAMES:
        return True
    if filename == ".env" or filename.startswith(".env."):
        return True
    if any(part.lower() in SENSITIVE_PATH_PARTS for part in parts):
        return True
    return any(token in normalized.lower() for token in ["api_key", "access_token", "refresh_token", "auth", "secret"])


def redact_bytes(content: bytes, relative_path: str) -> tuple[bytes, int]:
    text = content.decode("utf-8", errors="replace")
    redacted_text, count = redact_text(text)
    return redacted_text.encode("utf-8"), count


def redact_text(text: str) -> tuple[str, int]:
    patterns = [
        r"(?i)(api[_-]?key\s*[:=]\s*)(['\"]?)[^\s'\"]+(\2)",
        r"(?i)(access[_-]?token\s*[:=]\s*)(['\"]?)[^\s'\"]+(\2)",
        r"(?i)(refresh[_-]?token\s*[:=]\s*)(['\"]?)[^\s'\"]+(\2)",
        r"(?i)(password\s*[:=]\s*)(['\"]?)[^\s'\"]+(\2)",
        r"(?i)(authorization:\s*bearer\s+)[^\s]+",
    ]
    count = 0
    redacted = text
    for pattern in patterns:
        redacted, replacements = re.subn(pattern, r"\1[REDACTED]", redacted)
        count += replacements
    key_block_pattern = re.compile(r"-----BEGIN [^-]+ PRIVATE KEY-----.*?-----END [^-]+ PRIVATE KEY-----", re.DOTALL)
    redacted, replacements = key_block_pattern.subn("[REDACTED PRIVATE KEY]", redacted)
    count += replacements
    return redacted, count


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8", binary: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        if binary:
            tmp_path.write_bytes(content if isinstance(content, bytes) else str(content).encode(encoding))
        else:
            tmp_path.write_text(content, encoding=encoding)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def atomic_write_bytes(path: Path, content: bytes) -> None:
    atomic_write_text(path, content, binary=True)


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def append_unique(values: list[str], value: str) -> list[str]:
    items = list(values)
    if value not in items:
        items.append(value)
    return items


def append_history_entry(
    history: Any,
    *,
    prior_state: str,
    new_state: str,
    timestamp: str,
    summary: str,
) -> list[dict[str, Any]]:
    entries = [dict(item) for item in history] if isinstance(history, list) else []
    entries.append(
        {
            "prior_state": prior_state,
            "new_state": new_state,
            "timestamp": timestamp,
            "summary": summary,
        },
    )
    return entries


def default_request_id_factory(service: CloudQueueService) -> str:
    existing = {
        str(request["request_id"])
        for request in service.load_request_dicts()
        if str(request.get("request_id", "")).startswith("cloud-req-")
    }
    counter = 1
    while True:
        candidate = f"cloud-req-{counter:04d}"
        if candidate not in existing:
            return candidate
        counter += 1


def default_batch_id_factory(service: CloudQueueService) -> str:
    existing = {
        path.name
        for path in (service.root / "exports").glob("cloud-batch-*")
        if path.is_dir()
    }
    counter = 1
    while True:
        candidate = f"cloud-batch-{counter:04d}"
        if candidate not in existing:
            return candidate
        counter += 1


def default_event_id_factory(service: CloudQueueService) -> str:
    existing = sorted((service.root / "audit").glob("*.yaml"))
    counter = len(existing) + 1
    return f"cloud-event-{counter:06d}"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_checksums(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def load_redaction_summary(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"files_included": 0, "files_redacted": 0, "files_skipped": 0}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict) and isinstance(loaded.get("redaction_summary"), dict):
        summary = loaded["redaction_summary"]
        return {
            "files_included": int(summary.get("files_included", 0)),
            "files_redacted": int(summary.get("files_redacted", 0)),
            "files_skipped": int(summary.get("files_skipped", 0)),
        }
    return {"files_included": 0, "files_redacted": 0, "files_skipped": 0}


def update_request_fields(project_path: Path, request_id: str, updates: dict[str, Any]) -> None:
    request_path = project_path.resolve() / ".agentic" / "cloud_queue" / "requests" / request_id / "request.yaml"
    request = yaml.safe_load(request_path.read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise ValueError(f"Cloud queue request must be a YAML mapping: {request_path}")
    request.update(updates)
    atomic_write_text(request_path, yaml.safe_dump(request, sort_keys=False), encoding="utf-8")


def update_request_dict(project_path: Path, request_id: str, request: dict[str, Any]) -> None:
    request_path = project_path.resolve() / ".agentic" / "cloud_queue" / "requests" / request_id / "request.yaml"
    atomic_write_text(request_path, yaml.safe_dump(request, sort_keys=False), encoding="utf-8")


def request_export_summary(request: dict[str, Any]) -> str:
    return (
        f"{request['request_id']} | {request['request_type']} | status={request['status']} "
        f"| story={request.get('story_slug', '')}"
    )


def format_request_summary_lines(requests: Iterable[dict[str, Any]]) -> list[str]:
    return [request_export_summary(request) for request in requests]


def build_export_instructions(requests: list[dict[str, Any]]) -> str:
    request_ids = ", ".join(str(request["request_id"]) for request in requests)
    example_response = yaml.safe_dump(
        {
            "responses": [
                {
                    "schema_version": CLOUD_RESPONSE_SCHEMA_VERSION,
                    "request_id": "cloud-req-0001",
                    "response_type": "task_redecomposition",
                    "status": "completed",
                    "summary": "Split the task into smaller bounded subtasks.",
                    "requirement_preservation": {
                        "preserved_requirement_ids": [],
                        "removed_requirement_ids": [],
                        "modified_requirement_ids": [],
                    },
                    "proposed_changes": {
                        "subtasks": [],
                        "architecture_decisions": [],
                        "writable_paths": [],
                        "external_services": [],
                    },
                    "risk_classification": {"claims_requirement_preserving": False},
                    "handoff": {"decisions": [], "risks": [], "follow_up_actions": []},
                }
            ]
        },
        sort_keys=False,
    ).rstrip()
    return f"""# Manual Cloud Queue Instructions

Answer only for the included request IDs: {request_ids}.

Rules:

- Preserve request IDs exactly.
- Follow the response schema in `response_schema.yaml`.
- Do not execute code.
- Do not claim files were changed.
- Do not add credentials.
- Do not expand permissions silently.
- Identify requirement changes explicitly.
- Return one response per request.
- Place responses in the expected response-bundle layout.
- Avoid prose outside the required files.

Response bundle layout:

- `responses/*.yaml` or `responses/*.json`

Example response:

```yaml
{example_response}
```
"""


def format_status_report(result: CloudQueueStatusResult) -> str:
    lines = [
        "# Cloud Queue Status",
        "",
        f"- Total requests: {result.total_requests}",
        f"- Ready for export: {result.pending_exports}",
        f"- Awaiting response: {result.awaiting_response}",
        f"- Approval required: {result.approval_required}",
        f"- Validated safe: {result.validated_safe}",
        f"- Failed: {result.failed}",
        "",
        "## By Status",
        "",
    ]
    for status, count in result.counts_by_status.items():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## By Request Type", ""])
    for request_type, count in result.counts_by_request_type.items():
        lines.append(f"- {request_type}: {count}")
    lines.extend(["", "## Next Action", "", result.next_action, ""])
    return "\n".join(lines)


def path_is_broadening(requested_paths: list[str], candidate: str) -> bool:
    if not requested_paths:
        return False
    normalized_candidate = candidate.replace("\\", "/").strip("/")
    return not any(
        normalized_candidate == requested or normalized_candidate.startswith(requested.rstrip("/*"))
        for requested in requested_paths
    )


def is_sensitive_writable_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return any(token in normalized for token in [".env", "secret", "token", "passwd", "private", "wallet"])


def build_request_packet(
    request: dict[str, Any],
) -> dict[str, Any]:
    return dict(request)


def parse_request_type(request_type: str) -> str:
    if request_type not in REQUEST_TYPES:
        raise ValueError(f"Unsupported request type: {request_type}")
    return request_type


def parse_response_type(response_type: str) -> str:
    if response_type not in REQUEST_TYPES:
        raise ValueError(f"Unsupported response type: {response_type}")
    return response_type


def compare_requirement_sets(request: dict[str, Any], response: dict[str, Any]) -> list[str]:
    return validate_response_against_request(request, response).issues


def has_task_dependency_cycle(subtasks: list[dict[str, Any]]) -> bool:
    graph = {
        str(subtask.get("id", "")): [str(item) for item in subtask.get("depends_on", []) if str(item).strip()]
        for subtask in subtasks
        if isinstance(subtask, dict)
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visited:
            return False
        if node in visiting:
            return True
        visiting.add(node)
        for dependency in graph.get(node, []):
            if dependency in graph and visit(dependency):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def request_context_summary(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request["request_id"],
        "story_id": request["story_id"],
        "story_slug": request["story_slug"],
        "task_id": request.get("task_id"),
        "status": request["status"],
        "reason": request.get("reason", {}),
        "requested_action": request.get("requested_action", {}),
        "requirements": request.get("requirements", {}),
        "task": request.get("task", {}),
        "context": request.get("context", {}),
        "constraints": request.get("constraints", {}),
        "response_contract": request.get("response_contract", {}),
    }


def format_cloud_queue_list(result: CloudQueueListResult) -> str:
    lines = ["Cloud queue requests:"]
    if not result.items:
        lines.extend(["", "No cloud queue requests found."])
        return "\n".join(lines)
    for item in result.items:
        lines.append(
            f"- {item.request_id} | type={item.request_type} | status={item.status} | "
            f"story={item.story_slug} | blocker={item.blocker_reason or 'none'}",
        )
    return "\n".join(lines)


def format_cloud_queue_show(result: CloudQueueShowResult) -> str:
    request = result.request
    lines = [
        f"Cloud queue request: {request['request_id']}",
        f"Path: {result.request_path}",
        "",
        yaml.safe_dump(request, sort_keys=False).rstrip(),
    ]
    if result.raw_response_path.exists():
        lines.extend(["", f"Raw response: {result.raw_response_path}"])
    if result.normalized_response_path.exists():
        lines.extend(["", f"Normalized response: {result.normalized_response_path}"])
    if result.validation_path.exists():
        lines.extend(["", f"Validation: {result.validation_path}"])
    if result.classification_path.exists():
        lines.extend(["", f"Classification: {result.classification_path}"])
    if result.decision_path.exists():
        lines.extend(["", f"Decision: {result.decision_path}"])
    if result.export_paths:
        lines.extend(["", "Exports:"])
        lines.extend(f"- {path}" for path in result.export_paths)
    if result.audit_paths:
        lines.extend(["", "Audit:"])
        lines.extend(f"- {path}" for path in result.audit_paths)
    return "\n".join(lines)


def format_cloud_queue_status(result: CloudQueueStatusResult) -> str:
    return format_status_report(result)


def format_cloud_queue_export(result: CloudQueueExportResult) -> str:
    lines = [
        f"Cloud queue export batch: {result.batch_id}",
        f"Request IDs: {', '.join(result.request_ids)}",
        f"Export path: {result.export_path}",
        f"Packet path: {result.packet_path}",
        f"Manifest: {result.manifest_path}",
        f"Created at: {result.created_at}",
        f"Request count: {result.request_count}",
    ]
    if result.reused_existing_export:
        lines.append("Reused existing export: true")
    lines.extend(["", "Redaction summary:"])
    for key, value in result.redaction_summary.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def format_cloud_queue_import(result: CloudQueueImportBatchResult) -> str:
    lines = [
        f"Cloud queue import summary: {result.summary}",
        f"Source: {result.source_path}",
        f"Total: {result.total_count}",
        f"Valid: {result.valid_count}",
        f"Invalid: {result.invalid_count}",
        "",
    ]
    for item in result.items:
        lines.append(
            f"- {item.request_id} | status={item.status} | classification={item.classification or 'invalid'}",
        )
        for issue in item.issues:
            lines.append(f"  - {issue}")
    return "\n".join(lines)


def format_cloud_queue_approval(result: CloudQueueApprovalResult) -> str:
    return "\n".join(
        [
            f"Cloud queue request approved: {result.request_id}",
            f"Previous status: {result.previous_status}",
            f"New status: {result.new_status}",
            f"Decision record: {result.decision_path}",
            f"Checksum: {result.checksum}",
            f"Timestamp: {result.timestamp}",
        ]
    )


def format_cloud_queue_reject(result: CloudQueueRejectResult) -> str:
    return "\n".join(
        [
            f"Cloud queue request rejected: {result.request_id}",
            f"Previous status: {result.previous_status}",
            f"New status: {result.new_status}",
            f"Decision record: {result.decision_path}",
            f"Reason: {result.reason}",
            f"Timestamp: {result.timestamp}",
        ]
    )
