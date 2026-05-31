from pathlib import Path

import pytest
import yaml

from agentic_dev import finalize_story as finalize_story_module
from agentic_dev.cli import main
from agentic_dev.finalize_story import finalize_story
from agentic_dev.quality_gate import READY_FOR_REVIEW, REQUEST_CHANGES, QualityGateResult
from agentic_dev.review_bundle import ReviewBundleResult
from agentic_dev.test_layers import TEST_LAYER_PASSED, TestLayerResult as LayerValidationResult


STORY = "story_008_finalize_story_command"


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "status.yaml").write_text(
        f"story_id: {story}\n"
        "status: in_progress\n"
        "ready_for_review: false\n"
        "notes: keep this field\n",
        encoding="utf-8",
    )
    return story_path


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_test_layer_plan(story_path: Path) -> None:
    test_plan = {
        "test_layers_version": 1,
        "unit_tests": {
            "required": True,
            "action": "add_or_update",
            "frequency": "every_commit",
            "evidence_or_reason": "Unit tests were added.",
        },
        "integration_tests": {
            "required": True,
            "action": "confirm_existing",
            "frequency": "every_pull_request",
            "evidence_or_reason": "Existing integration tests apply.",
        },
        "mock_e2e_tests": {
            "required": True,
            "action": "confirm_existing",
            "frequency": "before_merge",
            "evidence_or_reason": "Existing mock E2E tests apply.",
        },
        "live_read_only_checks": {
            "required": False,
            "action": "not_applicable_with_reason",
            "frequency": "scheduled_or_before_release",
            "evidence_or_reason": "No live services are touched.",
        },
        "remote_dev_smoke_tests": {
            "required": False,
            "action": "not_applicable_with_reason",
            "frequency": "after_remote_dev_deploy",
            "evidence_or_reason": "No remote dev environment exists.",
        },
    }
    (story_path / "test_plan.yaml").write_text(
        yaml.safe_dump(test_plan, sort_keys=False),
        encoding="utf-8",
    )


def install_finalize_doubles(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> list[str]:
    calls: list[str] = []

    def fake_create_review_bundle(project_path: Path, story: str) -> ReviewBundleResult:
        calls.append(f"review_bundle:{story}")
        review_bundle_path = project_path.resolve() / "stories" / story / "review_bundle"
        review_bundle_path.mkdir(parents=True, exist_ok=True)
        (review_bundle_path / "handoff.md").write_text(
            f"# Handoff\n\nCall {calls.count(f'review_bundle:{story}')}\n",
            encoding="utf-8",
        )
        return ReviewBundleResult(
            review_bundle_path=review_bundle_path,
            generated_files=[review_bundle_path / "handoff.md"],
            pytest_passed=True,
            ruff_passed=True,
        )

    def fake_run_quality_gate(project_path: Path, story: str) -> QualityGateResult:
        calls.append(f"quality_gate:{story}")
        reports_path = project_path.resolve() / "stories" / story / "reports"
        reports_path.mkdir(parents=True, exist_ok=True)
        result_path = reports_path / "quality_gate_result.yaml"
        report_path = reports_path / "quality_gate_report.md"
        result_path.write_text(f"status: {status}\n", encoding="utf-8")
        report_path.write_text(f"# Quality Gate\n\n{status}\n", encoding="utf-8")
        return QualityGateResult(
            story=story,
            status=status,
            passed_checks=[],
            failed_checks=[] if status == READY_FOR_REVIEW else ["needs work"],
            ready_for_review=status == READY_FOR_REVIEW,
            next_action="Send to review."
            if status == READY_FOR_REVIEW
            else "Fix requested changes.",
            result_path=result_path,
            report_path=report_path,
        )

    monkeypatch.setattr(
        finalize_story_module,
        "create_review_bundle",
        fake_create_review_bundle,
    )
    monkeypatch.setattr(
        finalize_story_module,
        "run_quality_gate",
        fake_run_quality_gate,
    )
    return calls


def test_finalize_story_validates_story_folder_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        finalize_story(tmp_path, STORY)

    assert STORY in str(error.value)


def test_finalize_story_creates_reports_and_regenerates_review_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    calls = install_finalize_doubles(monkeypatch, READY_FOR_REVIEW)

    result = finalize_story(tmp_path, STORY)

    assert calls == [
        f"review_bundle:{STORY}",
        f"quality_gate:{STORY}",
        f"review_bundle:{STORY}",
    ]
    assert result.review_bundle_path == story_path / "review_bundle"
    assert (story_path / "review_bundle" / "handoff.md").exists()
    assert result.finalize_report_path == story_path / "reports" / "finalize_story_report.md"
    assert result.finalize_result_path == story_path / "reports" / "finalize_story_result.yaml"
    assert result.finalize_report_path.exists()
    assert result.finalize_result_path.exists()
    assert result.quality_gate_result_path.exists()
    assert result.quality_gate_report_path.exists()


def test_finalize_story_runs_test_layers_before_quality_gate_when_applicable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    write_test_layer_plan(story_path)
    calls = install_finalize_doubles(monkeypatch, READY_FOR_REVIEW)

    def fake_run_test_layers(project_path: Path, story: str) -> LayerValidationResult:
        calls.append(f"test_layers:{story}")
        reports_path = project_path.resolve() / "stories" / story / "reports"
        reports_path.mkdir(parents=True, exist_ok=True)
        result_path = reports_path / "test_layer_result.yaml"
        report_path = reports_path / "test_layer_report.md"
        result_path.write_text(f"status: {TEST_LAYER_PASSED}\n", encoding="utf-8")
        report_path.write_text("# Test Layer Report\n\nPASSED\n", encoding="utf-8")
        return LayerValidationResult(
            story=story,
            status=TEST_LAYER_PASSED,
            passed_checks=["all layers addressed"],
            failed_checks=[],
            layers={},
            next_action="Continue to quality gate.",
            result_path=result_path,
            report_path=report_path,
        )

    monkeypatch.setattr(finalize_story_module, "run_test_layers", fake_run_test_layers)

    result = finalize_story(tmp_path, STORY)

    assert calls == [
        f"review_bundle:{STORY}",
        f"test_layers:{STORY}",
        f"quality_gate:{STORY}",
        f"review_bundle:{STORY}",
    ]
    assert result.test_layer_result_path == story_path / "reports" / "test_layer_result.yaml"
    assert result.test_layer_result_path.exists()


def test_finalize_story_updates_status_ready_for_review_and_preserves_story_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    install_finalize_doubles(monkeypatch, READY_FOR_REVIEW)

    finalize_story(tmp_path, STORY)

    status = read_yaml(story_path / "status.yaml")
    result = read_yaml(story_path / "reports" / "finalize_story_result.yaml")
    report = (story_path / "reports" / "finalize_story_report.md").read_text(
        encoding="utf-8",
    )

    assert status["story_id"] == STORY
    assert status["status"] == "ready_for_review"
    assert status["ready_for_review"] is True
    assert status["notes"] == "keep this field"
    assert result["status"] == "ready_for_review"
    assert result["ready_for_review"] is True
    assert "Quality gate status: READY_FOR_REVIEW" in report
    assert "Updated `status.yaml` without committing, pushing, merging, deploying" in report
    assert "calling cloud models" in report


def test_finalize_story_updates_status_request_changes_and_preserves_story_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    install_finalize_doubles(monkeypatch, REQUEST_CHANGES)

    finalize_story(tmp_path, STORY)

    status = read_yaml(story_path / "status.yaml")
    result = read_yaml(story_path / "reports" / "finalize_story_result.yaml")
    report = (story_path / "reports" / "finalize_story_report.md").read_text(
        encoding="utf-8",
    )

    assert status["story_id"] == STORY
    assert status["status"] == "request_changes"
    assert status["ready_for_review"] is False
    assert status["notes"] == "keep this field"
    assert result["status"] == "request_changes"
    assert result["ready_for_review"] is False
    assert "Quality gate status: REQUEST_CHANGES" in report


def test_finalize_story_does_not_require_real_git_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    install_finalize_doubles(monkeypatch, READY_FOR_REVIEW)

    assert not (tmp_path / ".git").exists()

    finalize_story(tmp_path, STORY)

    assert (story_path / "reports" / "finalize_story_report.md").exists()


def test_cli_finalize_story_requires_story_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "finalize-story"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_finalize_story_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    install_finalize_doubles(monkeypatch, READY_FOR_REVIEW)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "finalize-story", "--story", STORY])

    main()

    assert (story_path / "review_bundle" / "handoff.md").exists()
    assert (story_path / "reports" / "finalize_story_report.md").exists()
    assert (story_path / "reports" / "finalize_story_result.yaml").exists()
