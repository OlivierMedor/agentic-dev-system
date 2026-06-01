from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.merge_readiness import run_merge_readiness


STORY = "story_017_merge_readiness_gate"
PRESERVED_STORY_ID = "STORY-017"


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True)
    (story_path / "status.yaml").write_text(
        yaml.safe_dump(
            {
                "story_id": PRESERVED_STORY_ID,
                "status": "cloud_review_approved",
                "ready_for_review": True,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return story_path


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_passing_local_evidence(story_path: Path) -> None:
    reports_path = story_path / "reports"
    write_yaml(
        reports_path / "quality_gate_result.yaml",
        {
            "status": "READY_FOR_REVIEW",
            "ready_for_review": True,
        },
    )
    write_yaml(
        reports_path / "finalize_story_result.yaml",
        {
            "status": "ready_for_review",
            "ready_for_review": True,
        },
    )
    write_yaml(
        reports_path / "test_layer_result.yaml",
        {
            "status": "PASSED",
        },
    )


def write_cloud_review_decision(story_path: Path, decision: str) -> None:
    write_yaml(
        story_path / "reports" / "cloud_review_result.yaml",
        {
            "story": STORY,
            "decision": decision,
            "ready_for_human_merge_decision": decision != "REQUEST_CHANGES",
        },
    )


@pytest.mark.parametrize(
    ("decision", "expected_status", "expected_status_text", "expected_ready"),
    [
        (
            "APPROVE",
            "READY_FOR_HUMAN_MERGE_DECISION",
            "ready_for_human_merge_decision",
            True,
        ),
        (
            "APPROVE_WITH_NOTES",
            "READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION",
            "ready_with_notes_for_human_merge_decision",
            True,
        ),
        (
            "REQUEST_CHANGES",
            "REQUEST_CHANGES",
            "request_changes",
            False,
        ),
    ],
)
def test_merge_readiness_writes_reports_and_decides_from_cloud_review(
    tmp_path: Path,
    decision: str,
    expected_status: str,
    expected_status_text: str,
    expected_ready: bool,
) -> None:
    story_path = create_story(tmp_path)
    write_passing_local_evidence(story_path)
    write_cloud_review_decision(story_path, decision)

    result = run_merge_readiness(tmp_path, STORY)

    result_path = story_path / "reports" / "merge_readiness_result.yaml"
    report_path = story_path / "reports" / "merge_readiness_report.md"
    status_path = story_path / "status.yaml"

    assert result.status == expected_status
    assert result.ready_for_human_merge_decision is expected_ready
    assert result.cloud_review_decision == decision
    assert result.result_path == result_path
    assert result.report_path == report_path
    assert result.status_path == status_path

    result_yaml = read_yaml(result_path)
    assert result_yaml["story"] == STORY
    assert result_yaml["status"] == expected_status
    assert result_yaml["ready_for_human_merge_decision"] is expected_ready
    assert result_yaml["cloud_review_decision"] == decision

    report = report_path.read_text(encoding="utf-8")
    assert "# Merge Readiness Report" in report
    assert expected_status in report
    assert decision in report
    assert "This command did not commit, push, merge, deploy, or call cloud models." in report

    status = read_yaml(status_path)
    assert status["story_id"] == PRESERVED_STORY_ID
    assert status["status"] == expected_status_text
    assert status["ready_for_review"] is expected_ready
    assert status["merge_readiness_status"] == expected_status
    assert status["ready_for_human_merge_decision"] is expected_ready
    assert status["cloud_review_decision"] == decision


@pytest.mark.parametrize(
    ("missing_file", "expected_failed_check"),
    [
        (
            "cloud_review_result.yaml",
            "Missing required evidence: reports/cloud_review_result.yaml.",
        ),
        (
            "quality_gate_result.yaml",
            "Missing required evidence: reports/quality_gate_result.yaml.",
        ),
        (
            "finalize_story_result.yaml",
            "Missing required evidence: reports/finalize_story_result.yaml.",
        ),
    ],
)
def test_merge_readiness_requests_changes_when_required_evidence_is_missing(
    tmp_path: Path,
    missing_file: str,
    expected_failed_check: str,
) -> None:
    story_path = create_story(tmp_path)
    write_passing_local_evidence(story_path)
    write_cloud_review_decision(story_path, "APPROVE")
    (story_path / "reports" / missing_file).unlink()

    result = run_merge_readiness(tmp_path, STORY)
    result_yaml = read_yaml(story_path / "reports" / "merge_readiness_result.yaml")
    status = read_yaml(story_path / "status.yaml")

    assert result.status == "REQUEST_CHANGES"
    assert result.ready_for_human_merge_decision is False
    assert result_yaml["status"] == "REQUEST_CHANGES"
    assert expected_failed_check in result_yaml["failed_checks"]
    assert status["story_id"] == PRESERVED_STORY_ID
    assert status["status"] == "request_changes"
    assert status["ready_for_human_merge_decision"] is False


def test_merge_readiness_requests_changes_when_test_layer_result_fails(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    write_passing_local_evidence(story_path)
    write_cloud_review_decision(story_path, "APPROVE")
    write_yaml(story_path / "reports" / "test_layer_result.yaml", {"status": "FAILED"})

    result = run_merge_readiness(tmp_path, STORY)
    result_yaml = read_yaml(story_path / "reports" / "merge_readiness_result.yaml")

    assert result.status == "REQUEST_CHANGES"
    assert result.ready_for_human_merge_decision is False
    assert result_yaml["status"] == "REQUEST_CHANGES"
    assert "Test layer result exists and must have status PASSED." in result_yaml[
        "failed_checks"
    ]


def test_merge_readiness_validates_story_folder_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        run_merge_readiness(tmp_path, STORY)

    assert STORY in str(error.value)


def test_merge_readiness_does_not_require_real_git_repo_or_cloud_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    write_passing_local_evidence(story_path)
    write_cloud_review_decision(story_path, "APPROVE")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert not (tmp_path / ".git").exists()

    run_merge_readiness(tmp_path, STORY)

    assert not (tmp_path / ".git").exists()
    assert (story_path / "reports" / "merge_readiness_result.yaml").exists()
    assert (story_path / "reports" / "merge_readiness_report.md").exists()


def test_cli_merge_readiness_requires_story_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "merge-readiness"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_merge_readiness_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    write_passing_local_evidence(story_path)
    write_cloud_review_decision(story_path, "APPROVE")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "merge-readiness", "--story", STORY])

    main()

    result_yaml = read_yaml(story_path / "reports" / "merge_readiness_result.yaml")
    assert result_yaml["status"] == "READY_FOR_HUMAN_MERGE_DECISION"
    assert (story_path / "reports" / "merge_readiness_report.md").exists()
