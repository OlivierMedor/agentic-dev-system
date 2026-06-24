from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agentic_dev.local_execution_recording import (
    ACCEPTED_DECISIONS,
    DEFAULT_EXECUTOR,
    LOCAL_REVIEW_DECISION_FILENAME,
    LOCAL_REVIEW_REPORT_FILENAME,
    LOCAL_EXECUTION_RECORD_FILENAME,
    DECISION_PENDING,
    load_local_review_decision,
    _write_local_review_report,
    LocalReviewDecision,
)
from agentic_dev.review_state.integrity import checksum_mapping, checksum_text, load_yaml_mapping, write_text_file
from agentic_dev.review_state.service import validate_review_bundle


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LocalReviewResult:
    story: str
    story_path: Path
    decision: LocalReviewDecision
    decision_path: Path
    report_path: Path


def record_local_review(
    project_path: Path,
    story: str,
    reviewer: str | None = None,
    decision: str = DECISION_PENDING,
    notes: str | None = None,
    base_ref: str = "origin/main",
    force: bool = False,
) -> LocalReviewResult:
    """Record a structured local review decision for a story.

    This creates a machine-readable review decision bound to the exact
    story, branch, HEAD, manifest checksum, and local execution record.
    It does NOT automatically set ready_for_review in status.yaml.
    """
    project_path = project_path.resolve()

    if decision not in ACCEPTED_DECISIONS:
        accepted = ", ".join(sorted(ACCEPTED_DECISIONS))
        raise ValueError(f"decision must be one of: {accepted}")

    reviewer_name = reviewer or DEFAULT_EXECUTOR

    story_path = project_path / "stories" / story
    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    reports_path = story_path / "reports"

    # 1. Validate the review bundle
    validation = validate_review_bundle(project_path, story, base_ref=base_ref)
    if not validation.valid:
        raise ValueError(
            "Review bundle validation failed: " + "; ".join(validation.reasons)
        )

    manifest = validation.manifest
    if manifest is None:
        raise ValueError("validate_review_bundle returned no manifest")

    repository = manifest.get("repository", {})
    manifest_path = story_path / "review_bundle" / "manifest.yaml"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_checksum = checksum_text(manifest_text)

    # 2. Require an existing local execution record
    record_path = reports_path / LOCAL_EXECUTION_RECORD_FILENAME
    if not record_path.exists():
        raise FileNotFoundError(
            f"Local execution record not found: {record_path}\n"
            "Run `agentic record-local-execution` first."
        )

    try:
        record_data = load_yaml_mapping(record_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to parse local execution record: {e}") from e

    execution_record_checksum = record_data.get("integrity", {}).get("record_checksum", "")
    if not execution_record_checksum:
        raise ValueError("Local execution record has no record_checksum in integrity section")

    # 3. Validate binding
    record_head = record_data.get("repository", {}).get("head_sha")
    current_head = repository.get("head_sha")
    if record_head != current_head:
        raise ValueError(
            f"Local execution record is bound to HEAD {record_head}, but current HEAD is {current_head}. "
            "Re-run record-local-execution first."
        )

    record_manifest_checksum = record_data.get("review_evidence", {}).get("manifest_checksum")
    if record_manifest_checksum != manifest_checksum:
        raise ValueError(
            "Local execution record manifest_checksum does not match current manifest. "
            "Re-run record-local-execution first."
        )

    # 4. Check for existing decision
    decision_path = reports_path / LOCAL_REVIEW_DECISION_FILENAME
    if decision_path.exists() and not force:
        existing = load_local_review_decision(reports_path)
        if existing is not None and existing.execution_record_checksum == execution_record_checksum:
            if existing.decision == decision:
                # Idempotent — same decision already recorded
                report_path = reports_path / LOCAL_REVIEW_REPORT_FILENAME
                return LocalReviewResult(
                    story=story,
                    story_path=story_path,
                    decision=existing,
                    decision_path=decision_path,
                    report_path=report_path,
                )
        raise ValueError(
            "Local review decision already exists. Use --force to replace."
        )

    # 5. Build the decision
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "story_slug": story,
        "branch": repository.get("branch", ""),
        "head_sha": current_head or "",
        "base_sha": repository.get("base_sha", ""),
        "merge_base_sha": repository.get("merge_base_sha", ""),
        "manifest_checksum": manifest_checksum,
        "execution_record_checksum": execution_record_checksum,
        "reviewer": reviewer_name,
        "decision": decision,
        "timestamp": timestamp,
        "notes": notes,
    }
    attestation_checksum = checksum_mapping({k: v for k, v in sorted(payload.items())})
    payload["attestation_checksum"] = attestation_checksum

    # 6. Write decision file
    reports_path.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    write_text_file(decision_path, content)

    review_decision = LocalReviewDecision(
        schema_version=payload["schema_version"],
        story_slug=payload["story_slug"],
        branch=payload["branch"],
        head_sha=payload["head_sha"],
        base_sha=payload["base_sha"],
        merge_base_sha=payload["merge_base_sha"],
        manifest_checksum=payload["manifest_checksum"],
        execution_record_checksum=payload["execution_record_checksum"],
        reviewer=payload["reviewer"],
        decision=payload["decision"],
        timestamp=payload["timestamp"],
        notes=payload["notes"],
        attestation_checksum=payload["attestation_checksum"],
    )

    # Load the record for report generation
    # We need a stub record for report generation; load from the file
    from agentic_dev.local_execution_recording import LocalExecutionRecord
    record_obj = LocalExecutionRecord(
        schema_version=record_data.get("schema_version", 1),
        story_slug=record_data.get("story", {}).get("slug", story),
        story_id=record_data.get("story", {}).get("story_id"),
        branch=record_data.get("repository", {}).get("branch", ""),
        head_sha=record_data.get("repository", {}).get("head_sha", ""),
        base_ref=record_data.get("repository", {}).get("base_ref", ""),
        base_sha=record_data.get("repository", {}).get("base_sha", ""),
        merge_base_sha=record_data.get("repository", {}).get("merge_base_sha", ""),
        manifest_path=record_data.get("review_evidence", {}).get("manifest_path", ""),
        manifest_checksum=record_data.get("review_evidence", {}).get("manifest_checksum", ""),
        committed_patch_checksum=record_data.get("review_evidence", {}).get("committed_patch_checksum", ""),
        pytest_checksum=record_data.get("review_evidence", {}).get("pytest_checksum", ""),
        ruff_checksum=record_data.get("review_evidence", {}).get("ruff_checksum", ""),
        cleanliness=record_data.get("review_evidence", {}).get("cleanliness", ""),
        parity_status=record_data.get("review_evidence", {}).get("parity_status", "not_checked"),
        execution_mode=record_data.get("execution", {}).get("mode", "local"),
        execution_type=record_data.get("execution", {}).get("type", "manual"),
        executor=record_data.get("execution", {}).get("executor", ""),
        executed_at=record_data.get("execution", {}).get("executed_at", ""),
        roles_covered=record_data.get("execution", {}).get("roles_covered", []),
        ai_role_agents_executed=record_data.get("provenance", {}).get("ai_role_agents_executed", False),
        evidence_derived=record_data.get("provenance", {}).get("evidence_derived", True),
        human_attestation_supplied=record_data.get("provenance", {}).get("human_attestation_supplied", False),
        attestation_checksum=record_data.get("provenance", {}).get("attestation_checksum"),
        role_evidence=record_data.get("execution", {}).get("role_evidence", {}),
        local_execution_recorded=record_data.get("readiness", {}).get("local_execution_recorded", True),
        record_checksum=execution_record_checksum,
    )

    # 7. Write updated local review report
    report_path = _write_local_review_report(record_obj, review_decision, reports_path)

    return LocalReviewResult(
        story=story,
        story_path=story_path,
        decision=review_decision,
        decision_path=decision_path,
        report_path=report_path,
    )
