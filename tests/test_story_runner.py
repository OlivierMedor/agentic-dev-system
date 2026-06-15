from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.runtime_config import default_runtime_config_text
from agentic_dev.story_runner import (
    RUNNER_REPORT_FILENAME,
    RUNNER_RESULT_FILENAME,
    resolve_story,
    run_next_story,
    run_story,
)


STORY = "story_055_one_command_story_runner"

AGENT_REPORTS = {
    "research_agent": "research_report.md",
    "planner_agent": "planner_report.md",
    "developer_agent": "developer_report.md",
    "test_agent": "test_report.md",
    "docs_agent": "docs_report.md",
    "security_quality_agent": "security_quality_report.md",
    "local_reviewer_agent": "local_review_report.md",
}


def create_project(project_path: Path, *, runtime_config: str | None = None) -> None:
    (project_path / "stories").mkdir(parents=True)
    if runtime_config is not None:
        agentic_path = project_path / ".agentic"
        agentic_path.mkdir()
        (agentic_path / "agent_runtime.yaml").write_text(runtime_config, encoding="utf-8")


def create_story(
    project_path: Path,
    story: str = STORY,
    *,
    slug: str = "one-command-story-runner",
    status: str = "planned",
) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text(
        "# Story 055\n\n## Goal\n\nRun one story with one command.\n",
        encoding="utf-8",
    )
    (story_path / "test_plan.yaml").write_text("unit_tests: true\n", encoding="utf-8")
    (story_path / "monitoring_plan.yaml").write_text(
        "watch_for:\n  - missing_runtime\n",
        encoding="utf-8",
    )
    (story_path / "status.yaml").write_text(
        yaml.safe_dump(
            {
                "story_id": story,
                "slug": slug,
                "status": status,
                "ready_for_review": False,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return story_path


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def codex_runtime_config_text(*, command: str = "codex", args: list[str] | None = None) -> str:
    config = yaml.safe_load(default_runtime_config_text())
    config["codex_runtime"]["enabled"] = True
    config["codex_runtime"]["command"] = command
    if args is not None:
        config["codex_runtime"]["args"] = args
    return yaml.safe_dump(config, sort_keys=False)


def write_required_agent_reports(story_path: Path) -> None:
    reports_path = story_path / "reports"
    reports_path.mkdir()
    for filename in [
        "research_report.md",
        "planner_report.md",
        "developer_report.md",
        "test_report.md",
        "docs_report.md",
        "security_quality_report.md",
        "local_review_report.md",
    ]:
        content = "READY_FOR_REVIEW\n" if filename == "local_review_report.md" else "done\n"
        (reports_path / filename).write_text(content, encoding="utf-8")


def test_resolves_story_by_exact_folder_name(tmp_path: Path) -> None:
    create_project(tmp_path)
    story_path = create_story(tmp_path)

    resolved = resolve_story(tmp_path, STORY)

    assert resolved.story == STORY
    assert resolved.story_path == story_path
    assert resolved.matched_by == "folder"


def test_resolves_story_by_status_slug(tmp_path: Path) -> None:
    create_project(tmp_path)
    create_story(tmp_path, slug="one-command-story-runner")

    resolved = resolve_story(tmp_path, "one-command-story-runner")

    assert resolved.story == STORY
    assert resolved.matched_by == "slug"


def test_dry_run_writes_plan_without_preparing_story(tmp_path: Path) -> None:
    create_project(tmp_path)
    story_path = create_story(tmp_path)

    result = run_story(tmp_path, STORY)

    assert result.executed is False
    assert result.status == "planned"
    assert result.planned_steps == [
        "prepare-story",
        "build-context",
        "codex-task-create",
        "automatic-agent-runtime",
        "verify-required-agent-reports",
        "local-finalize",
        "quality-gate",
    ]
    assert result.result_path == story_path / "reports" / RUNNER_RESULT_FILENAME
    assert result.report_path == story_path / "reports" / RUNNER_REPORT_FILENAME
    assert result.result_path.exists()
    assert result.report_path.exists()
    assert not (story_path / "agent_plan.yaml").exists()
    assert "Dry run only" in result.report_path.read_text(encoding="utf-8")
    assert f"Project: {tmp_path.resolve()}" in result.terminal_summary
    assert "Execute mode: off" in result.terminal_summary
    assert "Planned safe workflow steps:" in result.terminal_summary
    assert "prepare-story" in result.terminal_summary
    assert "automatic-agent-runtime" in result.terminal_summary
    assert "Next action: Review the planned story workflow." in result.terminal_summary


def test_execute_stops_clearly_when_no_automatic_runtime_is_configured(
    tmp_path: Path,
) -> None:
    create_project(tmp_path, runtime_config=default_runtime_config_text())
    story_path = create_story(tmp_path)

    result = run_story(tmp_path, STORY, execute=True)

    assert result.status == "BLOCKED_MISSING_RUNTIME"
    assert "No automatic agent runtime is configured" in result.next_action
    assert "Enable codex_runtime.enabled or local_model_runtime.enabled" in result.next_action
    assert (story_path / "agent_plan.yaml").exists()
    assert (story_path / "prompt_pack").exists()
    assert (story_path / "reports" / "role_context_result.yaml").exists()
    assert (story_path / "reports" / "codex_task_result.yaml").exists()
    assert not (story_path / "reports" / "finalize_story_result.yaml").exists()


def test_execute_uses_enabled_codex_runtime_and_invokes_task_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_project(tmp_path, runtime_config=codex_runtime_config_text())
    story_path = create_story(tmp_path)
    commands: list[list[str]] = []
    stdin_payloads: list[str] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        input: str | None,
        text: bool,
        shell: bool,
        timeout: int,
        check: bool,
    ) -> SimpleNamespace:
        commands.append(command)
        assert cwd == tmp_path
        assert capture_output is True
        assert text is True
        assert shell is False
        assert timeout == 1800
        assert check is False
        assert input is not None
        stdin_payloads.append(input)
        agent_id = input.split("- Agent ID: `", 1)[1].split("`", 1)[0]
        report_name = AGENT_REPORTS[agent_id]
        report_content = "READY_FOR_REVIEW\n" if agent_id == "local_reviewer_agent" else "done\n"
        (story_path / "reports" / report_name).write_text(report_content, encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=f"ran {agent_id}\n", stderr="")

    def fake_finalize_story(project_path: Path, story: str) -> SimpleNamespace:
        result_path = project_path / "stories" / story / "reports" / "finalize_story_result.yaml"
        result_path.write_text("status: ready_for_review\n", encoding="utf-8")
        return SimpleNamespace(
            ready_for_review=True,
            status="ready_for_review",
            finalize_result_path=result_path,
        )

    def fake_run_quality_gate(project_path: Path, story: str) -> SimpleNamespace:
        result_path = project_path / "stories" / story / "reports" / "quality_gate_result.yaml"
        result_path.write_text("status: READY_FOR_REVIEW\n", encoding="utf-8")
        return SimpleNamespace(
            ready_for_review=True,
            status="READY_FOR_REVIEW",
            result_path=result_path,
            next_action="Send the story to a human or cloud reviewer.",
        )

    monkeypatch.setattr("agentic_dev.codex_runtime.subprocess.run", fake_run)
    monkeypatch.setattr("agentic_dev.story_runner.finalize_story", fake_finalize_story)
    monkeypatch.setattr("agentic_dev.story_runner.run_quality_gate", fake_run_quality_gate)

    result = run_story(tmp_path, STORY, execute=True)
    runtime_result = read_yaml(story_path / "reports" / "codex_runtime_execution_result.yaml")

    assert result.status == "completed"
    assert commands
    assert commands[0] == ["codex", "exec", "-"]
    assert "- Agent ID: `research_agent`" in stdin_payloads[0]
    assert runtime_result["status"] == "PASSED"
    assert runtime_result["safety_flags"]["called_codex"] is True
    assert ("automatic-agent-runtime:codex", "PASSED") in [
        (step.step, step.status) for step in result.step_results
    ]


def test_execute_stops_when_codex_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_project(tmp_path, runtime_config=codex_runtime_config_text())
    story_path = create_story(tmp_path)

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=7, stdout="partial\n", stderr="failed\n")

    monkeypatch.setattr("agentic_dev.codex_runtime.subprocess.run", fake_run)

    result = run_story(tmp_path, STORY, execute=True)
    runtime_result = read_yaml(story_path / "reports" / "codex_runtime_execution_result.yaml")

    assert result.status == "BLOCKED_CODEX_NONZERO_EXIT"
    assert "exited with code 7" in result.next_action
    assert runtime_result["executions"][0]["exit_code"] == 7
    assert not (story_path / "reports" / "finalize_story_result.yaml").exists()


def test_execute_stops_with_clear_docker_message_when_codex_command_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_project(tmp_path, runtime_config=codex_runtime_config_text())
    story_path = create_story(tmp_path)

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        raise FileNotFoundError("codex")

    monkeypatch.setattr("agentic_dev.codex_runtime.subprocess.run", fake_run)

    result = run_story(tmp_path, STORY, execute=True)
    result_data = read_yaml(result.result_path)
    runtime_result = read_yaml(story_path / "reports" / "codex_runtime_execution_result.yaml")
    runtime_report = (
        story_path / "reports" / "codex_runtime_execution_report.md"
    ).read_text(encoding="utf-8")
    story_runner_report = result.report_path.read_text(encoding="utf-8")
    summary = runtime_result["executions"][0]["summary"]

    assert result.status == "BLOCKED_CODEX_COMMAND_NOT_FOUND"
    assert result.next_action == summary
    assert runtime_result["status"] == "BLOCKED_CODEX_COMMAND_NOT_FOUND"
    assert runtime_result["executions"][0]["status"] == "BLOCKED_CODEX_COMMAND_NOT_FOUND"
    assert "current runtime environment" in summary
    assert "Docker" in summary
    assert "dev container" in summary
    assert "codex_runtime.enabled: false" in summary
    assert "runtime setup problem, not a story implementation failure" in summary
    assert summary in runtime_report
    assert summary in story_runner_report
    assert not (story_path / "reports" / "finalize_story_result.yaml").exists()
    safety_flags = result_data["safety_flags"]
    assert safety_flags["committed_or_merged"] is False
    assert safety_flags["pushed"] is False
    assert safety_flags["merged"] is False
    assert safety_flags["deployed"] is False
    assert safety_flags["opened_pr"] is False


def test_execute_stops_when_codex_report_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_project(tmp_path, runtime_config=codex_runtime_config_text())
    story_path = create_story(tmp_path)

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr("agentic_dev.codex_runtime.subprocess.run", fake_run)

    result = run_story(tmp_path, STORY, execute=True)
    runtime_result = read_yaml(story_path / "reports" / "codex_runtime_execution_result.yaml")

    assert result.status == "BLOCKED_MISSING_CODEX_REPORT"
    assert "did not create the expected report" in result.next_action
    assert runtime_result["executions"][0]["status"] == "BLOCKED_MISSING_CODEX_REPORT"
    assert not (story_path / "reports" / "finalize_story_result.yaml").exists()


def test_execute_skips_missing_runtime_when_required_reports_already_exist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_project(tmp_path, runtime_config=default_runtime_config_text())
    story_path = create_story(tmp_path)
    write_required_agent_reports(story_path)
    finalized: list[str] = []
    quality_checked: list[str] = []

    def fake_finalize_story(project_path: Path, story: str) -> SimpleNamespace:
        finalized.append(story)
        result_path = project_path / "stories" / story / "reports" / "finalize_story_result.yaml"
        result_path.write_text("status: ready_for_review\n", encoding="utf-8")
        return SimpleNamespace(
            ready_for_review=True,
            status="ready_for_review",
            finalize_result_path=result_path,
        )

    def fake_run_quality_gate(project_path: Path, story: str) -> SimpleNamespace:
        quality_checked.append(story)
        result_path = project_path / "stories" / story / "reports" / "quality_gate_result.yaml"
        result_path.write_text("status: READY_FOR_REVIEW\n", encoding="utf-8")
        return SimpleNamespace(
            ready_for_review=True,
            status="READY_FOR_REVIEW",
            result_path=result_path,
            next_action="Send the story to a human or cloud reviewer.",
        )

    monkeypatch.setattr("agentic_dev.story_runner.finalize_story", fake_finalize_story)
    monkeypatch.setattr("agentic_dev.story_runner.run_quality_gate", fake_run_quality_gate)

    result = run_story(tmp_path, STORY, execute=True)
    result_data = read_yaml(result.result_path)

    assert result.status != "BLOCKED_MISSING_RUNTIME"
    assert result.missing_reports == []
    assert finalized == [STORY]
    assert quality_checked == [STORY]
    assert (story_path / "reports" / "finalize_story_result.yaml").exists()
    assert (story_path / "reports" / "quality_gate_result.yaml").exists()
    assert ("automatic-agent-runtime", "SKIPPED_EXISTING_REPORTS") in [
        (step.step, step.status) for step in result.step_results
    ]
    assert ("local-finalize", "PASSED") in [
        (step.step, step.status) for step in result.step_results
    ]
    assert ("quality-gate", "READY_FOR_REVIEW") in [
        (step.step, step.status) for step in result.step_results
    ]
    safety_flags = result_data["safety_flags"]
    assert safety_flags["committed_or_merged"] is False
    assert safety_flags["pushed"] is False
    assert safety_flags["merged"] is False
    assert safety_flags["deployed"] is False
    assert safety_flags["opened_pr"] is False


def test_story_runner_records_no_auto_merge_push_deploy_or_pr(tmp_path: Path) -> None:
    create_project(tmp_path)
    create_story(tmp_path)

    result = run_story(tmp_path, STORY)
    result_data = read_yaml(result.result_path)
    safety_flags = result_data["safety_flags"]

    assert safety_flags["committed_or_merged"] is False
    assert safety_flags["pushed"] is False
    assert safety_flags["merged"] is False
    assert safety_flags["deployed"] is False
    assert safety_flags["opened_pr"] is False
    assert "no merge, push, force-push, deploy, PR" in result.terminal_summary
    assert "Did not merge." in result.report_path.read_text(encoding="utf-8")


def test_run_next_story_uses_blueprint_order_not_alphabetical(tmp_path: Path) -> None:
    create_project(tmp_path)
    create_story(tmp_path, "story_z_later", slug="story_z_later")
    create_story(tmp_path, "story_a_next", slug="story_a_next")
    (tmp_path / "blueprints").mkdir()
    (tmp_path / "blueprints" / "blueprint.yaml").write_text(
        yaml.safe_dump(
            {
                "stories": [
                    {"id": "STORY-Z", "slug": "story_z_later"},
                    {"id": "STORY-A", "slug": "story_a_next"},
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = run_next_story(tmp_path)

    assert result.story == "story_z_later"


def test_run_next_story_does_not_fall_back_to_unordered_story_when_blueprint_exists(
    tmp_path: Path,
) -> None:
    create_project(tmp_path)
    create_story(tmp_path, "story_001_unordered", slug="story_001_unordered")
    create_story(tmp_path, "story_900_done", slug="story_900_done", status="ready_for_review")
    (tmp_path / "stories" / "story_900_done" / "status.yaml").write_text(
        yaml.safe_dump(
            {
                "story_id": "story_900_done",
                "slug": "story_900_done",
                "status": "ready_for_review",
                "ready_for_review": True,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "blueprints").mkdir()
    (tmp_path / "blueprints" / "blueprint.yaml").write_text(
        yaml.safe_dump(
            {"stories": [{"id": "STORY-900", "slug": "story_900_done"}]},
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No runnable story with blueprint order"):
        run_next_story(tmp_path)


def test_cli_run_story_dry_run_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    story_path = create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "run-story", "--story", STORY])

    main()

    captured = capsys.readouterr()
    assert "Story runner for" in captured.out
    assert "Project:" in captured.out
    assert "Execute mode: off" in captured.out
    assert "Planned safe workflow steps:" in captured.out
    assert "prepare-story" in captured.out
    assert "no merge, push, force-push, deploy, PR" in captured.out
    assert (story_path / "reports" / RUNNER_RESULT_FILENAME).exists()


def test_cli_run_story_execute_missing_runtime_exits_with_clear_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    create_project(tmp_path, runtime_config=default_runtime_config_text())
    create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "run-story", "--story", STORY, "--execute"],
    )

    with pytest.raises(SystemExit) as error:
        main()

    captured = capsys.readouterr()
    assert error.value.code == 1
    assert "BLOCKED_MISSING_RUNTIME" in captured.out
    assert "No automatic agent runtime is configured" in captured.out
    assert "Enable codex_runtime.enabled or local_model_runtime.enabled" in captured.out
