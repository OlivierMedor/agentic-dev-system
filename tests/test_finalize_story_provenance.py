"""Regression tests: finalize_story provenance must never be 'unknown'."""
from pathlib import Path
import yaml
import pytest

from agentic_dev.finalize_story import finalize_story
from agentic_dev.local_execution_recording import record_local_execution
from agentic_dev.local_review import record_local_review
from agentic_dev.local_execution_recording import DECISION_READY_FOR_REVIEW
from agentic_dev.review_state.service import ReviewBundleValidation
import agentic_dev.finalize_story as fs
import agentic_dev.local_execution_recording as ler
import agentic_dev.local_review as lr
import agentic_dev.local_evidence_validation as lev


def _setup_project(tmp_path: Path):
    import subprocess
    project_path = tmp_path / "project"
    story = "067-provenance-test"
    story_path = project_path / "stories" / story
    review_bundle_path = story_path / "review_bundle"
    validation_path = review_bundle_path / "validation"
    validation_path.mkdir(parents=True, exist_ok=True)
    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "branch", "origin/main"], cwd=project_path, capture_output=True)

    validation_path.joinpath("pytest_output.txt").write_text("status: passed")
    validation_path.joinpath("ruff_output.txt").write_text("All checks passed!")
    (story_path / "status.yaml").write_text(yaml.safe_dump({"ready_for_review": False}))

    manifest_data = {
        "repository": {
            "branch": "story/067",
            "head_sha": "abcd123",
            "base_sha": "1234abcd",
            "merge_base_sha": "1234abcd",
        },
        "working_tree": {"classification": "clean"},
        "validation": {"strict_clean_passed": True, "host_container_git_match": True},
        "host": {"status": "passed", "matched": True, "supplied": True},
        "integrity": {"evidence_checksums": {"committed_patch": "fake"}},
        "committed_diff": {"commit_count": 1, "patch_checksum": "fake"},
    }
    (review_bundle_path / "manifest.yaml").write_text(yaml.safe_dump(manifest_data))

    return project_path, story, story_path, manifest_data


def _mock_all(monkeypatch, manifest_data, project_path):
    """Mock validators and quality gate so we test only provenance logic."""
    rb_val = ReviewBundleValidation(
        valid=True, reasons=[], manifest=manifest_data,
        manifest_path=None, checksum_path=None,
    )
    monkeypatch.setattr(lev, "validate_review_bundle", lambda p, s, base_ref=None: rb_val)
    monkeypatch.setattr(ler, "validate_review_bundle", lambda p, s, base_ref=None: rb_val)
    monkeypatch.setattr(lr, "validate_review_bundle", lambda p, s, base_ref=None: rb_val)

    from agentic_dev.review_bundle import ReviewBundleResult
    dummy_rb = ReviewBundleResult(
        review_bundle_path=project_path / "stories" / "067-provenance-test" / "review_bundle",
        generated_files=[], pytest_passed=True, ruff_passed=True, strict_clean_passed=True,
    )

    class DummyQG:
        overall_ready_for_review = True
        overall_status = "READY_FOR_REVIEW"
        status = "READY_FOR_REVIEW"
        provenance = {"execution_mode": "local"}
        checks = []
        result_path = Path("qg_result.yaml")
        report_path = Path("qg_report.md")
        next_action = "Send to reviewer."

    monkeypatch.setattr(fs, "run_quality_gate", lambda p, s: DummyQG())
    monkeypatch.setattr(fs, "status_from_quality_gate", lambda qg: (qg.overall_status, qg.overall_ready_for_review))
    monkeypatch.setattr(fs, "create_review_bundle_with_runner", lambda p, s, cr: dummy_rb)


# --- Core regression tests ---

def test_provenance_never_unknown_when_valid_evidence(tmp_path: Path, monkeypatch):
    """The primary regression: valid local evidence must never produce 'unknown' provenance."""
    project_path, story, story_path, manifest_data = _setup_project(tmp_path)
    _mock_all(monkeypatch, manifest_data, project_path)

    record_local_execution(project_path, story, execution_type="manual", executor_name="ci-operator")
    record_local_review(project_path, story, reviewer="ci-reviewer", decision=DECISION_READY_FOR_REVIEW)
    result = finalize_story(project_path, story)

    prov = result.execution_provenance
    assert prov is not None, "execution_provenance must not be None when local evidence exists"
    assert prov.get("execution_mode") != "unknown", f"execution_mode should not be 'unknown': {prov}"
    assert prov.get("execution_type") != "unknown", f"execution_type should not be 'unknown': {prov}"
    assert prov.get("executor") != "unknown", f"executor should not be 'unknown': {prov}"
    assert prov.get("execution_mode") == "local"
    assert prov.get("execution_type") == "manual"
    assert prov.get("executor") == "ci-operator"


def test_provenance_roles_covered_populated(tmp_path: Path, monkeypatch):
    """roles_covered must be a non-empty list when developer+test roles are recorded."""
    project_path, story, story_path, manifest_data = _setup_project(tmp_path)
    _mock_all(monkeypatch, manifest_data, project_path)

    record_local_execution(project_path, story, execution_type="manual", executor_name="local-operator")
    record_local_review(project_path, story, decision=DECISION_READY_FOR_REVIEW)
    result = finalize_story(project_path, story)

    prov = result.execution_provenance
    roles = prov.get("roles_covered", [])
    assert isinstance(roles, list), "roles_covered must be a list"
    assert len(roles) > 0, "roles_covered must not be empty when evidence roles are recorded"


def test_provenance_review_decision_populated(tmp_path: Path, monkeypatch):
    """review_decision and review_decision_checksum must be populated after record-local-review."""
    project_path, story, story_path, manifest_data = _setup_project(tmp_path)
    _mock_all(monkeypatch, manifest_data, project_path)

    record_local_execution(project_path, story)
    record_local_review(project_path, story, decision=DECISION_READY_FOR_REVIEW)
    result = finalize_story(project_path, story)

    prov = result.execution_provenance
    assert prov.get("review_decision") == "ready_for_review", f"review_decision wrong: {prov}"
    assert prov.get("review_decision_checksum") is not None, "review_decision_checksum must be set"
    assert prov.get("readiness_source") == "structured_local_review"
    assert prov.get("execution_record_checksum") is not None


def test_provenance_execution_record_checksum_matches(tmp_path: Path, monkeypatch):
    """execution_record_checksum in provenance must match the integrity.record_checksum in the record file."""
    project_path, story, story_path, manifest_data = _setup_project(tmp_path)
    _mock_all(monkeypatch, manifest_data, project_path)

    exec_result = record_local_execution(project_path, story)
    record_local_review(project_path, story, decision=DECISION_READY_FOR_REVIEW)
    finalize_result = finalize_story(project_path, story)

    prov = finalize_result.execution_provenance
    assert prov.get("execution_record_checksum") == exec_result.record.record_checksum


def test_legacy_workflow_uses_legacy_readiness_source(tmp_path: Path, monkeypatch):
    """Legacy workflows (no local execution record) must report readiness_source=legacy_role_agent."""
    project_path, story, story_path, manifest_data = _setup_project(tmp_path)
    _mock_all(monkeypatch, manifest_data, project_path)

    # Do NOT record local execution — legacy path
    result = finalize_story(project_path, story)

    prov = result.execution_provenance
    assert prov is not None, "execution_provenance must not be None for legacy path"
    assert prov.get("readiness_source") == "legacy_role_agent"
    # Legacy must not accidentally bleed 'unknown' into the mode fields
    assert prov.get("execution_mode") == "legacy_role_agent"
    assert prov.get("execution_type") == "legacy_role_agent"
    assert prov.get("executor") == "legacy_role_agent"
    # Legacy must produce ready_for_review True (since QG passes in mock)
    assert result.ready_for_review is True


def test_finalize_result_yaml_provenance_fields(tmp_path: Path, monkeypatch):
    """finalize_story_result.yaml must contain correct provenance fields (not 'unknown')."""
    project_path, story, story_path, manifest_data = _setup_project(tmp_path)
    _mock_all(monkeypatch, manifest_data, project_path)

    record_local_execution(project_path, story, executor_name="test-operator")
    record_local_review(project_path, story, decision=DECISION_READY_FOR_REVIEW)
    result = finalize_story(project_path, story)

    # Read back from disk
    result_yaml = yaml.safe_load(result.finalize_result_path.read_text(encoding="utf-8"))
    prov = result_yaml.get("execution_provenance", {})

    assert prov.get("execution_mode") == "local", f"disk provenance execution_mode wrong: {prov}"
    assert prov.get("executor") == "test-operator"
    assert prov.get("readiness_source") == "structured_local_review"
    assert prov.get("review_decision") == "ready_for_review"
    assert prov.get("review_decision_checksum") is not None
    assert prov.get("execution_record_checksum") is not None
