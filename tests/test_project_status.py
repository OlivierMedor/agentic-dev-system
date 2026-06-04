from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.project_status import collect_story_status, run_project_status
from agentic_dev.queue_management import create_queue_item, set_queue_item_status


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def create_story(project_path: Path, story: str, status_data: dict | None = None) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text(f"# {story}\n", encoding="utf-8")
    if status_data is not None:
        write_yaml(story_path / "status.yaml", status_data)
    return story_path


def test_project_status_collects_all_story_folders_and_writes_report(tmp_path: Path) -> None:
    create_story(tmp_path, "story_alpha", {"story_id": "STORY-A", "status": "planned"})
    create_story(
        tmp_path,
        "story_ready",
        {"story_id": "STORY-B", "status": "ready_for_review", "ready_for_review": True},
    )

    result = run_project_status(tmp_path)

    assert [story.story for story in result.stories] == ["story_alpha", "story_ready"]
    assert result.summary_counts["total"] == 2
    assert result.report_path == tmp_path / "reports" / "project_status_report.md"
    assert result.report_path.exists()
    assert "story_alpha" in result.terminal_summary
    assert "story_ready" in result.terminal_summary

    report = result.report_path.read_text(encoding="utf-8")
    assert "# Project Status Report" in report
    assert "## Safety Notes" in report


def test_project_status_can_filter_to_one_story(tmp_path: Path) -> None:
    create_story(tmp_path, "story_one", {"status": "planned"})
    create_story(tmp_path, "story_two", {"status": "planned"})

    result = run_project_status(tmp_path, story="story_two")

    assert [story.story for story in result.stories] == ["story_two"]
    assert result.summary_counts["total"] == 1
    assert "story_two" in result.terminal_summary
    assert "story_one" not in result.terminal_summary


def test_story_status_reads_status_yaml_when_present(tmp_path: Path) -> None:
    story_path = create_story(
        tmp_path,
        "story_with_status",
        {
            "story_id": "STORY-STATUS",
            "status": "ready_for_review",
            "ready_for_review": True,
        },
    )

    status = collect_story_status(tmp_path, story_path)

    assert status.story_id == "STORY-STATUS"
    assert status.status == "ready_for_review"
    assert status.ready_for_review is True
    assert status.warnings == []


def test_story_status_handles_missing_status_yaml_gracefully(tmp_path: Path) -> None:
    story_path = create_story(tmp_path, "story_without_status")

    status = collect_story_status(tmp_path, story_path)

    assert status.status is None
    assert status.ready_for_review is None
    assert status.category == "NOT_STARTED"
    assert "status.yaml" in status.missing_evidence
    assert status.warnings == []


def test_story_status_handles_malformed_status_yaml_gracefully(tmp_path: Path) -> None:
    story_path = create_story(tmp_path, "story_bad_status")
    (story_path / "status.yaml").write_text("status: [unterminated\n", encoding="utf-8")

    status = collect_story_status(tmp_path, story_path)

    assert status.status is None
    assert status.category == "NOT_STARTED"
    assert status.warnings
    assert "Invalid YAML" in status.warnings[0]


def test_story_status_detects_workflow_evidence_files(tmp_path: Path) -> None:
    story_path = create_story(
        tmp_path,
        "story_evidence",
        {"story_id": "STORY-E", "status": "ready_for_review", "ready_for_review": True},
    )
    (story_path / "agent_plan.yaml").write_text("agents: []\n", encoding="utf-8")
    prompt_pack = story_path / "prompt_pack"
    prompt_pack.mkdir()
    (prompt_pack / "01_research_agent_prompt.md").write_text("# Prompt\n", encoding="utf-8")
    reports_path = story_path / "reports"
    write_yaml(reports_path / "test_layer_result.yaml", {"status": "PASSED"})
    write_yaml(
        reports_path / "quality_gate_result.yaml",
        {"status": "READY_FOR_REVIEW", "ready_for_review": True},
    )
    write_yaml(
        reports_path / "finalize_story_result.yaml",
        {"status": "ready_for_review", "ready_for_review": True},
    )
    write_yaml(reports_path / "cloud_review_result.yaml", {"decision": "APPROVE_WITH_NOTES"})
    write_yaml(
        reports_path / "merge_readiness_result.yaml",
        {"status": "READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION"},
    )
    (reports_path / "local_review_report.md").write_text(
        "# Local Review\n\nREADY_FOR_REVIEW\n",
        encoding="utf-8",
    )

    status = collect_story_status(tmp_path, story_path)

    assert status.agent_plan_exists is True
    assert status.prompt_pack_exists is True
    assert status.prompt_file_count == 1
    assert status.test_layer_exists is True
    assert status.test_layer_status == "PASSED"
    assert status.test_layer_passed is True
    assert status.quality_gate_exists is True
    assert status.quality_gate_status == "READY_FOR_REVIEW"
    assert status.quality_gate_ready is True
    assert status.finalize_exists is True
    assert status.finalize_status == "ready_for_review"
    assert status.finalize_ready is True
    assert status.cloud_review_exists is True
    assert status.cloud_review_decision == "APPROVE_WITH_NOTES"
    assert status.remote_dev_validation_exists is False
    assert status.remote_dev_validation_status is None
    assert status.merge_readiness_exists is True
    assert status.merge_readiness_status == "READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION"
    assert status.local_review_ready is True


def test_project_status_reads_and_reports_workflow_run_result(tmp_path: Path) -> None:
    story_path = create_story(tmp_path, "story_workflow_run", {"status": "planned"})
    write_yaml(
        story_path / "reports" / "workflow_run_result.yaml",
        {
            "phase": "local-finalize",
            "status": "completed",
            "executed": True,
            "executed_agents": False,
            "called_cloud_models": False,
            "called_github_apis": False,
            "committed_or_merged": False,
            "pushed": False,
            "merged": False,
            "deployed": False,
            "ran_destructive_commands": False,
            "ran_arbitrary_commands": False,
        },
    )

    story_status = collect_story_status(tmp_path, story_path)
    result = run_project_status(tmp_path)

    assert story_status.workflow_run_exists is True
    assert story_status.workflow_run_phase == "local-finalize"
    assert story_status.workflow_run_status == "completed"
    assert story_status.workflow_run_executed is True
    assert "called_cloud_models=no" in story_status.workflow_run_safety_summary
    assert "deployed=no" in story_status.workflow_run_safety_summary
    assert "workflow_run=completed (phase=local-finalize, executed=yes)" in result.terminal_summary
    assert "workflow_run_safety_summary=" in result.terminal_summary

    report = result.report_path.read_text(encoding="utf-8")
    assert "- workflow_run_result.yaml: present" in report
    assert "workflow_run_phase=local-finalize" in report
    assert "workflow_run_status=completed" in report
    assert "workflow_run_executed=yes" in report
    assert "called_github_apis=no" in report
    assert "ran_arbitrary_commands=no" in report


def test_project_status_handles_missing_workflow_run_result_as_not_recorded(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path, "story_without_workflow_run", {"status": "planned"})

    story_status = collect_story_status(tmp_path, story_path)
    result = run_project_status(tmp_path)

    assert story_status.workflow_run_exists is False
    assert story_status.workflow_run_phase is None
    assert story_status.workflow_run_status is None
    assert story_status.workflow_run_executed is None
    assert story_status.workflow_run_safety_summary == "not recorded"
    assert "workflow_run=not recorded (phase=not recorded, executed=missing)" in (
        result.terminal_summary
    )

    report = result.report_path.read_text(encoding="utf-8")
    assert "- workflow_run_result.yaml: missing" in report
    assert "workflow_run_phase=not recorded" in report
    assert "workflow_run_status=not recorded" in report
    assert "workflow_run_executed=missing" in report
    assert "- workflow_run_safety_summary: not recorded" in report


def test_project_status_handles_malformed_workflow_run_result_gracefully(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path, "story_bad_workflow_run", {"status": "planned"})
    reports_path = story_path / "reports"
    reports_path.mkdir()
    (reports_path / "workflow_run_result.yaml").write_text(
        "phase: [unterminated\n",
        encoding="utf-8",
    )

    story_status = collect_story_status(tmp_path, story_path)
    result = run_project_status(tmp_path)

    assert story_status.workflow_run_exists is True
    assert story_status.workflow_run_phase is None
    assert story_status.workflow_run_status is None
    assert story_status.workflow_run_executed is None
    assert story_status.workflow_run_safety_summary == "unavailable; see warnings"
    assert story_status.warnings
    assert "Invalid YAML" in story_status.warnings[0]

    report = result.report_path.read_text(encoding="utf-8")
    assert "- workflow_run_result.yaml: present" in report
    assert "workflow_run_status=not recorded" in report
    assert "- workflow_run_safety_summary: unavailable; see warnings" in report
    assert "Invalid YAML" in report


@pytest.mark.parametrize(
    "validation_status",
    [
        "DEV_VALIDATED",
        "DEV_VALIDATED_WITH_NOTES",
        "DEV_FAILED",
    ],
)
def test_project_status_reads_and_displays_remote_dev_validation_status(
    tmp_path: Path,
    validation_status: str,
) -> None:
    story_path = create_story(tmp_path, "story_remote_dev", {"status": "planned"})
    write_yaml(
        story_path / "reports" / "remote_dev_validation_result.yaml",
        {"validation_status": validation_status},
    )

    story_status = collect_story_status(tmp_path, story_path)
    result = run_project_status(tmp_path)

    assert story_status.remote_dev_validation_exists is True
    assert story_status.remote_dev_validation_status == validation_status
    assert f"remote_dev_validation={validation_status}" in result.terminal_summary

    report = result.report_path.read_text(encoding="utf-8")
    assert "- remote_dev_validation_result.yaml: present" in report
    assert f"validation_status={validation_status}" in report


def test_project_status_handles_missing_remote_dev_validation_as_not_recorded(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path, "story_without_remote_dev", {"status": "planned"})

    story_status = collect_story_status(tmp_path, story_path)
    result = run_project_status(tmp_path)

    assert story_status.remote_dev_validation_exists is False
    assert story_status.remote_dev_validation_status is None
    assert "remote_dev_validation=not recorded" in result.terminal_summary

    report = result.report_path.read_text(encoding="utf-8")
    assert "- remote_dev_validation_result.yaml: missing" in report
    assert "validation_status=not recorded" in report


def test_project_status_handles_malformed_remote_dev_validation_gracefully(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path, "story_bad_remote_dev", {"status": "planned"})
    reports_path = story_path / "reports"
    reports_path.mkdir()
    (reports_path / "remote_dev_validation_result.yaml").write_text(
        "validation_status: [unterminated\n",
        encoding="utf-8",
    )

    story_status = collect_story_status(tmp_path, story_path)
    result = run_project_status(tmp_path)

    assert story_status.remote_dev_validation_exists is True
    assert story_status.remote_dev_validation_status is None
    assert story_status.warnings
    assert "Invalid YAML" in story_status.warnings[0]

    report = result.report_path.read_text(encoding="utf-8")
    assert "validation_status=not recorded" in report
    assert "Invalid YAML" in report


def test_story_status_detects_blocking_support_ticket(tmp_path: Path) -> None:
    ticket_id = "SUPPORT-20260601-120000"
    story_path = create_story(
        tmp_path,
        "story_blocked",
        {"status": "blocked", "blocked_by": ticket_id},
    )
    support_ticket = tmp_path / ".agentic" / "support_queue" / "pending" / f"{ticket_id}.yaml"
    write_yaml(support_ticket, {"ticket_id": ticket_id, "status": "pending"})

    status = collect_story_status(tmp_path, story_path)

    assert status.support_ticket_blocking is True
    assert status.support_ticket_queue == "pending"
    assert status.category == "BLOCKED"


def test_summary_counts_include_ready_blocked_request_changes_and_unknown(
    tmp_path: Path,
) -> None:
    create_story(
        tmp_path,
        "story_ready",
        {"status": "ready_for_review", "ready_for_review": True},
    )
    create_story(tmp_path, "story_blocked", {"status": "blocked", "blocked_by": "SUPPORT-1"})
    create_story(tmp_path, "story_changes", {"status": "request_changes"})
    unknown_story = create_story(tmp_path, "story_unknown")
    (unknown_story / "agent_plan.yaml").write_text("agents: []\n", encoding="utf-8")

    result = run_project_status(tmp_path)

    assert result.summary_counts["total"] == 4
    assert result.summary_counts["READY_FOR_REVIEW"] == 1
    assert result.summary_counts["ready_stories"] == 1
    assert result.summary_counts["BLOCKED"] == 1
    assert result.summary_counts["blocked_stories"] == 1
    assert result.summary_counts["REQUEST_CHANGES"] == 1
    assert result.summary_counts["stories_needing_changes"] == 1
    assert result.summary_counts["UNKNOWN"] == 1
    assert "Ready for human/cloud review: 1" in result.terminal_summary
    assert "Blocked: 1" in result.terminal_summary
    assert "Needing changes: 1" in result.terminal_summary


def test_cli_project_status_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    create_story(tmp_path, "story_cli", {"status": "ready_for_review", "ready_for_review": True})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "project-status"])

    main()

    captured = capsys.readouterr()
    assert "Project status for:" in captured.out
    assert "story_cli" in captured.out
    assert "Report written to:" in captured.out
    assert (tmp_path / "reports" / "project_status_report.md").exists()


def test_project_status_does_not_require_git_or_cloud_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_story(tmp_path, "story_local_only", {"status": "planned"})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    result = run_project_status(tmp_path)

    assert not (tmp_path / ".git").exists()
    assert result.report_path.exists()
    report = result.report_path.read_text(encoding="utf-8")
    assert "does not call cloud models" in report
    assert "call GitHub APIs" in report


def test_project_status_includes_queue_counts(tmp_path: Path) -> None:
    create_story(tmp_path, "story_with_queues", {"status": "planned"})
    create_queue_item(
        project_path=tmp_path,
        queue_type="improvement",
        title="Improve reporting",
    )
    maintenance = create_queue_item(
        project_path=tmp_path,
        queue_type="maintenance",
        title="Clean up stale output",
    )
    create_queue_item(
        project_path=tmp_path,
        queue_type="feature",
        title="Add a dashboard",
    )
    set_queue_item_status(tmp_path, maintenance.item_id, "approved", "Approved for later.")

    result = run_project_status(tmp_path)

    assert result.queue_counts["improvement"]["total"] == 1
    assert result.queue_counts["improvement"]["pending"] == 1
    assert result.queue_counts["maintenance"]["total"] == 1
    assert result.queue_counts["maintenance"]["approved"] == 1
    assert result.queue_counts["feature"]["total"] == 1
    assert result.queue_counts["feature"]["pending"] == 1

    assert "improvement: total=1" in result.terminal_summary
    assert "maintenance: total=1" in result.terminal_summary
    assert "feature: total=1" in result.terminal_summary

    report = result.report_path.read_text(encoding="utf-8")
    assert "## Queue Counts" in report
    assert "### improvement" in report
    assert "### maintenance" in report
    assert "### feature" in report
    assert "- approved: 1" in report
