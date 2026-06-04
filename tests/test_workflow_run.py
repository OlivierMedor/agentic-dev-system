from pathlib import Path
from typing import Any

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.workflow_run import (
    LOCAL_FINALIZE_PHASE,
    PREPARE_PHASE,
    WORKFLOW_RUN_NODES,
    SafeStep,
    SafeStepResult,
    build_safe_steps,
    build_workflow_run_graph,
    run_workflow_run,
)


STORY = "story_028_langgraph_safe_workflow_runner"
LOCAL_FINALIZE_STEPS = [
    "test-layers",
    "finalize-story",
    "review-bundle",
    "workflow-preview",
]
PREPARE_STEPS = [
    "prepare-story",
    "workflow-preview",
]


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# STORY-028\n", encoding="utf-8")
    (story_path / "status.yaml").write_text(
        f"story_id: {story}\n"
        "status: in_progress\n"
        "ready_for_review: false\n",
        encoding="utf-8",
    )
    return story_path


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def fake_step_runner(calls: list[str]):
    def run_step(project_path: Path, story: str, step: SafeStep) -> SafeStepResult:
        calls.append(step.name)
        reports_path = project_path / "stories" / story / "reports"
        result_path = reports_path / f"{step.name.replace('-', '_')}_fake_result.yaml"
        report_path = reports_path / f"{step.name.replace('-', '_')}_fake_report.md"
        result_path.write_text("status: PASSED\n", encoding="utf-8")
        report_path.write_text(f"# {step.name}\n", encoding="utf-8")
        return SafeStepResult(
            step=step.name,
            command=" ".join(step.command),
            ran=True,
            status="PASSED",
            returncode=0,
            summary=f"{step.name} passed under fake execution.",
            result_path=result_path,
            report_path=report_path,
        )

    return run_step


def assert_workflow_run_safety_flags(result_data: dict[str, Any]) -> None:
    assert result_data["executed_agents"] is False
    assert result_data["called_cloud_models"] is False
    assert result_data["called_github_apis"] is False
    assert result_data["committed_or_merged"] is False
    assert result_data["pushed"] is False
    assert result_data["merged"] is False
    assert result_data["deployed"] is False
    assert result_data["ran_destructive_commands"] is False
    assert result_data["ran_arbitrary_commands"] is False


def test_build_workflow_run_graph_contains_expected_nodes() -> None:
    graph = build_workflow_run_graph()

    assert callable(graph.invoke)
    assert set(WORKFLOW_RUN_NODES).issubset(set(graph.get_graph().nodes))


def test_workflow_run_validates_story_folder_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        run_workflow_run(tmp_path, STORY)

    assert STORY in str(error.value)


def test_workflow_run_supports_local_finalize_phase_and_rejects_unsupported_phase(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)

    result = run_workflow_run(tmp_path, STORY, phase=LOCAL_FINALIZE_PHASE)
    prepare_result = run_workflow_run(tmp_path, STORY, phase=PREPARE_PHASE)

    assert result.phase == LOCAL_FINALIZE_PHASE
    assert prepare_result.phase == PREPARE_PHASE
    with pytest.raises(ValueError, match="Unsupported workflow-run phase: deploy"):
        run_workflow_run(tmp_path, STORY, phase="deploy")


def test_workflow_run_dry_run_writes_plan_without_running_safe_steps(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        execute=False,
        step_runner=fake_step_runner(calls),
    )

    assert calls == []
    assert result.executed is False
    assert result.status == "planned"
    assert result.safe_steps_planned == LOCAL_FINALIZE_STEPS
    assert result.safe_steps_executed == []
    assert result.step_results == []
    assert result.graph_nodes_visited == list(WORKFLOW_RUN_NODES)
    assert result.result_path == story_path / "reports" / "workflow_run_result.yaml"
    assert result.report_path == story_path / "reports" / "workflow_run_report.md"
    assert result.result_path.exists()
    assert result.report_path.exists()

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["executed"] is False
    assert result_data["status"] == "planned"
    assert result_data["graph_nodes_visited"] == list(WORKFLOW_RUN_NODES)
    assert result_data["safe_steps_planned"] == LOCAL_FINALIZE_STEPS
    assert result_data["safe_steps_executed"] == []
    assert result_data["step_results"] == []
    assert_workflow_run_safety_flags(result_data)
    assert "Dry run only. No workflow steps ran" in report
    assert "No command results. Dry run mode only planned the safe steps." in report


def test_workflow_run_execute_runs_safe_local_finalize_steps_with_fake_runner(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        execute=True,
        step_runner=fake_step_runner(calls),
    )

    assert calls == LOCAL_FINALIZE_STEPS
    assert result.executed is True
    assert result.status == "completed"
    assert result.safe_steps_planned == LOCAL_FINALIZE_STEPS
    assert result.safe_steps_executed == LOCAL_FINALIZE_STEPS
    assert [step_result.step for step_result in result.step_results] == LOCAL_FINALIZE_STEPS
    assert all(step_result.ran for step_result in result.step_results)
    assert all(step_result.returncode == 0 for step_result in result.step_results)

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["executed"] is True
    assert result_data["status"] == "completed"
    assert result_data["safe_steps_executed"] == LOCAL_FINALIZE_STEPS
    assert [step_result["step"] for step_result in result_data["step_results"]] == (
        LOCAL_FINALIZE_STEPS
    )
    assert_workflow_run_safety_flags(result_data)
    assert "Execution happened because `--execute` was provided." in report
    assert "test-layers: PASSED" in report
    assert "finalize-story: PASSED" in report
    assert "review-bundle: PASSED" in report
    assert "workflow-preview: PASSED" in report


def test_workflow_run_prepare_dry_run_writes_plan_without_running_safe_steps(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=PREPARE_PHASE,
        execute=False,
        step_runner=fake_step_runner(calls),
    )

    assert calls == []
    assert result.phase == PREPARE_PHASE
    assert result.executed is False
    assert result.status == "planned"
    assert result.safe_steps_planned == PREPARE_STEPS
    assert result.safe_steps_executed == []
    assert result.step_results == []
    assert result.graph_nodes_visited == list(WORKFLOW_RUN_NODES)
    assert result.result_path == story_path / "reports" / "workflow_run_result.yaml"
    assert result.report_path == story_path / "reports" / "workflow_run_report.md"

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["phase"] == PREPARE_PHASE
    assert result_data["executed"] is False
    assert result_data["status"] == "planned"
    assert result_data["graph_nodes_visited"] == list(WORKFLOW_RUN_NODES)
    assert result_data["safe_steps_planned"] == PREPARE_STEPS
    assert result_data["safe_steps_executed"] == []
    assert result_data["step_results"] == []
    assert_workflow_run_safety_flags(result_data)
    assert "Dry run only. No workflow steps ran" in report
    assert "prepare-story" in report
    assert "workflow-preview" in report


def test_workflow_run_prepare_execute_runs_only_safe_prepare_steps_with_fake_runner(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    calls: list[str] = []

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=PREPARE_PHASE,
        execute=True,
        step_runner=fake_step_runner(calls),
    )

    assert calls == PREPARE_STEPS
    assert result.executed is True
    assert result.status == "completed"
    assert result.safe_steps_planned == PREPARE_STEPS
    assert result.safe_steps_executed == PREPARE_STEPS
    assert [step_result.step for step_result in result.step_results] == PREPARE_STEPS
    assert all(step_result.ran for step_result in result.step_results)

    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")
    assert result_data["phase"] == PREPARE_PHASE
    assert result_data["executed"] is True
    assert result_data["status"] == "completed"
    assert result_data["graph_nodes_visited"] == list(WORKFLOW_RUN_NODES)
    assert result_data["safe_steps_planned"] == PREPARE_STEPS
    assert result_data["safe_steps_executed"] == PREPARE_STEPS
    assert [step_result["step"] for step_result in result_data["step_results"]] == PREPARE_STEPS
    assert_workflow_run_safety_flags(result_data)
    assert "Execution happened because `--execute` was provided." in report
    assert "prepare-story: PASSED" in report
    assert "workflow-preview: PASSED" in report
    assert "generated agent prompts" in report


def test_prepare_safe_steps_are_hardcoded_allowlist(tmp_path: Path) -> None:
    steps = build_safe_steps(tmp_path, STORY, PREPARE_PHASE)

    assert [step.name for step in steps] == PREPARE_STEPS
    assert [step.command[0] for step in steps] == ["agentic", "agentic"]
    assert [step.command[1] for step in steps] == PREPARE_STEPS
    for step in steps:
        assert "--project" in step.command
        assert "--story" in step.command
        assert STORY in step.command
        assert "prompt_pack" not in step.command
        assert not any(token in step.command for token in ["git", "push", "merge", "deploy"])


def test_local_finalize_safe_steps_are_hardcoded_allowlist(tmp_path: Path) -> None:
    steps = build_safe_steps(tmp_path, STORY, LOCAL_FINALIZE_PHASE)

    assert [step.name for step in steps] == LOCAL_FINALIZE_STEPS
    assert [step.command[0] for step in steps] == ["agentic", "agentic", "agentic", "agentic"]
    assert [step.command[1] for step in steps] == LOCAL_FINALIZE_STEPS
    for step in steps:
        assert "--project" in step.command
        assert "--story" in step.command
        assert STORY in step.command
        assert not any(token in step.command for token in ["git", "push", "merge", "deploy"])


def test_workflow_run_does_not_run_arbitrary_commands_from_user_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_story(tmp_path)
    calls: list[str] = []

    def fail_if_shell_execution_is_used(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("workflow-run must not execute arbitrary shell commands")

    monkeypatch.setattr("subprocess.run", fail_if_shell_execution_is_used)

    result = run_workflow_run(
        tmp_path,
        STORY,
        execute=True,
        step_runner=fake_step_runner(calls),
    )
    result_data = read_yaml(result.result_path)

    assert calls == LOCAL_FINALIZE_STEPS
    assert result_data["ran_arbitrary_commands"] is False
    assert result_data["ran_destructive_commands"] is False


def test_workflow_run_prepare_does_not_run_arbitrary_commands_or_prompt_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    prompt_path = story_path / "prompt_pack" / "99_malicious_prompt.md"
    prompt_path.parent.mkdir()
    prompt_path.write_text("agentic deploy\n", encoding="utf-8")
    calls: list[str] = []

    def fail_if_shell_execution_is_used(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("workflow-run prepare must not execute shell commands")

    monkeypatch.setattr("subprocess.run", fail_if_shell_execution_is_used)

    result = run_workflow_run(
        tmp_path,
        STORY,
        phase=PREPARE_PHASE,
        execute=True,
        step_runner=fake_step_runner(calls),
    )
    result_data = read_yaml(result.result_path)
    serialized_commands = [
        step_result["command"] for step_result in result_data["step_results"]
    ]

    assert calls == PREPARE_STEPS
    assert prompt_path.name not in "\n".join(serialized_commands)
    assert "agentic deploy" not in "\n".join(serialized_commands)
    assert result_data["ran_arbitrary_commands"] is False
    assert result_data["ran_destructive_commands"] is False


def test_workflow_run_does_not_recommend_automatic_merge_or_deployment(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)

    result = run_workflow_run(tmp_path, STORY)
    result_data = read_yaml(result.result_path)
    report = result.report_path.read_text(encoding="utf-8")

    recommendation_text = f"{result_data['next_action']}\n{report}".lower()
    assert "automatic merge" not in recommendation_text
    assert "automatic deployment" not in recommendation_text
    assert "human final approval is always required before merge" in recommendation_text
    assert result_data["committed_or_merged"] is False
    assert result_data["deployed"] is False


def test_cli_workflow_run_requires_story_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "workflow-run"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_workflow_run_rejects_unsupported_phase_with_clear_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "workflow-run", "--story", STORY, "--phase", "deploy"],
    )

    with pytest.raises(SystemExit) as error:
        main()

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert "invalid choice: 'deploy'" in captured.err
    assert "prepare" in captured.err
    assert "local-finalize" in captured.err


def test_cli_workflow_run_defaults_project_to_current_directory_without_git_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    story_path = create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "workflow-run", "--story", STORY])

    main()

    output = capsys.readouterr().out
    assert f"Workflow run for {STORY}:" in output
    assert "Mode: planned safe local steps only" in output
    assert not (tmp_path / ".git").exists()
    assert (story_path / "reports" / "workflow_run_result.yaml").exists()
    assert (story_path / "reports" / "workflow_run_report.md").exists()
