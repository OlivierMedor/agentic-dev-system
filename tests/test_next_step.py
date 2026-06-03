import os
from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.next_step import NextStepResult, run_next_step


STORY = "story_026_story_next_step_advisor"


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def create_story(project_path: Path, status_data: dict | None = None) -> Path:
    story_path = project_path / "stories" / STORY
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# STORY-026\n", encoding="utf-8")
    write_yaml(
        story_path / "status.yaml",
        status_data
        or {
            "story_id": "STORY-026",
            "status": "in_progress",
            "ready_for_review": False,
        },
    )
    return story_path


def create_agent_plan(story_path: Path) -> None:
    write_yaml(
        story_path / "agent_plan.yaml",
        {
            "story": STORY,
            "agents": [
                {"name": "developer_agent"},
                {"name": "test_agent"},
                {"name": "local_reviewer_agent"},
            ],
        },
    )


def create_prompt_pack(story_path: Path) -> None:
    prompt_pack_path = story_path / "prompt_pack"
    prompt_pack_path.mkdir()
    (prompt_pack_path / "03_developer_agent_prompt.md").write_text(
        "# Developer Agent Prompt\n",
        encoding="utf-8",
    )
    (prompt_pack_path / "04_test_agent_prompt.md").write_text(
        "# Test Agent Prompt\n",
        encoding="utf-8",
    )
    (prompt_pack_path / "07_local_reviewer_agent_prompt.md").write_text(
        "# Local Reviewer Agent Prompt\n",
        encoding="utf-8",
    )


def write_required_agent_reports(story_path: Path) -> None:
    reports_path = story_path / "reports"
    reports_path.mkdir(exist_ok=True)
    (reports_path / "developer_report.md").write_text("# Developer Report\n", encoding="utf-8")
    (reports_path / "test_report.md").write_text("# Test Report\n", encoding="utf-8")
    (reports_path / "local_review_report.md").write_text(
        "# Local Review Report\n",
        encoding="utf-8",
    )


def prepare_prompted_story(story_path: Path) -> None:
    create_agent_plan(story_path)
    create_prompt_pack(story_path)


def prepare_reported_story(story_path: Path) -> None:
    prepare_prompted_story(story_path)
    write_required_agent_reports(story_path)


def write_ready_finalize_result(story_path: Path) -> None:
    write_yaml(
        story_path / "reports" / "finalize_story_result.yaml",
        {"status": "ready_for_review", "ready_for_review": True},
    )


def write_cloud_review_export(story_path: Path) -> None:
    export_path = story_path / "cloud_review_packet" / "cloud_review_export.md"
    export_path.parent.mkdir()
    export_path.write_text("# Cloud Review Export\n", encoding="utf-8")


def write_cloud_review_result(story_path: Path) -> None:
    write_yaml(
        story_path / "reports" / "cloud_review_result.yaml",
        {
            "decision": "APPROVE",
            "ready_for_human_merge_decision": True,
        },
    )


def write_merge_readiness_result(
    story_path: Path,
    status: str = "READY_FOR_HUMAN_MERGE_DECISION",
) -> None:
    write_yaml(
        story_path / "reports" / "merge_readiness_result.yaml",
        {
            "status": status,
            "ready_for_human_merge_decision": True,
        },
    )


def write_remote_dev_validation_result(
    story_path: Path,
    validation_status: str = "DEV_VALIDATED",
) -> None:
    write_yaml(
        story_path / "reports" / "remote_dev_validation_result.yaml",
        {
            "validation_status": validation_status,
            "ready_for_review": validation_status != "DEV_FAILED",
        },
    )


def prepare_finalized_story(story_path: Path) -> None:
    prepare_reported_story(story_path)
    write_ready_finalize_result(story_path)


def prepare_cloud_reviewed_story(story_path: Path) -> None:
    prepare_finalized_story(story_path)
    write_cloud_review_export(story_path)
    write_cloud_review_result(story_path)


def recommendation_text(result: NextStepResult) -> str:
    recommendation = result.recommendation
    return "\n".join(
        [
            recommendation.title,
            recommendation.command or "",
            recommendation.reason,
            *recommendation.details,
        ],
    )


def test_next_step_validates_story_folder_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        run_next_step(tmp_path, STORY)

    assert STORY in str(error.value)


def test_missing_agent_plan_recommends_prepare_story(tmp_path: Path) -> None:
    create_story(tmp_path)

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Run prepare-story."
    assert result.recommendation.command == f"agentic prepare-story --story {STORY}"
    assert "agent_plan.yaml present: no" in result.recommendation.details


def test_missing_prompt_pack_recommends_prepare_story(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    create_agent_plan(story_path)

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Run prepare-story."
    assert result.recommendation.command == f"agentic prepare-story --story {STORY}"
    assert "prompt_pack present: no" in result.recommendation.details


def test_prompts_without_required_reports_recommend_configured_agent_runtime(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_prompted_story(story_path)

    result = run_next_step(tmp_path, STORY)
    text = recommendation_text(result)

    assert result.recommendation.title == "Run the generated agent prompts."
    assert result.recommendation.command is None
    assert "Missing required reports:" in result.recommendation.details[0]
    assert "developer_report.md" in text
    assert "test_report.md" in text
    assert "local_review_report.md" in text
    assert "configured agent runtime" in text
    assert "Codex" not in text


def test_test_layers_version_one_without_result_recommends_test_layers(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_reported_story(story_path)
    write_yaml(story_path / "test_plan.yaml", {"test_layers_version": 1})

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Run test-layers."
    assert result.recommendation.command == f"agentic test-layers --story {STORY}"
    assert "test_layers_version: 1" in result.recommendation.reason


def test_missing_finalize_result_recommends_finalize_story(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    prepare_reported_story(story_path)

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Run finalize-story."
    assert result.recommendation.command == f"agentic finalize-story --story {STORY}"
    assert "Finalize evidence is missing" in result.recommendation.reason


def test_stale_finalize_result_recommends_finalize_story(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    prepare_reported_story(story_path)
    write_ready_finalize_result(story_path)
    finalize_path = story_path / "reports" / "finalize_story_result.yaml"
    developer_report_path = story_path / "reports" / "developer_report.md"
    stale_time = finalize_path.stat().st_mtime - 10
    new_time = finalize_path.stat().st_mtime + 10

    os.utime(finalize_path, (stale_time, stale_time))
    os.utime(developer_report_path, (new_time, new_time))

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Run finalize-story."
    assert "changed after the last finalize result" in result.recommendation.reason


def test_ready_finalize_without_cloud_review_export_recommends_cloud_review_packet(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_finalized_story(story_path)

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Run cloud-review-packet."
    assert result.recommendation.command == f"agentic cloud-review-packet --story {STORY}"
    assert "cloud review export packet does not exist" in result.recommendation.reason


def test_final_review_bundle_newer_than_finalize_result_does_not_force_refinalize(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_finalized_story(story_path)
    finalize_path = story_path / "reports" / "finalize_story_result.yaml"
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir()
    handoff_path = review_bundle_path / "handoff.md"
    handoff_path.write_text("# Handoff\n", encoding="utf-8")
    new_time = finalize_path.stat().st_mtime + 10

    os.utime(handoff_path, (new_time, new_time))

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Run cloud-review-packet."
    assert result.recommendation.command == f"agentic cloud-review-packet --story {STORY}"


def test_cloud_review_export_without_result_recommends_record_cloud_review(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_finalized_story(story_path)
    write_cloud_review_export(story_path)

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Record the cloud review result."
    assert result.recommendation.command == (
        f"agentic record-cloud-review --story {STORY} --result-file <path>"
    )
    assert "manual cloud review decision" in result.recommendation.reason


def test_cloud_review_result_without_merge_readiness_recommends_merge_readiness(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_cloud_reviewed_story(story_path)

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Run merge-readiness."
    assert result.recommendation.command == f"agentic merge-readiness --story {STORY}"
    assert "merge readiness has not been checked" in result.recommendation.reason


def test_merge_readiness_without_remote_dev_validation_recommends_remote_dev_packet(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_cloud_reviewed_story(story_path)
    write_merge_readiness_result(story_path)

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Run remote-dev-packet."
    assert result.recommendation.command == f"agentic remote-dev-packet --story {STORY}"
    assert "remote dev validation is not recorded" in result.recommendation.reason


def test_remote_dev_validated_recommends_human_pr_ci_review(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    prepare_cloud_reviewed_story(story_path)
    write_merge_readiness_result(story_path)
    write_remote_dev_validation_result(story_path, "DEV_VALIDATED")

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Human PR/CI review is next."
    assert result.recommendation.command is None
    assert "human review" in result.recommendation.reason
    assert "Human final approval is always required before merge." in result.recommendation.details


def test_request_changes_status_recommends_fixing_failed_checks(tmp_path: Path) -> None:
    create_story(tmp_path, {"story_id": "STORY-026", "status": "request_changes"})

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Fix failed checks before continuing."
    assert result.recommendation.command is None
    assert "request changes" in result.recommendation.reason
    assert "status.yaml status is request_changes." in result.recommendation.details


def test_blocked_status_recommends_reviewing_support_ticket(tmp_path: Path) -> None:
    create_story(
        tmp_path,
        {
            "story_id": "STORY-026",
            "status": "blocked",
            "blocked_by": "SUPPORT-20260603-120000",
        },
    )

    result = run_next_step(tmp_path, STORY)

    assert result.recommendation.title == "Review the blocking support ticket."
    assert result.recommendation.command is None
    assert "This story is blocked" in result.recommendation.reason
    assert "SUPPORT-20260603-120000" in result.recommendation.details[0]


def test_next_step_report_is_written_and_recommendation_avoids_automatic_merge(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_cloud_reviewed_story(story_path)
    write_merge_readiness_result(story_path)
    write_remote_dev_validation_result(story_path)

    result = run_next_step(tmp_path, STORY)

    assert result.report_path == story_path / "reports" / "next_step_report.md"
    assert result.report_path.exists()
    report = result.report_path.read_text(encoding="utf-8")
    assert "# Next Step Report" in report
    assert "Human PR/CI review is next." in report
    assert "Human final approval is always required before merge." in report
    assert "automatic merge" not in recommendation_text(result).lower()


def test_cli_next_step_requires_story_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "next-step"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_next_step_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    story_path = create_story(tmp_path)
    prepare_reported_story(story_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "next-step", "--story", STORY])

    main()

    captured = capsys.readouterr()
    assert f"Next step for {STORY}:" in captured.out
    assert "Recommendation: Run finalize-story." in captured.out
    assert (story_path / "reports" / "next_step_report.md").exists()
