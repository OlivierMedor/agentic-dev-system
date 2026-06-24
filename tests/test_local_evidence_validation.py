from pathlib import Path
from typing import Any

from agentic_dev.local_evidence_validation import validate_local_evidence

def test_evidence_validation_absent(tmp_path: Path):
    result = validate_local_evidence(tmp_path, "missing-story")
    assert not result.execution_record_present
    assert not result.execution_record_valid
    assert not result.review_decision_present
    assert result.decision == "pending"

def test_evidence_validation_malformed(tmp_path: Path):
    story_dir = tmp_path / "stories" / "some-story"
    reports_dir = story_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "local_execution_record.yaml").write_text("not a dict")
    
    result = validate_local_evidence(tmp_path, "some-story")
    assert result.execution_record_present
    assert not result.execution_record_valid
    assert any("corrupt" in r for r in result.failure_reasons)

def test_evidence_validation_manifest_mismatch(tmp_path: Path):
    import agentic_dev.local_evidence_validation as lev
    from agentic_dev.review_state.service import ReviewBundleValidation
    
    original_validate = lev.validate_review_bundle
    lev.validate_review_bundle = lambda p, s, base_ref=None: ReviewBundleValidation(
        valid=True, reasons=[], manifest={"repository": {}}, manifest_path=None, checksum_path=None
    )
    
    try:
        story_dir = tmp_path / "stories" / "some-story"
        reports_dir = story_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "local_execution_record.yaml").write_text("record_checksum: abcd\nmanifest_checksum: wrong\nexecution_mode: local\nexecution_type: manual\nroles_covered: []\n")
        
        bundle_dir = story_dir / "review_bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "manifest.yaml").write_text("key: val")
        
        result = lev.validate_local_evidence(tmp_path, "some-story")
        assert result.execution_record_present
        assert not result.execution_record_valid
        assert any("manifest_checksum does not match canonical manifest" in r for r in result.failure_reasons), f"Reasons: {result.failure_reasons}"
    finally:
        lev.validate_review_bundle = original_validate
