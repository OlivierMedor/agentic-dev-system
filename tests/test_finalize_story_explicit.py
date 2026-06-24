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

def setup_dummy_project(tmp_path: Path):
    project_path = tmp_path / "project"
    story = "067-test-story"
    story_path = project_path / "stories" / story
    review_bundle_path = story_path / "review_bundle"
    validation_path = review_bundle_path / "validation"
    validation_path.mkdir(parents=True, exist_ok=True)
    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)
    import subprocess
    subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "branch", "origin/main"], cwd=project_path, capture_output=True)

    validation_path.joinpath("pytest_output.txt").write_text("status: passed")
    validation_path.joinpath("ruff_output.txt").write_text("All checks passed!")
    
    # Needs status.yaml
    status_path = story_path / "status.yaml"
    status_path.write_text(yaml.safe_dump({"ready_for_review": False}))

    manifest_data = {
        "repository": {
            "branch": "story/067",
            "head_sha": "abcd123",
            "base_sha": "1234abcd",
            "merge_base_sha": "1234abcd",
        },
        "working_tree": {"classification": "clean"},
        "validation": {"strict_clean_passed": True, "host_container_git_match": True},
        "host": {"status": "passed", "matched": True},
        "integrity": {"evidence_checksums": {"committed_patch": "fake"}},
        "committed_diff": {"commit_count": 1, "patch_checksum": "fake"},
    }
    manifest_path = review_bundle_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest_data))
    
    return project_path, story, story_path, manifest_data

def mock_validators(monkeypatch, manifest_data):
    monkeypatch.setattr(lev, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=True, reasons=[], manifest=manifest_data, manifest_path=None, checksum_path=None))
    monkeypatch.setattr(ler, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=True, reasons=[], manifest=manifest_data, manifest_path=None, checksum_path=None))
    monkeypatch.setattr(lr, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=True, reasons=[], manifest=manifest_data, manifest_path=None, checksum_path=None))
    class DummyQG:
        def __init__(self):
            self.overall_ready_for_review = True
            self.overall_status = "READY_FOR_REVIEW"
            self.status = "READY_FOR_REVIEW"
            self.provenance = {"execution_mode": "local"}
            self.checks = []
            from pathlib import Path
            self.result_path = Path("qg_result.yaml")
            self.report_path = Path("qg_report.md")
            self.next_action = "none" 
    monkeypatch.setattr(fs, "run_quality_gate", lambda p, s: DummyQG())
    monkeypatch.setattr(fs, "status_from_quality_gate", lambda qg: (qg.overall_status, qg.overall_ready_for_review))
    from agentic_dev.review_bundle import ReviewBundleResult
    dummy_rb = ReviewBundleResult(
        review_bundle_path=Path("review_bundle"),
        generated_files=[],
        pytest_passed=True,
        ruff_passed=True,
        strict_clean_passed=True,
    )
    monkeypatch.setattr(fs, "create_review_bundle_with_runner", lambda p, s, cr: dummy_rb)


def test_legacy_role_agent_story_no_local_evidence(tmp_path: Path, monkeypatch):
    # Ensure legacy behavior isn't broken
    project_path, story, story_path, manifest_data = setup_dummy_project(tmp_path)
    mock_validators(monkeypatch, manifest_data)
    
    # We don't record local execution. Just finalize story.
    result = finalize_story(project_path, story)
    assert result.ready_for_review is True
    
    # It updates status.yaml to ready_for_review
    status_data = yaml.safe_load((story_path / "status.yaml").read_text())
    assert status_data["ready_for_review"] is True

def test_complete_lifecycle_integration(tmp_path: Path, monkeypatch):
    project_path, story, story_path, manifest_data = setup_dummy_project(tmp_path)
    mock_validators(monkeypatch, manifest_data)
    
    # 1. Record Execution
    exec_result = record_local_execution(project_path, story, execution_type="manual", executor_name="test-operator")
    assert exec_result.record.execution_mode == "local"
    
    # 2. Try Finalize (should fail because pending review)
    result = finalize_story(project_path, story)
    assert result.ready_for_review is False
    
    # 3. Record Review
    review_result = record_local_review(project_path, story, reviewer="test-reviewer", decision=DECISION_READY_FOR_REVIEW)
    assert review_result.decision.decision == DECISION_READY_FOR_REVIEW
    
    # 4. Finalize Success
    result = finalize_story(project_path, story)
    assert result.ready_for_review is True
    
    status_data = yaml.safe_load((story_path / "status.yaml").read_text())
    assert status_data["ready_for_review"] is True

def test_finalize_story_rejects_missing_decision(tmp_path: Path, monkeypatch):
    project_path, story, story_path, manifest_data = setup_dummy_project(tmp_path)
    mock_validators(monkeypatch, manifest_data)
    record_local_execution(project_path, story)
    
    result = finalize_story(project_path, story)
    assert result.ready_for_review is False

def test_finalize_story_rejects_request_changes(tmp_path: Path, monkeypatch):
    project_path, story, story_path, manifest_data = setup_dummy_project(tmp_path)
    mock_validators(monkeypatch, manifest_data)
    record_local_execution(project_path, story)
    record_local_review(project_path, story, decision="request_changes")
    
    result = finalize_story(project_path, story)
    assert result.ready_for_review is False

def test_finalize_story_rejects_corrupt_record(tmp_path: Path, monkeypatch):
    project_path, story, story_path, manifest_data = setup_dummy_project(tmp_path)
    mock_validators(monkeypatch, manifest_data)
    record_local_execution(project_path, story)
    record_local_review(project_path, story, decision="ready_for_review")
    
    # Corrupt execution record
    (story_path / "reports" / "local_execution_record.yaml").write_text("corrupt: yaml: :")
    
    with pytest.raises(ValueError):
        finalize_story(project_path, story)

def test_finalize_story_rejects_stale_record(tmp_path: Path, monkeypatch):
    project_path, story, story_path, manifest_data = setup_dummy_project(tmp_path)
    mock_validators(monkeypatch, manifest_data)
    record_local_execution(project_path, story)
    record_local_review(project_path, story, decision="ready_for_review")
    
    # Modify manifest to simulate stale record
    manifest_data["repository"]["head_sha"] = "different_sha"
    
    with pytest.raises(ValueError):
        finalize_story(project_path, story)

