from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentic_dev.cloud_queue.models import CloudQueueRequest, CloudQueueResponse
from agentic_dev.cloud_queue.validation import normalize_relative_path


VALIDATED_SAFE = "validated_safe"
VALIDATED_FAILED = "validated_failed"
APPROVAL_REQUIRED = "approval_required"
VALIDATION_FAILED = "validation_failed"
CLASSIFIED_SAFE = "classified_safe"


@dataclass(frozen=True)
class ComparisonResult:
    request_id: str
    classification: str
    requirement_status: str
    writable_path_status: str
    scope_status: str
    dependency_status: str
    reason: str
    safe_to_apply: bool
    approval_required: bool
    validation_failed: bool
    normalized_response_checksum: str


def compare_requirements(request: CloudQueueRequest, claims: dict[str, Any]) -> tuple[str, list[str]]:
    expected = set(request.requirements)
    applicable = set(str(item) for item in claims.get("applicable_requirements", []) or [])
    missing = sorted(expected - applicable)
    extra = sorted(applicable - expected)
    removed = sorted(str(item) for item in claims.get("removed_requirements", []) or [])
    modified = sorted(str(item) for item in claims.get("modified_requirements", []) or [])

    if removed or modified or extra:
        return "changed", [
            *(f"removed:{item}" for item in removed),
            *(f"modified:{item}" for item in modified),
            *(f"unknown:{item}" for item in extra),
        ]
    if missing:
        return "missing", [f"missing:{item}" for item in missing]
    return "preserved", []


def compare_writable_paths(request: CloudQueueRequest, claims: dict[str, Any]) -> tuple[str, list[str]]:
    expected = {normalize_relative_path(path) for path in request.writable_paths}
    claimed = set()
    for path in claims.get("writable_paths", []) or []:
        claimed.add(normalize_relative_path(str(path)))
    broadened = sorted(claimed - expected)
    narrowed = sorted(expected - claimed)
    if broadened:
        return "broadened", [f"broadened:{item}" for item in broadened]
    if narrowed:
        return "narrowed", [f"narrowed:{item}" for item in narrowed]
    return "preserved", []


def compare_scope(request: CloudQueueRequest, claims: dict[str, Any]) -> tuple[str, list[str]]:
    requested = {str(item).strip().lower() for item in request.notes if str(item).strip()}
    reported = {str(item).strip().lower() for item in claims.get("scope_changes", []) or []}
    if reported - requested:
        return "changed", [f"scope:{item}" for item in sorted(reported - requested)]
    if claims.get("external_service_added"):
        return "changed", ["external_service_added"]
    if claims.get("network_access"):
        return "changed", ["network_access"]
    return "preserved", []


def compare_dependencies(request: CloudQueueRequest, claims: dict[str, Any]) -> tuple[str, list[str]]:
    dependency_status = str(claims.get("dependency_status", "resolved"))
    if dependency_status not in {"resolved", "blocked", "missing"}:
        return "invalid", [dependency_status]
    if dependency_status != "resolved":
        return dependency_status, [dependency_status]
    if request.dependencies and not claims.get("resolved_dependencies"):
        return "blocked", ["resolved_dependencies_missing"]
    return "resolved", []


def classify_response(request: CloudQueueRequest, response: CloudQueueResponse) -> ComparisonResult:
    claims = response.claims
    requirement_status, requirement_details = compare_requirements(request, claims)
    writable_status, writable_details = compare_writable_paths(request, claims)
    scope_status, scope_details = compare_scope(request, claims)
    dependency_status, dependency_details = compare_dependencies(request, claims)

    problems = [*requirement_details, *writable_details, *scope_details, *dependency_details]
    if response.response_schema_version != request.response_schema_version:
        problems.append("schema_version_mismatch")

    if dependency_status in {"blocked", "missing", "invalid"}:
        classification = VALIDATION_FAILED
        reason = "Dependency resolution did not succeed."
        validation_failed = True
        approval_required = False
        safe_to_apply = False
    elif problems and any(item.startswith(("removed:", "modified:", "unknown:", "broadened:", "scope:")) for item in problems):
        classification = APPROVAL_REQUIRED
        reason = "Response changes require operator approval."
        validation_failed = False
        approval_required = True
        safe_to_apply = False
    elif problems:
        classification = VALIDATION_FAILED
        reason = "Response failed independent validation."
        validation_failed = True
        approval_required = False
        safe_to_apply = False
    else:
        classification = CLASSIFIED_SAFE
        reason = "Response matched the request and is safe to validate."
        validation_failed = False
        approval_required = False
        safe_to_apply = True

    if response.decision.upper() == "APPROVED":
        safe_to_apply = False
        approval_required = False
    if response.decision.upper() == "SAFE":
        safe_to_apply = True
    if response.decision.upper() == "APPROVAL_REQUIRED":
        approval_required = True

    return ComparisonResult(
        request_id=request.request_id,
        classification=classification,
        requirement_status=requirement_status,
        writable_path_status=writable_status,
        scope_status=scope_status,
        dependency_status=dependency_status,
        reason=reason,
        safe_to_apply=safe_to_apply,
        approval_required=approval_required,
        validation_failed=validation_failed,
        normalized_response_checksum=response.checksum,
    )
