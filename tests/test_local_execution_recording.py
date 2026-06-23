from pathlib import Path

import yaml

from agentic_dev.local_execution_recording import (
    DECISION_READY_FOR_REVIEW,
    LOCAL_EXECUTION_RECORD_FILENAME,
    record_local_execution,
)
from agentic_dev.local_review import record_local_review


def test_record_local_execution_dry_run(tmp_path: Path) -> None:
    # Setup dummy project and story
    project_path = tmp_path / "project"
    story = "067-test-story"
    story_path = project_path / "stories" / story
    review_bundle_path = story_path / "review_bundle"
    validation_path = review_bundle_path / "validation"
    validation_path.mkdir(parents=True, exist_ok=True)
    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    # Write dummy evidence
    validation_path.joinpath("pytest_output.txt").write_text("=== 1 passed ===")
    validation_path.joinpath("ruff_output.txt").write_text("All checks passed!")

    # Write dummy manifest
    manifest_data = {
        "repository": {
            "branch": "story/067",
            "head_sha": "abcd123",
            "base_sha": "1234abcd",
        },
        "working_tree": {"classification": "clean"},
        "validation": {"strict_clean_passed": True},
        "integrity": {"evidence_checksums": {}},
    }
    manifest_path = review_bundle_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest_data))

    # Mock validate_review_bundle to avoid needing real git/manifest checks
    # For now, we assume tests handle full integration or we mock the validation
    # This is a basic test skeleton
    from agentic_dev.review_state.service import ReviewBundleValidationResult
    import agentic_dev.local_execution_recording as ler

    # We mock validate_review_bundle for the dry run test
    original_validate = ler.validate_review_bundle
    ler.validate_review_bundle = lambda p, s, base_ref=None: ReviewBundleValidationResult(valid=True, reasons=[], manifest=manifest_data)
    
    try:
        result = record_local_execution(
            project_path, story, execution_type="manual", executor_name="test-operator", dry_run=True
        )
        assert result.dry_run is True
        assert result.record.executor == "test-operator"
        assert result.record.evidence_derived is True
    finally:
        ler.validate_review_bundle = original_validate


def test_record_local_review_decision(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    story = "067-test-story"
    story_path = project_path / "stories" / story
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir(parents=True, exist_ok=True)
    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    manifest_data = {
        "repository": {"head_sha": "abcd123"},
        "integrity": {"evidence_checksums": {}},
    }
    manifest_path = review_bundle_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest_data))

    # Mock the execution record
    execution_record = {
        "schema_version": 1,
        "repository": {"head_sha": "abcd123"},
        "review_evidence": {"manifest_checksum": "dummy"},
        "integrity": {"record_checksum": "dummy-record-checksum"}
    }
    (reports_path / LOCAL_EXECUTION_RECORD_FILENAME).write_text(yaml.safe_dump(execution_record))

    import agentic_dev.local_review as lr
    from agentic_dev.review_state.service import ReviewBundleValidationResult
    original_validate = lr.validate_review_bundle
    lr.validate_review_bundle = lambda p, s, base_ref=None: ReviewBundleValidationResult(valid=True, reasons=[], manifest=manifest_data)
    
    # Also mock checksum_text so manifest_checksum matches
    original_checksum = lr.checksum_text
    lr.checksum_text = lambda t: "dummy"
    
    try:
        result = record_local_review(
            project_path, story, reviewer="test-reviewer", decision=DECISION_READY_FOR_REVIEW
        )
        assert result.decision.decision == DECISION_READY_FOR_REVIEW
        assert result.decision.reviewer == "test-reviewer"
        assert result.decision_path.exists()
    finally:
        lr.validate_review_bundle = original_validate
        lr.checksum_text = original_checksum
