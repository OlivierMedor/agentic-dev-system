from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.review_state.integrity import checksum_mapping, checksum_text, load_yaml_mapping
from agentic_dev.review_state.service import validate_review_bundle
from agentic_dev.runtime_config import resolve_project_base_ref


@dataclass(frozen=True)
class LocalEvidenceValidationResult:
    execution_record_present: bool
    execution_record_valid: bool
    review_decision_present: bool
    review_decision_valid: bool
    decision: str
    ready_for_review: bool
    roles_covered: list[str]
    provenance: dict[str, object]
    failure_reasons: list[str]
    record_checksum: str | None = None
    review_decision_checksum: str | None = None


def validate_local_evidence(
    project_path: Path,
    story: str,
    base_ref: str | None = None,
) -> LocalEvidenceValidationResult:
    """Validate the canonical local execution record and review decision."""
    project_path = project_path.resolve()
    resolved_base_ref = resolve_project_base_ref(project_path, base_ref)
    story_path = project_path / "stories" / story
    reports_path = story_path / "reports"
    review_bundle_path = story_path / "review_bundle"

    record_path = reports_path / "local_execution_record.yaml"
    decision_path = reports_path / "local_review_decision.yaml"

    execution_record_present = record_path.exists()
    review_decision_present = decision_path.exists()
    
    if not execution_record_present:
        return LocalEvidenceValidationResult(
            execution_record_present=False,
            execution_record_valid=False,
            review_decision_present=review_decision_present,
            review_decision_valid=False,
            decision="pending",
            ready_for_review=False,
            roles_covered=[],
            provenance={},
            failure_reasons=["local_execution_record.yaml is missing"],
        )

    failure_reasons: list[str] = []
    
    # Load record
    try:
        record_data = load_yaml_mapping(record_path.read_text(encoding="utf-8"))
    except Exception as e:
        failure_reasons.append(f"corrupt local_execution_record.yaml: {e}")
        return _build_invalid_result(failure_reasons, review_decision_present)

    # Re-compute record checksum
    record_checksum = record_data.get("integrity", {}).get("record_checksum")
    if not record_checksum:
        failure_reasons.append("execution record is missing record_checksum")
        return _build_invalid_result(
            failure_reasons,
            review_decision_present=review_decision_present,
        )

    computed_record_checksum = compute_local_execution_record_checksum(record_data)
    if computed_record_checksum != record_checksum:
        failure_reasons.append("execution record checksum mismatch")

    # Validate review bundle
    validation = validate_review_bundle(project_path, story, base_ref=resolved_base_ref)
    if not validation.valid:
        failure_reasons.append("review bundle validation failed: " + "; ".join(validation.reasons))
        return _build_invalid_result(
            failure_reasons,
            record_checksum=record_checksum,
            review_decision_present=review_decision_present,
        )

    manifest = validation.manifest
    if not manifest:
        failure_reasons.append("review manifest missing")
        return _build_invalid_result(
            failure_reasons,
            record_checksum=record_checksum,
            review_decision_present=review_decision_present,
        )

    # Validate bindings
    manifest_path = review_bundle_path / "manifest.yaml"
    manifest_checksum = checksum_text(manifest_path.read_text(encoding="utf-8"))
    
    review_evidence = record_data.get("review_evidence", {})
    if review_evidence.get("manifest_checksum") != manifest_checksum:
        failure_reasons.append("execution record manifest_checksum does not match canonical manifest")

    repository = manifest.get("repository", {})
    record_repo = record_data.get("repository", {})
    if record_repo.get("head_sha") != repository.get("head_sha"):
        failure_reasons.append("execution record head_sha mismatch")
    if record_repo.get("base_sha") != repository.get("base_sha"):
        failure_reasons.append("execution record base_sha mismatch")
    if record_repo.get("merge_base_sha") != repository.get("merge_base_sha"):
        failure_reasons.append("execution record merge_base_sha mismatch")

    # Cleanliness
    cleanliness = manifest.get("working_tree", {}).get("classification")
    if review_evidence.get("cleanliness") != cleanliness:
        failure_reasons.append("execution record cleanliness mismatch")

    # Host Parity
    host_status = manifest.get("host", {}).get("status")
    parity_status = review_evidence.get("parity_status")
    if parity_status != host_status and host_status is not None:
        failure_reasons.append("execution record parity_status mismatch")

    execution = record_data.get("execution", {})
    roles_covered = execution.get("roles_covered", [])
    role_evidence = execution.get("role_evidence", {})

    # Validate Role Evidence
    if "developer" in roles_covered:
        if not role_evidence.get("developer", {}).get("committed_patch_checksum"):
            failure_reasons.append("developer role claimed but missing patch checksum in role_evidence")
    
    if "test" in roles_covered:
        if not role_evidence.get("test", {}).get("pytest_evidence_checksum"):
            failure_reasons.append("test role claimed but missing pytest evidence checksum in role_evidence")

    if "docs" in roles_covered:
        docs_ev = role_evidence.get("docs", {})
        if not docs_ev.get("paths") and not docs_ev.get("checksums"):
            failure_reasons.append("docs role claimed but missing paths or checksums in role_evidence")

    if "research" in roles_covered:
        res_ev = role_evidence.get("research", {})
        if not res_ev.get("artifacts"):
            failure_reasons.append("research role claimed but missing artifacts in role_evidence")

    # Check if execution record is fundamentally valid
    execution_record_valid = len(failure_reasons) == 0

    # --- Provenance: read from correct nested keys ---
    execution_sect = record_data.get("execution", {})
    provenance: dict[str, object] = {
        "execution_mode": execution_sect.get("mode", "unknown"),
        "execution_type": execution_sect.get("type", "unknown"),
        "executor": execution_sect.get("executor", "unknown"),
        "roles_covered": execution_sect.get("roles_covered", []),
        "execution_record_checksum": record_checksum,
        "readiness_source": "pending",  # updated below once decision validated
        "review_decision": "pending",
        "review_decision_checksum": None,
    }

    # Now validate Review Decision
    decision_valid = False
    decision_val = "pending"
    ready_for_review = False
    review_decision_checksum: str | None = None

    if review_decision_present:
        try:
            decision_data = load_yaml_mapping(decision_path.read_text(encoding="utf-8"))
            decision_val = decision_data.get("decision", "pending")
            # Compute checksum over the raw decision file text
            review_decision_checksum = checksum_text(decision_path.read_text(encoding="utf-8"))
            if decision_data.get("execution_record_checksum") != record_checksum:
                failure_reasons.append("review decision bound to different execution record")
            elif decision_data.get("head_sha") != repository.get("head_sha"):
                failure_reasons.append("review decision head_sha mismatch")
            elif decision_data.get("manifest_checksum") != manifest_checksum:
                failure_reasons.append("review decision manifest_checksum mismatch")
            else:
                decision_valid = True
                if decision_val == "ready_for_review":
                    ready_for_review = True
                    provenance["readiness_source"] = "structured_local_review"
                    provenance["review_decision"] = decision_val
                    provenance["review_decision_checksum"] = review_decision_checksum
                else:
                    provenance["review_decision"] = decision_val
                    provenance["review_decision_checksum"] = review_decision_checksum
        except Exception as e:
            failure_reasons.append(f"corrupt local_review_decision.yaml: {e}")
            decision_val = "pending"
    
    if execution_record_valid and not decision_valid:
        # User requested: "Do not label the execution record itself invalid merely because review has not occurred."
        if not review_decision_present:
            failure_reasons.append("structured local review decision is pending (missing file)")
        elif decision_val == "pending":
            failure_reasons.append("structured local review decision is pending")

    # If the execution record itself is invalid, force readiness to False
    if not execution_record_valid:
        ready_for_review = False

    return LocalEvidenceValidationResult(
        execution_record_present=True,
        execution_record_valid=execution_record_valid,
        review_decision_present=review_decision_present,
        review_decision_valid=decision_valid,
        decision=decision_val,
        ready_for_review=ready_for_review,
        roles_covered=roles_covered,
        provenance=provenance,
        failure_reasons=failure_reasons,
        record_checksum=record_checksum,
        review_decision_checksum=review_decision_checksum,
    )

def _build_invalid_result(failure_reasons: list[str], record_checksum: str | None = None, review_decision_present: bool = False) -> LocalEvidenceValidationResult:
    return LocalEvidenceValidationResult(
        execution_record_present=True,
        execution_record_valid=False,
        review_decision_present=review_decision_present,
        review_decision_valid=False,
        decision="pending",
        ready_for_review=False,
        roles_covered=[],
        provenance={},
        failure_reasons=failure_reasons,
        record_checksum=record_checksum,
    )


def compute_local_execution_record_checksum(record_data: dict[str, object]) -> str:
    payload_data = {key: value for key, value in record_data.items() if key not in {"integrity", "execution"}}
    repository_data = payload_data.get("repository")
    if isinstance(repository_data, dict):
        payload_data["repository"] = {
            key: None if value == "" else value
            for key, value in repository_data.items()
        }
    execution_data = {
        key: value
        for key, value in record_data.get("execution", {}).items()
        if key != "executed_at"
    }
    payload_data["execution"] = execution_data
    return checksum_mapping(payload_data)
