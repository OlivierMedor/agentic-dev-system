from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.cloud_review_result import extract_decision, record_cloud_review


STORY = "story_016_cloud_review_result_recording"
PRESERVED_STORY_ID = "STORY-016"


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# STORY-016\n", encoding="utf-8")
    (story_path / "status.yaml").write_text(
        yaml.safe_dump(
            {
                "story_id": PRESERVED_STORY_ID,
                "status": "ready_for_review",
                "ready_for_review": True,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return story_path


def write_cloud_review_result(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("decision", "expected_status", "expected_ready_for_review", "expected_human_ready"),
    [
        ("APPROVE", "cloud_review_approved", True, True),
        ("APPROVE_WITH_NOTES", "cloud_review_approved_with_notes", True, True),
        ("REQUEST_CHANGES", "request_changes", False, False),
    ],
)
def test_record_cloud_review_writes_reports_and_updates_status(
    tmp_path: Path,
    decision: str,
    expected_status: str,
    expected_ready_for_review: bool,
    expected_human_ready: bool,
) -> None:
    story_path = create_story(tmp_path)
    result_file = write_cloud_review_result(
        tmp_path / "cloud_answer.md",
        f"Decision: {decision}\n\nRationale from the main cloud model.\n",
    )

    result = record_cloud_review(tmp_path, STORY, result_file)

    result_yaml_path = story_path / "reports" / "cloud_review_result.yaml"
    report_path = story_path / "reports" / "cloud_review_report.md"
    status_path = story_path / "status.yaml"

    assert result.decision == decision
    assert result.ready_for_human_merge_decision is expected_human_ready
    assert result.cloud_review_result_path == result_yaml_path
    assert result.cloud_review_report_path == report_path
    assert result.status_path == status_path

    result_yaml = yaml.safe_load(result_yaml_path.read_text(encoding="utf-8"))
    assert result_yaml["story"] == STORY
    assert result_yaml["decision"] == decision
    assert result_yaml["ready_for_human_merge_decision"] is expected_human_ready

    report = report_path.read_text(encoding="utf-8")
    assert "# Cloud Review Report" in report
    assert decision in report
    assert "This command did not call cloud models, commit, push, merge, or deploy." in report
    assert "Rationale from the main cloud model." in report

    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    assert status["story_id"] == PRESERVED_STORY_ID
    assert status["status"] == expected_status
    assert status["ready_for_review"] is expected_ready_for_review
    assert status["cloud_review_decision"] == decision


def test_extract_decision_accepts_decision_on_own_line() -> None:
    assert extract_decision("Review complete.\n\nAPPROVE_WITH_NOTES\n\nNo blockers.\n") == (
        "APPROVE_WITH_NOTES"
    )


def test_record_cloud_review_validates_story_folder_exists(tmp_path: Path) -> None:
    result_file = write_cloud_review_result(tmp_path / "cloud_answer.md", "Decision: APPROVE\n")

    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        record_cloud_review(tmp_path, STORY, result_file)

    assert STORY in str(error.value)


def test_record_cloud_review_validates_result_file_exists(tmp_path: Path) -> None:
    create_story(tmp_path)

    with pytest.raises(FileNotFoundError, match="Cloud review result file does not exist"):
        record_cloud_review(tmp_path, STORY, tmp_path / "missing_result.md")


def test_extract_decision_requires_a_decision() -> None:
    with pytest.raises(ValueError, match="Missing cloud review decision"):
        extract_decision("The review is complete, but no accepted decision was provided.\n")


def test_extract_decision_rejects_ambiguous_multiple_decisions() -> None:
    with pytest.raises(ValueError, match="Ambiguous cloud review decision"):
        extract_decision("Decision: APPROVE\n\nREQUEST_CHANGES\n")


def test_cli_record_cloud_review_requires_story_argument(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result_file = write_cloud_review_result(tmp_path / "cloud_answer.md", "Decision: APPROVE\n")
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "record-cloud-review", "--result-file", str(result_file)],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_record_cloud_review_requires_result_file_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "record-cloud-review", "--story", STORY])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_record_cloud_review_defaults_project_to_cwd_without_git_or_cloud_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    result_file = write_cloud_review_result(tmp_path / "cloud_answer.md", "APPROVE\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "record-cloud-review", "--story", STORY, "--result-file", str(result_file)],
    )

    main()

    status = yaml.safe_load((story_path / "status.yaml").read_text(encoding="utf-8"))
    assert not (tmp_path / ".git").exists()
    assert (story_path / "reports" / "cloud_review_result.yaml").exists()
    assert (story_path / "reports" / "cloud_review_report.md").exists()
    assert status["status"] == "cloud_review_approved"
    assert status["ready_for_review"] is True
