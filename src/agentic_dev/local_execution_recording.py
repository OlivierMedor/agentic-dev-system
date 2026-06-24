from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.quality_gate import pytest_passed, ruff_passed
from agentic_dev.review_state.integrity import checksum_mapping, checksum_text, load_yaml_mapping, write_text_file
from agentic_dev.review_state.service import validate_review_bundle


SCHEMA_VERSION = 1
ATTESTATION_SCHEMA_VERSION = 1

# Canonical execution modes
MODE_LOCAL = "local"

# Canonical execution types
TYPE_MANUAL = "manual"
TYPE_AGENTLESS = "agentless"
ACCEPTED_EXECUTION_TYPES = frozenset({TYPE_MANUAL, TYPE_AGENTLESS})

# Canonical readiness decisions
DECISION_PENDING = "pending"
DECISION_READY_FOR_REVIEW = "ready_for_review"
DECISION_REQUEST_CHANGES = "request_changes"
ACCEPTED_DECISIONS = frozenset({DECISION_PENDING, DECISION_READY_FOR_REVIEW, DECISION_REQUEST_CHANGES})

# Canonical roles
ROLE_DEVELOPER = "developer"
ROLE_TEST = "test"
ROLE_DOCS = "docs"
ROLE_RESEARCH = "research"
ROLE_LOCAL_REVIEWER = "local_reviewer"
ALL_ROLES = frozenset({ROLE_DEVELOPER, ROLE_TEST, ROLE_DOCS, ROLE_RESEARCH})

# Acceptable cleanliness states for recording
ACCEPTABLE_CLEANLINESS = frozenset({"clean", "normalization_noise_only", "clean_with_generated_artifacts"})

# Default executor name when none is supplied
DEFAULT_EXECUTOR = "local-operator"

# Path traversal protection
_UNSAFE_PATH_PATTERN = re.compile(r"(\.\.|~|\\|\x00)")

LOCAL_EXECUTION_RECORD_FILENAME = "local_execution_record.yaml"
LOCAL_EXECUTION_REPORT_FILENAME = "local_execution_report.md"
LOCAL_TEST_EVIDENCE_FILENAME = "local_test_evidence.md"
LOCAL_REVIEW_DECISION_FILENAME = "local_review_decision.yaml"

# Compatibility report filenames (rendered views of canonical record)
DEVELOPER_REPORT_FILENAME = "developer_report.md"
TEST_REPORT_FILENAME = "test_report.md"
LOCAL_REVIEW_REPORT_FILENAME = "local_review_report.md"


@dataclass(frozen=True)
class LocalExecutionRecord:
    schema_version: int
    story_slug: str
    story_id: str | None
    branch: str
    head_sha: str
    base_ref: str
    base_sha: str
    merge_base_sha: str
    manifest_path: str
    manifest_checksum: str
    committed_patch_checksum: str
    pytest_checksum: str
    ruff_checksum: str
    cleanliness: str
    parity_status: str
    execution_mode: str
    execution_type: str
    executor: str
    executed_at: str
    roles_covered: list[str]
    ai_role_agents_executed: bool
    evidence_derived: bool
    human_attestation_supplied: bool
    attestation_checksum: str | None
    role_evidence: dict[str, Any]
    local_execution_recorded: bool
    record_checksum: str


@dataclass(frozen=True)
class LocalReviewDecision:
    schema_version: int
    story_slug: str
    branch: str
    head_sha: str
    base_sha: str
    merge_base_sha: str
    manifest_checksum: str
    execution_record_checksum: str
    reviewer: str
    decision: str
    timestamp: str
    notes: str | None
    attestation_checksum: str


@dataclass(frozen=True)
class LocalExecutionResult:
    story: str
    story_path: Path
    record: LocalExecutionRecord
    record_path: Path
    dry_run: bool
    reports_written: list[Path]
    review_decision: LocalReviewDecision | None


def _safe_relative_path(path: Path, base: Path) -> str:
    """Convert path to a portable relative string, rejecting unsafe paths."""
    try:
        rel = path.relative_to(base)
    except ValueError:
        raise ValueError(f"Path {path} is not under project root {base}")
    rel_str = str(rel).replace("\\", "/")
    if _UNSAFE_PATH_PATTERN.search(rel_str):
        raise ValueError(f"Unsafe path detected: {rel_str}")
    return rel_str


def _validate_attestation(attestation_data: dict[str, Any], context: dict[str, Any]) -> tuple[bool, str | None, str | None]:
    """Validate a structured attestation dict. Returns (valid, error_msg, checksum)."""
    if attestation_data.get("schema_version") != ATTESTATION_SCHEMA_VERSION:
        return False, f"attestation schema_version must be {ATTESTATION_SCHEMA_VERSION}", None

    required_fields = ["reviewer", "decision", "timestamp", "head_sha", "manifest_checksum"]
    for field_name in required_fields:
        if not attestation_data.get(field_name):
            return False, f"attestation missing required field: {field_name}", None

    if attestation_data["decision"] not in ACCEPTED_DECISIONS:
        accepted = ", ".join(sorted(ACCEPTED_DECISIONS))
        return False, f"attestation decision must be one of: {accepted}", None

    if attestation_data["head_sha"] != context.get("head_sha"):
        return False, f"attestation head_sha does not match current HEAD {context.get('head_sha')}", None

    if attestation_data["manifest_checksum"] != context.get("manifest_checksum"):
        return False, "attestation manifest_checksum does not match current manifest", None

    # Validate timestamp format (ISO 8601)
    try:
        datetime.fromisoformat(attestation_data["timestamp"].replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False, "attestation timestamp must be valid ISO 8601", None

    # Compute checksum over deterministic payload
    payload = {k: v for k, v in sorted(attestation_data.items())}
    checksum = checksum_mapping(payload)
    return True, None, checksum


def _validate_role_coverage(
    requested_roles: list[str],
    manifest: dict[str, Any],
    review_bundle_path: Path,
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Validate role coverage against evidence. Returns (valid_roles, errors, role_evidence)."""
    from agentic_dev.review_state.integrity import checksum_text
    from agentic_dev.quality_gate import pytest_passed
    valid_roles: list[str] = []
    errors: list[str] = []
    role_evidence: dict[str, Any] = {}

    committed_diff = manifest.get("committed_diff", {})

    for role in requested_roles:
        if role not in ALL_ROLES:
            errors.append(f"unsupported role: {role}")
            continue

        if role == ROLE_DEVELOPER:
            if committed_diff.get("commit_count", 0) == 0:
                errors.append("developer role requires committed implementation (commit_count=0)")
            elif not committed_diff.get("patch_checksum"):
                errors.append("developer role requires committed_patch_checksum in manifest")
            else:
                valid_roles.append(role)
                role_evidence["developer"] = {
                    "committed_patch_checksum": committed_diff.get("patch_checksum"),
                    "changed_paths": committed_diff.get("paths", [])
                }

        elif role == ROLE_TEST:
            pytest_path = review_bundle_path / "validation" / "pytest_output.txt"
            if not pytest_path.exists():
                pytest_path = review_bundle_path / "pytest_output.txt"
            if not pytest_passed(pytest_path):
                errors.append("test role requires passing pytest evidence in review bundle")
            else:
                valid_roles.append(role)
                role_evidence["test"] = {
                    "pytest_evidence_checksum": checksum_text(pytest_path.read_text(encoding="utf-8", errors="replace"))
                }

        elif role == ROLE_DOCS:
            doc_paths = [p for p in committed_diff.get("paths", []) if "/docs/" in p or p.endswith(".md")]
            if not doc_paths:
                errors.append("docs role requires documentation changes in committed diff or explicitly passed artifacts")
            else:
                valid_roles.append(role)
                role_evidence["docs"] = {
                    "paths": doc_paths,
                    "checksums": {}
                }

        elif role == ROLE_RESEARCH:
            research_paths = [p for p in committed_diff.get("paths", []) if "research" in p.lower()]
            if not research_paths:
                errors.append("research role requires explicit research artifacts")
            else:
                valid_roles.append(role)
                role_evidence["research"] = {
                    "artifacts": [{"path": p, "checksum": ""} for p in research_paths]
                }

    return valid_roles, errors, role_evidence


def _build_evidence_payload(
    story_slug: str,
    story_id: str | None,
    manifest: dict[str, Any],
    manifest_checksum: str,
    review_bundle_path: Path,
    valid_roles: list[str],
    role_evidence: dict[str, Any],
    execution_type: str,
    executor: str,
    attestation_checksum: str | None,
) -> dict[str, Any]:
    """Build the deterministic evidence payload for checksum computation."""
    from agentic_dev.review_state.integrity import checksum_text
    repository = manifest.get("repository", {})
    committed_diff = manifest.get("committed_diff", {})
    working_tree = manifest.get("working_tree", {})
    host = manifest.get("host", {})

    # Get pytest and ruff checksums from the validation bundle
    pytest_checksum_val = ""
    ruff_checksum_val = ""
    pytest_path = review_bundle_path / "validation" / "pytest_output.txt"
    if not pytest_path.exists():
        pytest_path = review_bundle_path / "pytest_output.txt"
    ruff_path = review_bundle_path / "validation" / "ruff_output.txt"
    if not ruff_path.exists():
        ruff_path = review_bundle_path / "ruff_output.txt"
    if pytest_path.exists():
        pytest_checksum_val = checksum_text(pytest_path.read_text(encoding="utf-8", errors="replace"))
    if ruff_path.exists():
        ruff_checksum_val = checksum_text(ruff_path.read_text(encoding="utf-8", errors="replace"))

    return {
        "schema_version": SCHEMA_VERSION,
        "story": {
            "slug": story_slug,
            "story_id": story_id,
        },
        "repository": {
            "branch": repository.get("branch"),
            "head_sha": repository.get("head_sha"),
            "base_ref": repository.get("requested_base_ref"),
            "base_sha": repository.get("base_sha"),
            "merge_base_sha": repository.get("merge_base_sha"),
        },
        "review_evidence": {
            "manifest_path": f"stories/{story_slug}/review_bundle/manifest.yaml",
            "manifest_checksum": manifest_checksum,
            "committed_patch_checksum": committed_diff.get("patch_checksum", ""),
            "pytest_checksum": pytest_checksum_val,
            "ruff_checksum": ruff_checksum_val,
            "cleanliness": working_tree.get("classification"),
            "parity_status": host.get("status", "not_checked"),
        },
        "execution": {
            "mode": MODE_LOCAL,
            "type": execution_type,
            "executor": executor,
            "roles_covered": sorted(valid_roles),
            "role_evidence": role_evidence,
        },
        "provenance": {
            "ai_role_agents_executed": False,
            "evidence_derived": True,
            "human_attestation_supplied": attestation_checksum is not None,
            "attestation_checksum": attestation_checksum,
        },
        "readiness": {
            "local_execution_recorded": True,
        },
    }


def _compute_record_checksum(payload: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 over the evidence payload."""
    return checksum_mapping(payload)


def _build_record(
    payload: dict[str, Any],
    record_checksum: str,
    executed_at: str,
) -> LocalExecutionRecord:
    """Construct a LocalExecutionRecord from a validated payload."""
    story = payload["story"]
    repo = payload["repository"]
    evidence = payload["review_evidence"]
    execution = payload["execution"]
    provenance = payload["provenance"]
    readiness = payload["readiness"]

    return LocalExecutionRecord(
        schema_version=payload["schema_version"],
        story_slug=story["slug"],
        story_id=story["story_id"],
        branch=repo["branch"] or "",
        head_sha=repo["head_sha"] or "",
        base_ref=repo["base_ref"] or "",
        base_sha=repo["base_sha"] or "",
        merge_base_sha=repo["merge_base_sha"] or "",
        manifest_path=evidence["manifest_path"],
        manifest_checksum=evidence["manifest_checksum"],
        committed_patch_checksum=evidence["committed_patch_checksum"],
        pytest_checksum=evidence["pytest_checksum"],
        ruff_checksum=evidence["ruff_checksum"],
        cleanliness=evidence["cleanliness"] or "",
        parity_status=evidence["parity_status"],
        execution_mode=execution["mode"],
        execution_type=execution["type"],
        executor=execution["executor"],
        executed_at=executed_at,
        roles_covered=list(execution["roles_covered"]),
        ai_role_agents_executed=provenance["ai_role_agents_executed"],
        evidence_derived=provenance["evidence_derived"],
        human_attestation_supplied=provenance["human_attestation_supplied"],
        attestation_checksum=provenance["attestation_checksum"],
        role_evidence=execution["role_evidence"],
        local_execution_recorded=readiness["local_execution_recorded"],
        record_checksum=record_checksum,
    )


def _record_to_yaml_dict(record: LocalExecutionRecord) -> dict[str, Any]:
    """Serialize a LocalExecutionRecord to a dict for YAML output."""
    return {
        "schema_version": record.schema_version,
        "story": {
            "slug": record.story_slug,
            "story_id": record.story_id,
        },
        "repository": {
            "branch": record.branch,
            "head_sha": record.head_sha,
            "base_ref": record.base_ref,
            "base_sha": record.base_sha,
            "merge_base_sha": record.merge_base_sha,
        },
        "review_evidence": {
            "manifest_path": record.manifest_path,
            "manifest_checksum": record.manifest_checksum,
            "committed_patch_checksum": record.committed_patch_checksum,
            "pytest_checksum": record.pytest_checksum,
            "ruff_checksum": record.ruff_checksum,
            "cleanliness": record.cleanliness,
            "parity_status": record.parity_status,
        },
        "execution": {
            "mode": record.execution_mode,
            "type": record.execution_type,
            "executor": record.executor,
            "executed_at": record.executed_at,
            "roles_covered": record.roles_covered,
            "role_evidence": record.role_evidence,
        },
        "provenance": {
            "ai_role_agents_executed": record.ai_role_agents_executed,
            "evidence_derived": record.evidence_derived,
            "human_attestation_supplied": record.human_attestation_supplied,
            "attestation_checksum": record.attestation_checksum,
        },
        "readiness": {
            "local_execution_recorded": record.local_execution_recorded,
        },
        "integrity": {
            "record_checksum": record.record_checksum,
        },
    }


def _write_canonical_record(record: LocalExecutionRecord, reports_path: Path) -> Path:
    """Write the canonical local_execution_record.yaml."""
    record_dict = _record_to_yaml_dict(record)
    content = yaml.safe_dump(record_dict, sort_keys=False, allow_unicode=True)
    record_path = reports_path / LOCAL_EXECUTION_RECORD_FILENAME
    write_text_file(record_path, content)
    return record_path


def _write_developer_report(record: LocalExecutionRecord, reports_path: Path) -> Path:
    """Write developer_report.md as a deterministic view of the canonical record."""
    content = f"""# Developer Report — Evidence-Derived Local Execution

## Provenance

- **Type**: Evidence-derived local execution (not AI role-agent output)
- **No AI role agent executed this story.** This report is generated from validated review bundle evidence.
- **Execution mode**: {record.execution_mode}
- **Execution type**: {record.execution_type}
- **Executor**: {record.executor}
- **Recorded at**: {record.executed_at}

## Story

- **Slug**: {record.story_slug}
- **Story ID**: {record.story_id or 'not specified'}

## Git Identity

- **Branch**: {record.branch}
- **HEAD SHA**: {record.head_sha}
- **Base ref**: {record.base_ref}
- **Base SHA**: {record.base_sha}
- **Merge-base SHA**: {record.merge_base_sha}

## Evidence

- **Manifest path**: {record.manifest_path}
- **Manifest checksum**: {record.manifest_checksum}
- **Committed patch checksum**: {record.committed_patch_checksum}
- **Working tree cleanliness**: {record.cleanliness}
- **Host/container parity**: {record.parity_status}

## Roles covered

{chr(10).join(f'- {r}' for r in record.roles_covered) if record.roles_covered else '- None'}

## Canonical record

- **Record file**: reports/{LOCAL_EXECUTION_RECORD_FILENAME}
- **Record checksum**: {record.record_checksum}

## Readiness

- **Local execution recorded**: {record.local_execution_recorded}

> Readiness is not granted by this report. A structured local review decision or quality gate approval is required.

## Generation command

```
agentic record-local-execution --story {record.story_slug}
```

Schema version: {record.schema_version}
"""
    path = reports_path / DEVELOPER_REPORT_FILENAME
    write_text_file(path, content)
    return path


def _write_test_report(record: LocalExecutionRecord, reports_path: Path) -> Path:
    """Write test_report.md as a deterministic view of the canonical record."""
    content = f"""# Test Report — Evidence-Derived Local Execution

## Provenance

- **Type**: Evidence-derived local execution (not AI test-agent output)
- **No AI test agent executed tests for this story.** This report reflects validated pytest evidence from the review bundle.
- **Executor**: {record.executor}
- **Recorded at**: {record.executed_at}

## Story

- **Slug**: {record.story_slug}

## Git Identity

- **Branch**: {record.branch}
- **HEAD SHA**: {record.head_sha}

## Test Evidence

- **Pytest evidence checksum**: {record.pytest_checksum}
- **Ruff evidence checksum**: {record.ruff_checksum}
- **Evidence source**: review bundle validation evidence (review_bundle/validation/)

## Canonical record

- **Record file**: reports/{LOCAL_EXECUTION_RECORD_FILENAME}
- **Record checksum**: {record.record_checksum}
- **Manifest checksum**: {record.manifest_checksum}

## Readiness


> Test truth comes from validated pytest evidence, not from this report. Editing this report does not alter test results.

Schema version: {record.schema_version}
"""
    path = reports_path / TEST_REPORT_FILENAME
    write_text_file(path, content)
    return path


def _write_local_review_report(record: LocalExecutionRecord, review_decision: LocalReviewDecision | None, reports_path: Path) -> Path:
    """Write local_review_report.md as a deterministic view of the review decision."""
    if review_decision is not None:
        decision_section = f"""## Review Decision

- **Decision**: {review_decision.decision}
- **Reviewer**: {review_decision.reviewer}
- **Timestamp**: {review_decision.timestamp}
- **Notes**: {review_decision.notes or 'None'}
- **Decision checksum**: {review_decision.attestation_checksum}
- **Execution record checksum**: {review_decision.execution_record_checksum}

> This decision is binding only when the attestation checksum matches the canonical record.
"""
    else:
        decision_section = """## Review Decision

- **Decision**: pending
- No structured review decision has been recorded yet.
- Run `agentic record-local-review` to record a review decision.

> Editing this file does not grant readiness. A structured machine-readable decision is required.
"""

    content = f"""# Local Review Report — Evidence-Derived Local Execution

## Provenance

- **Type**: Evidence-derived local execution (not AI reviewer output)
- **No AI reviewer executed this story.** This report reflects the structured local review decision.
- **Executor**: {record.executor}
- **Recorded at**: {record.executed_at}

## Story

- **Slug**: {record.story_slug}

## Git Identity

- **Branch**: {record.branch}
- **HEAD SHA**: {record.head_sha}
- **Manifest checksum**: {record.manifest_checksum}

{decision_section}
## Canonical record

- **Record file**: reports/{LOCAL_EXECUTION_RECORD_FILENAME}
- **Record checksum**: {record.record_checksum}

> Readiness is controlled by the structured review decision, not by text in this file.
> Inserting 'READY_FOR_REVIEW' into this file does not grant readiness.

Schema version: {record.schema_version}
"""
    path = reports_path / LOCAL_REVIEW_REPORT_FILENAME
    write_text_file(path, content)
    return path


def _write_local_execution_report(record: LocalExecutionRecord, reports_path: Path) -> Path:
    """Write the human-readable local_execution_report.md summary."""
    content = f"""# Local Execution Report

## Summary

This story was implemented through a local, evidence-derived workflow.

- **Story**: {record.story_slug}
- **Execution type**: {record.execution_type}
- **Executor**: {record.executor}
- **Recorded at**: {record.executed_at}
- **Roles covered**: {', '.join(record.roles_covered) if record.roles_covered else 'None'}

## Evidence bindings

- **HEAD SHA**: {record.head_sha}
- **Branch**: {record.branch}
- **Manifest checksum**: {record.manifest_checksum}
- **Record checksum**: {record.record_checksum}

## Attestation

- **Human attestation supplied**: {record.human_attestation_supplied}
- **Attestation checksum**: {record.attestation_checksum or 'None'}

## Provenance

- **AI role agents executed**: {record.ai_role_agents_executed}
- **Evidence derived**: {record.evidence_derived}
"""
    path = reports_path / LOCAL_EXECUTION_REPORT_FILENAME
    write_text_file(path, content)
    return path


def load_local_review_decision(reports_path: Path) -> LocalReviewDecision | None:
    """Load a structured local review decision if present."""
    decision_path = reports_path / LOCAL_REVIEW_DECISION_FILENAME
    if not decision_path.exists():
        return None
    try:
        data = load_yaml_mapping(decision_path.read_text(encoding="utf-8"))
        return LocalReviewDecision(
            schema_version=data.get("schema_version", 1),
            story_slug=data.get("story_slug", ""),
            branch=data.get("branch", ""),
            head_sha=data.get("head_sha", ""),
            base_sha=data.get("base_sha", ""),
            merge_base_sha=data.get("merge_base_sha", ""),
            manifest_checksum=data.get("manifest_checksum", ""),
            execution_record_checksum=data.get("execution_record_checksum", ""),
            reviewer=data.get("reviewer", ""),
            decision=data.get("decision", DECISION_PENDING),
            timestamp=data.get("timestamp", ""),
            notes=data.get("notes"),
            attestation_checksum=data.get("attestation_checksum", ""),
        )
    except Exception:
        return None


def validate_local_execution_record(
    project_path: Path,
    story: str,
    manifest: dict[str, Any],
    manifest_checksum: str,
) -> tuple[bool, list[str]]:
    """Validate an existing local execution record against current state."""
    story_path = project_path / "stories" / story
    reports_path = story_path / "reports"
    record_path = reports_path / LOCAL_EXECUTION_RECORD_FILENAME

    if not record_path.exists():
        return True, []  # No record to validate — not an error

    errors: list[str] = []
    try:
        record_data = load_yaml_mapping(record_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, [f"corrupt local execution record: {e}"]

    # Check record checksum
    stored_checksum = record_data.get("integrity", {}).get("record_checksum")
    if stored_checksum:
        # Recompute checksum over the evidence payload (sans integrity section)
        payload_data = {k: v for k, v in record_data.items() if k not in ("integrity", "execution")}
        # Also exclude executed_at from checksum (it is non-deterministic metadata)
        execution_data = {k: v for k, v in record_data.get("execution", {}).items() if k != "executed_at"}
        payload_data["execution"] = execution_data
        computed = checksum_mapping(payload_data)
        if computed != stored_checksum:
            errors.append("local execution record checksum mismatch (record may be tampered)")

    # Check HEAD binding
    repo_data = record_data.get("repository", {})
    manifest_repo = manifest.get("repository", {})
    if repo_data.get("head_sha") != manifest_repo.get("head_sha"):
        errors.append("local execution record HEAD does not match current manifest HEAD")

    # Check manifest checksum binding
    evidence_data = record_data.get("review_evidence", {})
    if evidence_data.get("manifest_checksum") != manifest_checksum:
        errors.append("local execution record manifest_checksum does not match current manifest")

    return not errors, errors


def record_local_execution(
    project_path: Path,
    story: str,
    execution_type: str = TYPE_MANUAL,
    executor_name: str | None = None,
    roles: list[str] | None = None,
    attestation_file: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    base_ref: str = "origin/main",
) -> LocalExecutionResult:
    """Record evidence-derived local execution for a story.

    This function records truthful provenance without claiming AI agents ran.
    It does NOT automatically set ready_for_review. Readiness requires a separate
    structured review decision via `agentic record-local-review`.
    """
    project_path = project_path.resolve()

    # Validate execution type
    if execution_type not in ACCEPTED_EXECUTION_TYPES:
        accepted = ", ".join(sorted(ACCEPTED_EXECUTION_TYPES))
        raise ValueError(f"execution_type must be one of: {accepted}")

    # Default executor
    executor = executor_name or DEFAULT_EXECUTOR

    # Validate executor name for path safety
    if _UNSAFE_PATH_PATTERN.search(executor):
        raise ValueError(f"executor name contains unsafe characters: {executor}")

    # Default roles
    roles_requested = list(roles) if roles else [ROLE_DEVELOPER, ROLE_TEST]

    story_path = project_path / "stories" / story
    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")
    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    reports_path = story_path / "reports"
    review_bundle_path = story_path / "review_bundle"

    # Determine manifest path
    manifest_path = review_bundle_path / "manifest.yaml"

    # Validate path safety
    _safe_relative_path(manifest_path.resolve(), project_path)

    # 1. Validate the review bundle (strict)
    validation = validate_review_bundle(project_path, story, base_ref=base_ref)
    if not validation.valid:
        raise ValueError(
            "Review bundle validation failed before recording: "
            + "; ".join(validation.reasons)
        )

    manifest = validation.manifest
    if manifest is None:
        raise ValueError("validate_review_bundle returned no manifest")

    # 2. Check cleanliness
    working_tree = manifest.get("working_tree", {})
    cleanliness = working_tree.get("classification", "")
    if cleanliness not in ACCEPTABLE_CLEANLINESS:
        raise ValueError(
            f"Working tree cleanliness '{cleanliness}' is not acceptable for local execution recording. "
            f"Must be one of: {', '.join(sorted(ACCEPTABLE_CLEANLINESS))}"
        )

    # 3. Require passing pytest
    pytest_path = review_bundle_path / "validation" / "pytest_output.txt"
    if not pytest_path.exists():
        pytest_path = review_bundle_path / "pytest_output.txt"
    if not pytest_passed(pytest_path):
        raise ValueError("Pytest evidence in review bundle does not show a passing result")

    # 4. Require passing Ruff
    ruff_path = review_bundle_path / "validation" / "ruff_output.txt"
    if not ruff_path.exists():
        ruff_path = review_bundle_path / "ruff_output.txt"
    if not ruff_passed(ruff_path):
        raise ValueError("Ruff evidence in review bundle does not show a passing result")

    # 5. Compute manifest checksum
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_checksum = checksum_text(manifest_text)

    # 6. Validate attestation if provided
    attestation_checksum: str | None = None
    if attestation_file is not None:
        attestation_path = Path(attestation_file).resolve()
        _safe_relative_path(attestation_path, project_path.parent)  # must be accessible
        if not attestation_path.exists():
            raise FileNotFoundError(f"Attestation file does not exist: {attestation_path}")
        try:
            att_data = load_yaml_mapping(attestation_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ValueError(f"Failed to parse attestation file: {e}") from e

        context = {
            "head_sha": manifest.get("repository", {}).get("head_sha"),
            "manifest_checksum": manifest_checksum,
        }
        valid_att, att_error, att_checksum = _validate_attestation(att_data, context)
        if not valid_att:
            raise ValueError(f"Invalid attestation: {att_error}")
        attestation_checksum = att_checksum

    valid_roles, role_errors, role_evidence = _validate_role_coverage(roles_requested, manifest, review_bundle_path)
    if role_errors:
        raise ValueError("Role coverage validation failed: " + "; ".join(role_errors))

    # 9. Read story status for story_id
    story_id: str | None = None
    status_path = story_path / "status.yaml"
    if status_path.exists():
        try:
            status_data = load_yaml_mapping(status_path.read_text(encoding="utf-8"))
            story_id = status_data.get("story_id")
        except Exception:
            pass

    # 10. Build evidence payload (deterministic, for checksum)
    payload = _build_evidence_payload(story_slug=story, story_id=story_id, manifest=manifest, manifest_checksum=manifest_checksum, review_bundle_path=review_bundle_path, valid_roles=valid_roles, role_evidence=role_evidence, execution_type=execution_type, executor=executor, attestation_checksum=attestation_checksum)

    # 11. Compute record checksum (excludes executed_at for idempotency)
    record_checksum = _compute_record_checksum(payload)

    # 12. Check for idempotency — if record already exists with same checksum, preserve executed_at
    executed_at = datetime.now(tz=timezone.utc).isoformat()
    record_path = reports_path / LOCAL_EXECUTION_RECORD_FILENAME
    if record_path.exists():
        try:
            existing_data = load_yaml_mapping(record_path.read_text(encoding="utf-8"))
            existing_checksum = existing_data.get("integrity", {}).get("record_checksum")
            existing_head = existing_data.get("repository", {}).get("head_sha")
            current_head = manifest.get("repository", {}).get("head_sha")

            if existing_checksum == record_checksum:
                # Identical inputs — preserve original executed_at (idempotent)
                executed_at = existing_data.get("execution", {}).get("executed_at", executed_at)
            elif not force:
                existing_manifest_checksum = existing_data.get("review_evidence", {}).get("manifest_checksum")
                if existing_head != current_head or existing_manifest_checksum != manifest_checksum:
                    raise ValueError(
                        "Existing local execution record is bound to a different HEAD or manifest. "
                        "Use --force only after confirming all evidence is current. "
                        f"Existing HEAD: {existing_head}, Current HEAD: {current_head}"
                    )
                raise ValueError(
                    "Local execution record already exists with different inputs. "
                    "Use --force to replace after revalidation."
                )
            # force=True: will overwrite after full validation (already done above)
        except (yaml.YAMLError, KeyError):
            if not force:
                raise ValueError(
                    "Existing local execution record is corrupt. Use --force to replace."
                )

    # 13. Build the record object
    record = _build_record(payload, record_checksum, executed_at)

    # 14. Dry-run: report what would be written, no mutation
    reports_written: list[Path] = []
    dry_run_report: list[str] = []

    if dry_run:
        dry_run_report.append("DRY RUN — no files will be written.")
        dry_run_report.append(f"\nStory: {story}")
        dry_run_report.append(f"HEAD SHA: {record.head_sha}")
        dry_run_report.append(f"Branch: {record.branch}")
        dry_run_report.append(f"Cleanliness: {record.cleanliness}")
        dry_run_report.append(f"Parity status: {record.parity_status}")
        dry_run_report.append(f"Roles covered: {', '.join(record.roles_covered)}")
        dry_run_report.append(f"Record checksum: {record.record_checksum}")
        dry_run_report.append("\nWould write:")
        dry_run_report.append(f"  reports/{LOCAL_EXECUTION_RECORD_FILENAME}")
        dry_run_report.append(f"  reports/{LOCAL_EXECUTION_REPORT_FILENAME}")
        if ROLE_DEVELOPER in valid_roles:
            dry_run_report.append(f"  reports/{DEVELOPER_REPORT_FILENAME}")
        if ROLE_TEST in valid_roles:
            dry_run_report.append(f"  reports/{TEST_REPORT_FILENAME}")
        if ROLE_LOCAL_REVIEWER in valid_roles:
            dry_run_report.append(f"  reports/{LOCAL_REVIEW_REPORT_FILENAME}")
        print("\n".join(dry_run_report))
        return LocalExecutionResult(
            story=story,
            story_path=story_path,
            record=record,
            record_path=record_path,
            dry_run=True,
            reports_written=[],
            review_decision=None,
        )

    # 15. Write canonical record
    reports_path.mkdir(parents=True, exist_ok=True)
    written_record_path = _write_canonical_record(record, reports_path)
    reports_written.append(written_record_path)

    # 16. Write human-readable execution report
    exec_report_path = _write_local_execution_report(record, reports_path)
    reports_written.append(exec_report_path)

    # 17. Write compatibility reports for requested roles
    if ROLE_DEVELOPER in valid_roles:
        reports_written.append(_write_developer_report(record, reports_path))
    if ROLE_TEST in valid_roles:
        reports_written.append(_write_test_report(record, reports_path))
    if ROLE_LOCAL_REVIEWER in valid_roles:
        reports_written.append(_write_local_review_report(record, None, reports_path))

    return LocalExecutionResult(
        story=story,
        story_path=story_path,
        record=record,
        record_path=written_record_path,
        dry_run=False,
        reports_written=reports_written,
        review_decision=None,
    )
