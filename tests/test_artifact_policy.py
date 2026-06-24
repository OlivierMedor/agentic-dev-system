import pytest
import subprocess
from pathlib import Path

def test_generated_evidence_is_ignored(tmp_path: Path):
    project_root = Path(__file__).parent.parent
    files_to_test = [
        "stories/evidence-derived-local-execution-recording/reports/local_execution_record.yaml",
        "stories/evidence-derived-local-execution-recording/reports/local_review_decision.yaml",
        "stories/evidence-derived-local-execution-recording/reports/local_execution_report.md",
        "stories/evidence-derived-local-execution-recording/reports/local_review_report.md",
        "stories/evidence-derived-local-execution-recording/reports/quality_gate_report.md",
        "stories/evidence-derived-local-execution-recording/reports/quality_gate_result.yaml",
        "stories/evidence-derived-local-execution-recording/reports/finalize_story_report.md",
        "stories/evidence-derived-local-execution-recording/reports/finalize_story_result.yaml",
        "stories/evidence-derived-local-execution-recording/cloud_review_packet/cloud_review_prompt.md"
    ]
    for f in files_to_test:
        result = subprocess.run(["git", "check-ignore", "-v", f], cwd=project_root, capture_output=True, text=True)
        assert result.returncode == 0, f"File {f} is not ignored by git"

def test_legacy_evidence_is_not_ignored(tmp_path: Path):
    project_root = Path(__file__).parent.parent
    files_to_test = [
        "stories/evidence-derived-local-execution-recording/reports/developer_report.md",
        "stories/evidence-derived-local-execution-recording/reports/test_report.md",
        "stories/evidence-derived-local-execution-recording/reports/test_layer_report.md",
        "stories/evidence-derived-local-execution-recording/reports/test_layer_result.yaml",
        "stories/evidence-derived-local-execution-recording/cloud_review_packet/.gitkeep"
    ]
    for f in files_to_test:
        result = subprocess.run(["git", "check-ignore", "-v", f], cwd=project_root, capture_output=True, text=True)
        assert result.returncode == 1, f"File {f} is incorrectly ignored by git"
