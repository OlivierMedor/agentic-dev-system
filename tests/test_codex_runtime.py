from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.codex_runtime import (
    create_codex_tasks,
    render_codex_runtime_command,
    run_one_codex_task,
)
from agentic_dev.runtime_config import CodexRuntimeConfig


STORY = "story_052_codex_runtime_connector"


def create_codex_task_story(
    project_path: Path,
    *,
    with_context: bool = True,
    include_execution_order: bool = True,
) -> Path:
    story_path = project_path / "stories" / STORY
    reports_path = story_path / "reports"
    role_context_path = reports_path / "role_context"
    story_path.mkdir(parents=True)
    reports_path.mkdir()

    agent_plan = {
        "story": STORY,
        "assigned_agents": [
            {
                "id": "developer_agent",
                "display_name": "Developer Agent",
                "responsibility": "Implement the Codex runtime connector.",
                "expected_output": "reports/developer_report.md",
            },
            {
                "id": "test_agent",
                "display_name": "Test Agent",
                "responsibility": "Test the Codex runtime connector.",
                "expected_output": "reports/test_report.md",
            },
        ],
    }
    if include_execution_order:
        agent_plan["execution_order"] = ["developer_agent", "test_agent"]

    (story_path / "agent_plan.yaml").write_text(
        yaml.safe_dump(agent_plan, sort_keys=False),
        encoding="utf-8",
    )

    agentic_path = project_path / ".agentic"
    agentic_path.mkdir()
    (agentic_path / "agent_runtime.yaml").write_text(
        """agents:
  developer_agent:
    provider: codex
    model: gpt-5.4
  test_agent:
    provider: codex
    model: gpt-5.4
""",
        encoding="utf-8",
    )

    if with_context:
        role_context_path.mkdir()
        (role_context_path / "developer_agent_context.md").write_text(
            """# Developer Agent Context

## Agent Identity

- Agent ID: `developer_agent`

## Role Responsibility

Implement the connector from role context.

## Expected Output

reports/developer_report.md

## Safety Boundaries

- Do not call cloud models.
""",
            encoding="utf-8",
        )
        (role_context_path / "test_agent_context.md").write_text(
            """# Test Agent Context

## Agent Identity

- Agent ID: `test_agent`

## Role Responsibility

Verify task generation behavior.

## Expected Output

reports/test_report.md
""",
            encoding="utf-8",
        )

    return story_path


def read_task(story_path: Path, agent_id: str) -> str:
    return (
        story_path / "reports" / "codex_tasks" / f"{agent_id}_codex_task.md"
    ).read_text(encoding="utf-8")


def test_missing_story_folder_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        create_codex_tasks(tmp_path, STORY)

    assert STORY in str(error.value)


def test_missing_role_context_raises_clear_error(tmp_path: Path) -> None:
    create_codex_task_story(tmp_path, with_context=False)

    with pytest.raises(FileNotFoundError, match="agentic build-context --story") as error:
        create_codex_tasks(tmp_path, STORY, agent="developer_agent")

    assert f"agentic build-context --story {STORY} --all --force" in str(error.value)


def test_creates_one_codex_task_file_for_one_agent(tmp_path: Path) -> None:
    story_path = create_codex_task_story(tmp_path)

    result = create_codex_tasks(tmp_path, STORY, agent="developer_agent")

    task_path = story_path / "reports" / "codex_tasks" / "developer_agent_codex_task.md"
    assert task_path.exists()
    assert result.generated_files == [task_path]
    assert not (story_path / "reports" / "codex_tasks" / "test_agent_codex_task.md").exists()
    assert "gpt-5.4 (codex)" in task_path.read_text(encoding="utf-8")


def test_creates_all_codex_task_files_with_all(tmp_path: Path) -> None:
    story_path = create_codex_task_story(tmp_path)

    result = create_codex_tasks(tmp_path, STORY, all_agents=True)

    assert [task.agent_id for task in result.tasks] == ["developer_agent", "test_agent"]
    assert (story_path / "reports" / "codex_tasks" / "developer_agent_codex_task.md").exists()
    assert (story_path / "reports" / "codex_tasks" / "test_agent_codex_task.md").exists()


def test_defaults_to_all_when_agent_is_omitted(tmp_path: Path) -> None:
    story_path = create_codex_task_story(tmp_path)

    create_codex_tasks(tmp_path, STORY)

    assert (story_path / "reports" / "codex_tasks" / "developer_agent_codex_task.md").exists()
    assert (story_path / "reports" / "codex_tasks" / "test_agent_codex_task.md").exists()


def test_force_overwrites_existing_task_file(tmp_path: Path) -> None:
    story_path = create_codex_task_story(tmp_path)
    task_folder = story_path / "reports" / "codex_tasks"
    task_folder.mkdir()
    task_path = task_folder / "developer_agent_codex_task.md"
    task_path.write_text("old task\n", encoding="utf-8")

    result = create_codex_tasks(tmp_path, STORY, agent="developer_agent", force=True)

    assert "old task" not in task_path.read_text(encoding="utf-8")
    assert result.generated_files == [task_path]
    assert result.skipped_files == []


def test_without_force_does_not_overwrite_existing_task_file(tmp_path: Path) -> None:
    story_path = create_codex_task_story(tmp_path)
    task_folder = story_path / "reports" / "codex_tasks"
    task_folder.mkdir()
    task_path = task_folder / "developer_agent_codex_task.md"
    task_path.write_text("custom task\n", encoding="utf-8")

    result = create_codex_tasks(tmp_path, STORY, agent="developer_agent")

    assert task_path.read_text(encoding="utf-8") == "custom task\n"
    assert result.generated_files == []
    assert result.skipped_files == [task_path]
    assert result.tasks[0].status == "skipped_existing"


def test_task_file_includes_safety_rules_and_required_do_not_do_items(tmp_path: Path) -> None:
    story_path = create_codex_task_story(tmp_path)

    create_codex_tasks(tmp_path, STORY, agent="developer_agent")

    task = read_task(story_path, "developer_agent")
    assert "## Safety Rules" in task
    assert "do not merge" in task
    assert "do not deploy" in task
    assert "do not call cloud models" in task
    assert "do not commit secrets" in task
    assert "do not modify unrelated files" in task
    assert "do not bypass artifact-policy" in task


def test_task_file_includes_role_context_and_required_output_report_path(
    tmp_path: Path,
) -> None:
    story_path = create_codex_task_story(tmp_path)

    create_codex_tasks(tmp_path, STORY, agent="developer_agent", model="gpt-5-codex")

    task = read_task(story_path, "developer_agent")
    assert "## Context Packet Content" in task
    assert "Implement the connector from role context." in task
    assert "## Required Output Report Path" in task
    assert "`reports/developer_report.md`" in task
    assert "gpt-5-codex" in task


def test_result_yaml_is_created_with_false_safety_flags(tmp_path: Path) -> None:
    story_path = create_codex_task_story(tmp_path)

    result = create_codex_tasks(tmp_path, STORY, agent="developer_agent")

    result_yaml = yaml.safe_load(result.result_path.read_text(encoding="utf-8"))
    assert result.result_path == story_path / "reports" / "codex_task_result.yaml"
    assert result.report_path == story_path / "reports" / "codex_task_report.md"
    assert result_yaml["safety_flags"] == {
        "called_codex": False,
        "called_cloud_models": False,
        "executed_agents": False,
        "called_github_apis": False,
        "committed_or_merged": False,
        "deployed": False,
    }


def test_codex_task_outputs_model_recommendation_from_runtime_config(tmp_path: Path) -> None:
    story_path = create_codex_task_story(tmp_path)

    result = create_codex_tasks(tmp_path, STORY, all_agents=True)

    result_yaml = yaml.safe_load(result.result_path.read_text(encoding="utf-8"))
    report = result.report_path.read_text(encoding="utf-8")
    developer_task = read_task(story_path, "developer_agent")
    test_task = read_task(story_path, "test_agent")

    assert result_yaml["tasks"][0]["model_recommendation"] == "gpt-5.4 (codex)"
    assert result_yaml["tasks"][1]["model_recommendation"] == "gpt-5.4 (codex)"
    assert "- Model recommendation: gpt-5.4 (codex)" in report
    assert "## Model Recommendation\n\ngpt-5.4 (codex)" in developer_task
    assert "## Model Recommendation\n\ngpt-5.4 (codex)" in test_task
    assert result_yaml["safety_flags"]["called_codex"] is False
    assert result_yaml["safety_flags"]["called_cloud_models"] is False


def test_execution_order_is_read_from_agent_plan(tmp_path: Path) -> None:
    create_codex_task_story(tmp_path)

    result = create_codex_tasks(tmp_path, STORY)

    assert result.recommended_execution_order == ["developer_agent", "test_agent"]


def test_fallback_standard_execution_order_is_used_when_missing(tmp_path: Path) -> None:
    create_codex_task_story(tmp_path, include_execution_order=False)

    result = create_codex_tasks(tmp_path, STORY, agent="developer_agent")

    assert result.recommended_execution_order == [
        "research_agent",
        "planner_agent",
        "developer_agent",
        "test_agent",
        "docs_agent",
        "security_quality_agent",
        "local_reviewer_agent",
    ]


def test_result_yaml_includes_recommended_execution_order(tmp_path: Path) -> None:
    create_codex_task_story(tmp_path)

    result = create_codex_tasks(tmp_path, STORY)

    result_yaml = yaml.safe_load(result.result_path.read_text(encoding="utf-8"))
    report = result.report_path.read_text(encoding="utf-8")
    assert result_yaml["recommended_execution_order"] == ["developer_agent", "test_agent"]
    assert "## Recommended Execution Order" in report
    assert "1. developer_agent" in report
    assert "2. test_agent" in report


def test_task_file_mentions_role_position_and_neighbors(tmp_path: Path) -> None:
    story_path = create_codex_task_story(tmp_path)

    create_codex_tasks(tmp_path, STORY, agent="developer_agent")

    task = read_task(story_path, "developer_agent")
    assert "## Recommended Execution Order Context" in task
    assert "- Position: 1" in task
    assert "- Usually comes before this agent: None" in task
    assert "- Usually comes after this agent: test_agent" in task
    assert "only do `developer_agent` work" in task


def test_tests_do_not_require_codex_cloud_models_or_github_apis(tmp_path: Path) -> None:
    create_codex_task_story(tmp_path)

    result = create_codex_tasks(tmp_path, STORY, agent="developer_agent")

    result_yaml = yaml.safe_load(result.result_path.read_text(encoding="utf-8"))
    assert result_yaml["safety_flags"]["called_codex"] is False
    assert result_yaml["safety_flags"]["called_cloud_models"] is False
    assert result_yaml["safety_flags"]["called_github_apis"] is False


def test_missing_codex_command_blocks_with_runtime_environment_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_file = tmp_path / "developer_agent_codex_task.md"
    expected_report = tmp_path / "reports" / "developer_report.md"
    runtime_path = tmp_path / "reports" / "codex_runtime"
    task_file.write_text("task\n", encoding="utf-8")
    config = CodexRuntimeConfig(
        enabled=True,
        command="codex",
        args=["exec", "--sandbox", "workspace-write", "-"],
        stdin_from_task_file=True,
        timeout_seconds=1800,
    )

    def fake_run(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("codex")

    monkeypatch.setattr("agentic_dev.codex_runtime.subprocess.run", fake_run)

    result = run_one_codex_task(
        project_path=tmp_path,
        runtime_path=runtime_path,
        agent_id="developer_agent",
        config=config,
        task_file=task_file,
        expected_report=expected_report,
    )

    assert result.status == "BLOCKED_CODEX_COMMAND_NOT_FOUND"
    assert "current runtime environment" in result.summary
    assert "Docker" in result.summary
    assert "dev container" in result.summary
    assert "codex_runtime.enabled: false" in result.summary
    assert "runtime setup problem, not a story implementation failure" in result.summary
    assert result.stderr_path is not None
    assert result.summary in result.stderr_path.read_text(encoding="utf-8")


def test_runtime_passes_task_file_content_to_codex_stdin_with_shell_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_file = tmp_path / "developer_agent_codex_task.md"
    expected_report = tmp_path / "reports" / "developer_report.md"
    runtime_path = tmp_path / "reports" / "codex_runtime"
    task_file.write_text("task content for stdin\n", encoding="utf-8")
    config = CodexRuntimeConfig(
        enabled=True,
        command="codex",
        args=["exec", "--sandbox", "workspace-write", "-"],
        stdin_from_task_file=True,
        timeout_seconds=1800,
    )
    calls: list[dict[str, object]] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append({"command": command, **kwargs})
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr("agentic_dev.codex_runtime.subprocess.run", fake_run)

    result = run_one_codex_task(
        project_path=tmp_path,
        runtime_path=runtime_path,
        agent_id="developer_agent",
        config=config,
        task_file=task_file,
        expected_report=expected_report,
    )

    assert result.status == "BLOCKED_MISSING_CODEX_REPORT"
    assert calls == [
        {
            "command": ["codex", "exec", "--sandbox", "workspace-write", "-"],
            "cwd": tmp_path,
            "capture_output": True,
            "input": "task content for stdin\n",
            "text": True,
            "shell": False,
            "timeout": 1800,
            "check": False,
        }
    ]


def test_render_codex_runtime_command_uses_workspace_write_sandbox(tmp_path: Path) -> None:
    task_file = tmp_path / "developer_agent_codex_task.md"
    config = CodexRuntimeConfig(
        enabled=True,
        command="codex",
        args=["exec", "--sandbox", "workspace-write", "-"],
        stdin_from_task_file=True,
        timeout_seconds=1800,
    )

    command = render_codex_runtime_command(config, task_file)

    assert command == ["codex", "exec", "--sandbox", "workspace-write", "-"]


def test_cli_codex_task_create_defaults_to_all_agents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    story_path = create_codex_task_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "codex-task", "create", "--story", STORY])

    main()

    captured = capsys.readouterr()
    assert "Codex tasks created for:" in captured.out
    assert (story_path / "reports" / "codex_tasks" / "developer_agent_codex_task.md").exists()
    assert (story_path / "reports" / "codex_tasks" / "test_agent_codex_task.md").exists()
