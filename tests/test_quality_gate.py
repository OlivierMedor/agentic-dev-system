from pathlib import Path

import pytest
import yaml

from agentic_dev.quality_gate import READY_FOR_REVIEW, REQUEST_CHANGES, run_quality_gate


def create_complete_story(project_path: Path, story: str = "story_005_quality_gate") -> Path:
    story_path = project_path / "stories" / story
    reports_path = story_path / "reports"
    review_bundle_path = story_path / "review_bundle"
    reports_path.mkdir(parents=True)
    review_bundle_path.mkdir()

    for filename in [
        "story.md",
        "status.yaml",
        "test_plan.yaml",
        "monitoring_plan.yaml",
        "agent_plan.yaml",
    ]:
        (story_path / filename).write_text(f"{filename}: present\n", encoding="utf-8")

    (reports_path / "developer_report.md").write_text(
        "# Developer Report\n",
        encoding="utf-8",
    )
    (reports_path / "test_report.md").write_text("# Test Report\n", encoding="utf-8")
    (reports_path / "local_review_report.md").write_text(
        "Status: READY_FOR_REVIEW\n",
        encoding="utf-8",
    )

    (review_bundle_path / "handoff.md").write_text("# Handoff\n", encoding="utf-8")
    (review_bundle_path / "pytest_output.txt").write_text(
        "12 passed in 0.34s\n",
        encoding="utf-8",
    )
    (review_bundle_path / "ruff_output.txt").write_text(
        "All checks passed!\n",
        encoding="utf-8",
    )

    return story_path


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def assert_request_changes_for_missing_file(
    tmp_path: Path,
    relative_path: str,
    expected_message: str,
) -> None:
    story = "story_005_quality_gate"
    story_path = create_complete_story(tmp_path, story)
    (story_path / relative_path).unlink()

    result = run_quality_gate(tmp_path, story)

    assert result.status == REQUEST_CHANGES
    assert result.ready_for_review is False
    assert expected_message in result.failed_checks


def test_quality_gate_creates_result_yaml_and_report(tmp_path: Path) -> None:
    story = "story_005_quality_gate"
    story_path = create_complete_story(tmp_path, story)

    result = run_quality_gate(tmp_path, story)

    assert result.result_path == story_path / "reports" / "quality_gate_result.yaml"
    assert result.report_path == story_path / "reports" / "quality_gate_report.md"
    assert result.result_path.exists()
    assert result.report_path.exists()

    yaml_result = read_yaml(result.result_path)
    markdown_report = result.report_path.read_text(encoding="utf-8")

    assert yaml_result["story"] == story
    assert yaml_result["status"] == READY_FOR_REVIEW
    assert "## Final status" in markdown_report
    assert READY_FOR_REVIEW in markdown_report


def test_complete_story_with_passing_evidence_returns_ready_for_review(
    tmp_path: Path,
) -> None:
    story = "story_005_quality_gate"
    create_complete_story(tmp_path, story)

    result = run_quality_gate(tmp_path, story)

    assert result.status == READY_FOR_REVIEW
    assert result.ready_for_review is True
    assert result.failed_checks == []


def test_missing_story_folder_raises_clear_error(tmp_path: Path) -> None:
    missing_story = "missing_story"

    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        run_quality_gate(tmp_path, missing_story)

    assert missing_story in str(error.value)


def test_missing_agent_plan_returns_request_changes(tmp_path: Path) -> None:
    assert_request_changes_for_missing_file(
        tmp_path,
        "agent_plan.yaml",
        "Missing required file: agent_plan.yaml",
    )


def test_missing_required_report_returns_request_changes(tmp_path: Path) -> None:
    assert_request_changes_for_missing_file(
        tmp_path,
        "reports/test_report.md",
        "Missing required file: reports/test_report.md",
    )


def test_failing_pytest_output_returns_request_changes(tmp_path: Path) -> None:
    story = "story_005_quality_gate"
    story_path = create_complete_story(tmp_path, story)
    (story_path / "review_bundle" / "pytest_output.txt").write_text(
        "1 failed, 11 passed in 0.34s\n",
        encoding="utf-8",
    )

    result = run_quality_gate(tmp_path, story)

    assert result.status == REQUEST_CHANGES
    assert "pytest output does not clearly show a passing result." in result.failed_checks


def test_failing_ruff_output_returns_request_changes(tmp_path: Path) -> None:
    story = "story_005_quality_gate"
    story_path = create_complete_story(tmp_path, story)
    (story_path / "review_bundle" / "ruff_output.txt").write_text(
        "Found 2 errors.\n",
        encoding="utf-8",
    )

    result = run_quality_gate(tmp_path, story)

    assert result.status == REQUEST_CHANGES
    assert "Ruff output does not clearly show a passing result." in result.failed_checks


def test_local_review_without_ready_for_review_returns_request_changes(
    tmp_path: Path,
) -> None:
    story = "story_005_quality_gate"
    story_path = create_complete_story(tmp_path, story)
    (story_path / "reports" / "local_review_report.md").write_text(
        "Status: REQUEST_CHANGES\n",
        encoding="utf-8",
    )

    result = run_quality_gate(tmp_path, story)

    assert result.status == REQUEST_CHANGES
    assert "Local reviewer report does not contain READY_FOR_REVIEW." in result.failed_checks


def test_failed_checks_are_listed_clearly(tmp_path: Path) -> None:
    story = "story_005_quality_gate"
    story_path = create_complete_story(tmp_path, story)
    (story_path / "agent_plan.yaml").unlink()
    (story_path / "reports" / "test_report.md").unlink()
    (story_path / "review_bundle" / "pytest_output.txt").write_text(
        "1 failed in 0.12s\n",
        encoding="utf-8",
    )

    result = run_quality_gate(tmp_path, story)
    yaml_result = read_yaml(result.result_path)
    markdown_report = result.report_path.read_text(encoding="utf-8")

    expected_failures = [
        "Missing required file: agent_plan.yaml",
        "Missing required file: reports/test_report.md",
        "pytest output does not clearly show a passing result.",
    ]

    assert result.status == REQUEST_CHANGES
    for failure in expected_failures:
        assert failure in result.failed_checks
        assert failure in yaml_result["failed_checks"]
        assert f"- {failure}" in markdown_report
