from pathlib import Path
import yaml
import pytest

from agentic_dev.local_execution_recording import (
    record_local_execution,
    LOCAL_EXECUTION_RECORD_FILENAME,
)
from agentic_dev.review_state.service import ReviewBundleValidation
import agentic_dev.local_execution_recording as ler

def setup_dummy_story(tmp_path: Path):
    project_path = tmp_path / "project"
    story = "067-test-story"
    story_path = project_path / "stories" / story
    review_bundle_path = story_path / "review_bundle"
    validation_path = review_bundle_path / "validation"
    validation_path.mkdir(parents=True, exist_ok=True)
    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    validation_path.joinpath("pytest_output.txt").write_text("status: passed")
    validation_path.joinpath("ruff_output.txt").write_text("All checks passed!")

    manifest_data = {
        "repository": {
            "branch": "story/067",
            "head_sha": "abcd123",
            "base_sha": "1234abcd",
        },
        "working_tree": {"classification": "clean"},
        "validation": {"strict_clean_passed": True},
        "integrity": {"evidence_checksums": {"committed_patch": "fake"}},
        "committed_diff": {"commit_count": 1, "patch_checksum": "fake"},
    }
    manifest_path = review_bundle_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest_data))
    
    return project_path, story, story_path, manifest_data

def test_record_local_execution_dry_run_no_mutation(tmp_path: Path, monkeypatch) -> None:
    project_path, story, story_path, manifest_data = setup_dummy_story(tmp_path)
    
    monkeypatch.setattr(ler, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=True, reasons=[], manifest=manifest_data, manifest_path=None, checksum_path=None))
    
    result = record_local_execution(
        project_path, story, execution_type="manual", executor_name="test-operator", dry_run=True
    )
    
    assert result.dry_run is True
    assert not (story_path / "reports" / LOCAL_EXECUTION_RECORD_FILENAME).exists()

def test_record_local_execution_idempotency(tmp_path: Path, monkeypatch) -> None:
    project_path, story, story_path, manifest_data = setup_dummy_story(tmp_path)
    monkeypatch.setattr(ler, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=True, reasons=[], manifest=manifest_data, manifest_path=None, checksum_path=None))
    
    # Run first time
    result1 = record_local_execution(project_path, story, execution_type="manual", executor_name="test-operator")
    checksum1 = result1.record.record_checksum
    
    # Snapshot directory modified times
    # (record_path omitted - we check existence directly below)

    # Run second time
    result2 = record_local_execution(project_path, story, execution_type="manual", executor_name="test-operator")
    checksum2 = result2.record.record_checksum
    
    assert checksum1 == checksum2
    assert (story_path / "reports" / LOCAL_EXECUTION_RECORD_FILENAME).exists()

def test_force_never_bypasses_validation(tmp_path: Path, monkeypatch):
    project_path, story, story_path, manifest_data = setup_dummy_story(tmp_path)
    
    # Make working tree dirty
    manifest_data["working_tree"]["classification"] = "dirty"
    
    monkeypatch.setattr(ler, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=True, reasons=[], manifest=manifest_data, manifest_path=None, checksum_path=None))
    
    with pytest.raises(ValueError, match="not acceptable"):
        record_local_execution(project_path, story, force=True)

def test_stale_head_rejection_no_mutation(tmp_path: Path, monkeypatch):
    project_path, story, story_path, manifest_data = setup_dummy_story(tmp_path)
    
    # Simulate current HEAD differing from manifest (validate_review_bundle returns valid=False)
    monkeypatch.setattr(ler, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=False, reasons=["does not match current HEAD"], manifest=manifest_data, manifest_path=None, checksum_path=None))
    
    with pytest.raises(ValueError, match="does not match current HEAD"):
        record_local_execution(project_path, story)
        
    assert not (story_path / "reports" / LOCAL_EXECUTION_RECORD_FILENAME).exists()

def test_corrupt_manifest_rejection_no_mutation(tmp_path: Path, monkeypatch):
    project_path, story, story_path, manifest_data = setup_dummy_story(tmp_path)
    
    # Make manifest validation fail
    monkeypatch.setattr(ler, "validate_review_bundle", lambda p, s, base_ref=None: ReviewBundleValidation(valid=False, reasons=["corrupt format"], manifest={}, manifest_path=None, checksum_path=None))
    
    with pytest.raises(ValueError, match="corrupt format"):
        record_local_execution(project_path, story)
        
    assert not (story_path / "reports" / LOCAL_EXECUTION_RECORD_FILENAME).exists()

