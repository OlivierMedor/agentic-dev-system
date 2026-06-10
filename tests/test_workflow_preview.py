from pathlib import Path
from typing import Any

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.workflow_preview import (
    WORKFLOW_PREVIEW_NODES,
    build_workflow_preview_graph,
    run_workflow_preview,
)


STORY = "story_027_langgraph_workflow_preview"


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def create_story(project_path: Path, status_data: dict[str, Any] | None = None) -> Path:
    story_path = project_path / "stories" / STORY
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# STORY-027\n", encoding="utf-8")
    write_yaml(
        story_path / "status.yaml",
        status_data
        or {
            "story_id": "STORY-027",
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


def write_micro_readiness_result(story_path: Path, status: str = "READY_FOR_MICRO") -> None:
    write_yaml(
        story_path / "reports" / "micro_readiness_result.yaml",
        {
            "status": status,
            "warnings": [],
            "failed_checks": [],
        },
    )


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


def write_merge_readiness_result(story_path: Path) -> None:
    write_yaml(
        story_path / "reports" / "merge_readiness_result.yaml",
        {
            "status": "READY_FOR_HUMAN_MERGE_DECISION",
            "ready_for_human_merge_decision": True,
        },
    )


def write_remote_dev_validation_result(story_path: Path) -> None:
    write_yaml(
        story_path / "reports" / "remote_dev_validation_result.yaml",
        {
            "validation_status": "DEV_VALIDATED",
            "ready_for_review": True,
        },
    )


def assert_preview_safety_flags(result_data: dict[str, Any]) -> None:
    assert result_data["automation_level"] == "preview_only"
    assert result_data["executed_agents"] is False
    assert result_data["called_cloud_models"] is False
    assert result_data["called_github_apis"] is False
    assert result_data["committed_or_merged"] is False
    assert result_data["deployed"] is False


def recommendation_text(result_data: dict[str, Any], report: str) -> str:
    return "\n".join(
        [
            str(result_data["recommended_next_action"]),
            str(result_data.get("suggested_command") or ""),
            report,
        ],
    )


def test_build_workflow_preview_graph_contains_expected_nodes() -> None:
    graph = build_workflow_preview_graph()

    assert callable(graph.invoke)
    assert set(WORKFLOW_PREVIEW_NODES).issubset(set(graph.get_graph().nodes))


def test_workflow_preview_validates_story_folder_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        run_workflow_preview(tmp_path, STORY)

    assert STORY in str(error.value)


def test_workflow_preview_creates_result_report_and_records_preview_safety(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)

    result = run_workflow_preview(tmp_path, STORY)

    assert result.result_path == tmp_path / "stories" / STORY / "reports" / (
        "workflow_preview_result.yaml"
    )
    assert result.report_path == tmp_path / "stories" / STORY / "reports" / (
        "workflow_preview_report.md"
    )
    assert result.result_path.exists()
    assert result.report_path.exists()
    assert result.graph_nodes_visited == list(WORKFLOW_PREVIEW_NODES)

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["graph_nodes_visited"] == list(WORKFLOW_PREVIEW_NODES)
    assert_preview_safety_flags(result_data)
    assert "Route: collect_story_state -> determine_next_action -> write_preview" in (
        result.terminal_summary
    )
    assert "No agents, cloud models, GitHub APIs, merge, or deployment ran." in (
        result.terminal_summary
    )
    assert "## Graph nodes visited" in report
    assert "It did not execute agents through the configured agent runtime." in report


def test_workflow_preview_recommends_workflow_run_prepare_when_agent_plan_is_missing(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)

    result = run_workflow_preview(tmp_path, STORY)
    result_data = read_yaml(result.result_path)

    assert result_data["recommended_next_action"] == "Run workflow-run prepare."
    assert result_data["suggested_command"] == (
        f"agentic workflow-run --story {STORY} --phase prepare --execute"
    )
    assert result_data["current_state"]["agent_plan_exists"] is False


def test_workflow_preview_recommends_workflow_run_prepare_when_prompt_pack_is_missing(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    create_agent_plan(story_path)

    result = run_workflow_preview(tmp_path, STORY)
    result_data = read_yaml(result.result_path)

    assert result_data["recommended_next_action"] == "Run workflow-run prepare."
    assert result_data["suggested_command"] == (
        f"agentic workflow-run --story {STORY} --phase prepare --execute"
    )
    assert result_data["current_state"]["agent_plan_exists"] is True
    assert result_data["current_state"]["prompt_pack_exists"] is False


def test_workflow_preview_recommends_configured_agent_runtime_when_reports_are_missing(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_prompted_story(story_path)
    write_micro_readiness_result(story_path)

    result = run_workflow_preview(tmp_path, STORY)
    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")

    assert result_data["recommended_next_action"] == "Run the generated agent prompts."
    assert result_data["suggested_command"] is None
    assert "configured agent runtime" in report
    assert "developer_report.md" in report
    assert "test_report.md" in report
    assert "local_review_report.md" in report


def test_workflow_preview_recommends_micro_readiness_when_result_is_missing(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_prompted_story(story_path)

    result = run_workflow_preview(tmp_path, STORY)
    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")

    assert result_data["recommended_next_action"] == "Run micro-readiness."
    assert result_data["suggested_command"] == f"agentic micro-readiness --story {STORY}"
    assert "micro_readiness_result.yaml is not recorded yet" in report


def test_workflow_preview_recommends_workflow_run_cloud_review_prep_after_finalize_is_ready(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_reported_story(story_path)
    write_ready_finalize_result(story_path)

    result = run_workflow_preview(tmp_path, STORY)
    result_data = read_yaml(result.result_path)

    assert result_data["recommended_next_action"] == "Run workflow-run cloud-review-prep."
    assert result_data["suggested_command"] == (
        f"agentic workflow-run --story {STORY} --phase cloud-review-prep --execute"
    )
    assert result_data["current_state"]["cloud_review_export_exists"] is False


def test_workflow_preview_does_not_recommend_automatic_merge_or_deployment(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    prepare_reported_story(story_path)
    write_ready_finalize_result(story_path)
    write_cloud_review_export(story_path)
    write_cloud_review_result(story_path)
    write_merge_readiness_result(story_path)
    write_remote_dev_validation_result(story_path)

    result = run_workflow_preview(tmp_path, STORY)
    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    text = recommendation_text(result_data, report).lower()

    assert result_data["recommended_next_action"] == "Human PR/CI review is next."
    assert "automatic merge" not in text.split("## safety reminders", maxsplit=1)[0]
    assert "automatic deployment" not in text.split("## safety reminders", maxsplit=1)[0]
    assert "It does not recommend automatic merge or automatic deployment." in report
    assert_preview_safety_flags(result_data)


def test_cli_workflow_preview_requires_story_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "workflow-preview"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_workflow_preview_defaults_project_to_current_directory_without_git_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    story_path = create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "workflow-preview", "--story", STORY])

    main()

    output = capsys.readouterr().out
    assert f"Workflow preview for {STORY}:" in output
    assert "Recommended next action: Run workflow-run prepare." in output
    assert not (tmp_path / ".git").exists()
    assert (story_path / "reports" / "workflow_preview_result.yaml").exists()
    assert (story_path / "reports" / "workflow_preview_report.md").exists()


def test_workflow_preview_does_not_call_shell_cloud_models_or_github_apis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    prepare_reported_story(story_path)

    def fail_if_external_execution_is_used(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("workflow-preview must not call external execution APIs")

    monkeypatch.setattr("subprocess.run", fail_if_external_execution_is_used)
    monkeypatch.setattr("urllib.request.urlopen", fail_if_external_execution_is_used)

    result = run_workflow_preview(tmp_path, STORY)
    result_data = read_yaml(result.result_path)

    assert_preview_safety_flags(result_data)
    assert result_data["called_cloud_models"] is False
    assert result_data["called_github_apis"] is False
