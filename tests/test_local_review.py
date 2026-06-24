from pathlib import Path
import yaml
import pytest

from agentic_dev.local_review import record_local_review
from agentic_dev.local_execution_recording import DECISION_READY_FOR_REVIEW
from agentic_dev.review_state.service import ReviewBundleValidation
import agentic_dev.local_review as lr

def setup_dummy_review(tmp_path: Path):
    project_path = tmp_path / "project"
    story = "067-test-story"
    story_path = project_path / "stories" / story
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir(parents=True, exist_ok=True)
    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    manifest_data = {
        "repository": {"head_sha": "abcd123"},
        "integrity": {"evidence_checksums": {"committed_patch": "fake"}},
    }
    manifest_path = review_bundle_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest_data))

    execution_record = {
        "schema_version": 1,
        "repository": {"head_sha": "abcd123"},
        "review_evidence": {"manifest_checksum": "dummy"},
        "integrity": {"record_checksum": "dummy-record-checksum"}
    }
    (reports_path / "local_execution_record.yaml").write_text(yaml.safe_dump(execution_record))
    
    return project_path, story, story_path, manifest_data

def test_record_local_review_idempotency(tmp_path: Path, monkeypatch) -> None:
    project_path, story, story_path, manifest_data = setup_dummy_review(tmp_path)

    monkeypatch.setattr(lr, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=True, reasons=[], manifest=manifest_data, manifest_path=None, checksum_path=None))
    monkeypatch.setattr(lr, "checksum_text", lambda t: "dummy")
    
    result1 = record_local_review(project_path, story, reviewer="test-reviewer", decision=DECISION_READY_FOR_REVIEW)
    checksum1 = result1.decision.attestation_checksum
    
    result2 = record_local_review(project_path, story, reviewer="test-reviewer", decision=DECISION_READY_FOR_REVIEW)
    checksum2 = result2.decision.attestation_checksum
    
    assert checksum1 == checksum2

def test_record_local_review_dry_run_no_mutation(tmp_path: Path, monkeypatch) -> None:
    project_path, story, story_path, manifest_data = setup_dummy_review(tmp_path)

    monkeypatch.setattr(lr, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=True, reasons=[], manifest=manifest_data, manifest_path=None, checksum_path=None))
    monkeypatch.setattr(lr, "checksum_text", lambda t: "dummy")
    
    record_local_review(project_path, story, reviewer="test-reviewer", decision=DECISION_READY_FOR_REVIEW, dry_run=True)
    
    assert not (story_path / "reports" / "local_review_decision.yaml").exists()

def test_record_local_review_rejects_missing_record(tmp_path: Path, monkeypatch):
    project_path, story, story_path, manifest_data = setup_dummy_review(tmp_path)
    monkeypatch.setattr(lr, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=True, reasons=[], manifest=manifest_data, manifest_path=None, checksum_path=None))
    (story_path / "reports" / "local_execution_record.yaml").unlink()
    
    with pytest.raises(FileNotFoundError, match="not found"):
        record_local_review(project_path, story, reviewer="test", decision=DECISION_READY_FOR_REVIEW)

