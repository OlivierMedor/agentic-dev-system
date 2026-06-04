from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import yaml
from langgraph.graph import StateGraph

from agentic_dev.finalize_story import finalize_story
from agentic_dev.next_step import format_bullet_list, validate_story_folder
from agentic_dev.prepare_story import prepare_story
from agentic_dev.review_bundle import create_review_bundle
from agentic_dev.test_layers import TEST_LAYER_PASSED, run_test_layers
from agentic_dev.workflow_preview import run_workflow_preview


PREPARE_PHASE = "prepare"
LOCAL_FINALIZE_PHASE = "local-finalize"
SUPPORTED_PHASES = {PREPARE_PHASE, LOCAL_FINALIZE_PHASE}
WORKFLOW_RUN_PHASES = (PREPARE_PHASE, LOCAL_FINALIZE_PHASE)

WORKFLOW_RUN_NODES = (
    "collect_story_state",
    "plan_safe_steps",
    "run_or_skip_safe_steps",
    "write_workflow_run_report",
)


@dataclass(frozen=True)
class SafeStep:
    name: str
    command: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class SafeStepResult:
    step: str
    command: str
    ran: bool
    status: str
    returncode: int | None
    summary: str
    result_path: Path | None = None
    report_path: Path | None = None


@dataclass(frozen=True)
class WorkflowRunResult:
    story: str
    story_path: Path
    phase: str
    executed: bool
    status: str
    result_path: Path
    report_path: Path
    graph_nodes_visited: list[str]
    safe_steps_planned: list[str]
    safe_steps_executed: list[str]
    step_results: list[SafeStepResult]
    terminal_summary: str
    next_action: str


class WorkflowRunState(TypedDict, total=False):
    project_path: Path
    story: str
    phase: str
    execute: bool
    story_path: Path
    reports_path: Path
    graph_nodes_visited: list[str]
    safe_steps_planned: list[SafeStep]
    safe_steps_executed: list[str]
    step_results: list[SafeStepResult]
    status: str
    next_action: str
    result_path: Path
    report_path: Path
    terminal_summary: str


SafeStepRunner = Callable[[Path, str, SafeStep], SafeStepResult]


def build_workflow_run_graph(step_runner: SafeStepRunner | None = None):
    """Build the LangGraph safe runner graph without persistence or model calls."""
    runner = step_runner or run_safe_step

    def run_node(state: WorkflowRunState) -> WorkflowRunState:
        return run_or_skip_safe_steps(state, runner)

    graph = StateGraph(WorkflowRunState)
    graph.add_node("collect_story_state", collect_story_state)
    graph.add_node("plan_safe_steps", plan_safe_steps)
    graph.add_node("run_or_skip_safe_steps", run_node)
    graph.add_node("write_workflow_run_report", write_workflow_run_report)
    graph.set_entry_point("collect_story_state")
    graph.add_edge("collect_story_state", "plan_safe_steps")
    graph.add_edge("plan_safe_steps", "run_or_skip_safe_steps")
    graph.add_edge("run_or_skip_safe_steps", "write_workflow_run_report")
    graph.set_finish_point("write_workflow_run_report")
    return graph.compile()


def run_workflow_run(
    project_path: Path,
    story: str,
    phase: str = LOCAL_FINALIZE_PHASE,
    execute: bool = False,
    step_runner: SafeStepRunner | None = None,
) -> WorkflowRunResult:
    """Plan or execute a safe local story workflow using LangGraph."""
    if phase not in SUPPORTED_PHASES:
        raise ValueError(f"Unsupported workflow-run phase: {phase}")

    project_path = project_path.resolve()
    story_path = project_path / "stories" / story
    validate_story_folder(story_path)

    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    graph = build_workflow_run_graph(step_runner)
    final_state = graph.invoke(
        {
            "project_path": project_path,
            "story": story,
            "phase": phase,
            "execute": execute,
            "story_path": story_path,
            "reports_path": reports_path,
            "graph_nodes_visited": [],
        }
    )

    return WorkflowRunResult(
        story=story,
        story_path=story_path,
        phase=phase,
        executed=execute,
        status=final_state["status"],
        result_path=final_state["result_path"],
        report_path=final_state["report_path"],
        graph_nodes_visited=final_state["graph_nodes_visited"],
        safe_steps_planned=[step.name for step in final_state["safe_steps_planned"]],
        safe_steps_executed=final_state["safe_steps_executed"],
        step_results=final_state["step_results"],
        terminal_summary=final_state["terminal_summary"],
        next_action=final_state["next_action"],
    )


def collect_story_state(state: WorkflowRunState) -> WorkflowRunState:
    return {
        "graph_nodes_visited": append_node(state, "collect_story_state"),
    }


def plan_safe_steps(state: WorkflowRunState) -> WorkflowRunState:
    safe_steps = build_safe_steps(state["project_path"], state["story"], state["phase"])
    return {
        "safe_steps_planned": safe_steps,
        "graph_nodes_visited": append_node(state, "plan_safe_steps"),
    }


def run_or_skip_safe_steps(
    state: WorkflowRunState,
    step_runner: SafeStepRunner,
) -> WorkflowRunState:
    graph_nodes_visited = append_node(state, "run_or_skip_safe_steps")

    if not state["execute"]:
        return {
            "safe_steps_executed": [],
            "step_results": [],
            "status": "planned",
            "next_action": (
                "Review the planned safe local steps. Rerun with --execute to run them."
            ),
            "graph_nodes_visited": graph_nodes_visited,
        }

    step_results: list[SafeStepResult] = []
    safe_steps_executed: list[str] = []
    for step in state["safe_steps_planned"]:
        safe_steps_executed.append(step.name)
        step_results.append(step_runner(state["project_path"], state["story"], step))

    status = "completed" if all(result.returncode == 0 for result in step_results) else "failed"
    next_action = determine_next_action(state["phase"], status)

    return {
        "safe_steps_executed": safe_steps_executed,
        "step_results": step_results,
        "status": status,
        "next_action": next_action,
        "graph_nodes_visited": graph_nodes_visited,
    }


def write_workflow_run_report(state: WorkflowRunState) -> WorkflowRunState:
    reports_path = state["reports_path"]
    result_path = reports_path / "workflow_run_result.yaml"
    report_path = reports_path / "workflow_run_report.md"
    graph_nodes_visited = append_node(state, "write_workflow_run_report")
    planned_steps = state["safe_steps_planned"]
    step_results = state["step_results"]

    result_data = {
        "story": state["story"],
        "phase": state["phase"],
        "executed": state["execute"],
        "status": state["status"],
        "graph_nodes_visited": graph_nodes_visited,
        "safe_steps_planned": [step.name for step in planned_steps],
        "safe_steps_executed": state["safe_steps_executed"],
        "step_results": [serialize_step_result(result) for result in step_results],
        "executed_agents": False,
        "called_cloud_models": False,
        "called_github_apis": False,
        "committed_or_merged": False,
        "pushed": False,
        "merged": False,
        "deployed": False,
        "ran_destructive_commands": False,
        "ran_arbitrary_commands": False,
        "next_action": state["next_action"],
    }

    result_path.write_text(yaml.safe_dump(result_data, sort_keys=False), encoding="utf-8")
    write_markdown_report(report_path, state, graph_nodes_visited)

    terminal_summary = format_terminal_summary(
        state["story"],
        state["phase"],
        state["execute"],
        state["status"],
        result_path,
        report_path,
        graph_nodes_visited,
    )
    return {
        "result_path": result_path,
        "report_path": report_path,
        "terminal_summary": terminal_summary,
        "graph_nodes_visited": graph_nodes_visited,
    }


def build_safe_steps(project_path: Path, story: str, phase: str) -> list[SafeStep]:
    project_text = str(project_path)

    if phase == PREPARE_PHASE:
        return [
            SafeStep(
                name="prepare-story",
                command=("agentic", "prepare-story", "--project", project_text, "--story", story),
                description="Create or refresh the story setup artifacts without running agents.",
            ),
            SafeStep(
                name="workflow-preview",
                command=("agentic", "workflow-preview", "--project", project_text, "--story", story),
                description="Refresh the LangGraph route preview report.",
            ),
        ]

    if phase == LOCAL_FINALIZE_PHASE:
        return [
            SafeStep(
                name="test-layers",
                command=("agentic", "test-layers", "--project", project_text, "--story", story),
                description="Validate the story test layer plan.",
            ),
            SafeStep(
                name="finalize-story",
                command=("agentic", "finalize-story", "--project", project_text, "--story", story),
                description="Refresh final local evidence and update story status.",
            ),
            SafeStep(
                name="review-bundle",
                command=("agentic", "review-bundle", "--project", project_text, "--story", story),
                description="Refresh the local review bundle.",
            ),
            SafeStep(
                name="workflow-preview",
                command=("agentic", "workflow-preview", "--project", project_text, "--story", story),
                description="Refresh the LangGraph route preview report.",
            ),
        ]

    raise ValueError(f"Unsupported workflow-run phase: {phase}")


def run_safe_step(project_path: Path, story: str, step: SafeStep) -> SafeStepResult:
    """Execute one hardcoded safe step directly through local Python functions."""
    try:
        if step.name == "prepare-story":
            result = prepare_story(project_path, story)
            return build_step_result(
                step,
                True,
                (
                    "prepare-story completed; "
                    f"prompt files created or updated: {len(result.prompt_files_created)}; "
                    f"prompt files skipped: {len(result.prompt_files_skipped)}"
                ),
                None,
                result.report_path,
            )

        if step.name == "test-layers":
            result = run_test_layers(project_path, story)
            passed = result.status == TEST_LAYER_PASSED
            return build_step_result(
                step,
                passed,
                f"test-layers status: {result.status}",
                result.result_path,
                result.report_path,
            )

        if step.name == "finalize-story":
            result = finalize_story(project_path, story)
            return build_step_result(
                step,
                result.ready_for_review,
                f"finalize-story status: {result.status}",
                result.finalize_result_path,
                result.finalize_report_path,
            )

        if step.name == "review-bundle":
            result = create_review_bundle(project_path, story)
            passed = result.pytest_passed and result.ruff_passed
            return build_step_result(
                step,
                passed,
                (
                    "review-bundle completed; "
                    f"pytest passed: {result.pytest_passed}; ruff passed: {result.ruff_passed}"
                ),
                None,
                result.review_bundle_path / "handoff.md",
            )

        if step.name == "workflow-preview":
            result = run_workflow_preview(project_path, story)
            return build_step_result(
                step,
                True,
                f"workflow-preview next action: {result.recommended_next_action}",
                result.result_path,
                result.report_path,
            )
    except Exception as error:  # noqa: BLE001
        return SafeStepResult(
            step=step.name,
            command=format_command(step.command),
            ran=True,
            status="FAILED",
            returncode=1,
            summary=f"{type(error).__name__}: {error}",
        )

    return SafeStepResult(
        step=step.name,
        command=format_command(step.command),
        ran=False,
        status="BLOCKED_UNSAFE_STEP",
        returncode=1,
        summary="The requested step is not in the safe workflow-run allowlist.",
    )


def build_step_result(
    step: SafeStep,
    passed: bool,
    summary: str,
    result_path: Path | None,
    report_path: Path | None,
) -> SafeStepResult:
    return SafeStepResult(
        step=step.name,
        command=format_command(step.command),
        ran=True,
        status="PASSED" if passed else "FAILED",
        returncode=0 if passed else 1,
        summary=summary,
        result_path=result_path,
        report_path=report_path,
    )


def write_markdown_report(
    report_path: Path,
    state: WorkflowRunState,
    graph_nodes_visited: list[str],
) -> None:
    planned_steps = state["safe_steps_planned"]
    step_results = state["step_results"]
    execution_text = (
        "Execution happened because `--execute` was provided."
        if state["execute"]
        else "Dry run only. No workflow steps ran because `--execute` was not provided."
    )

    content = f"""# Workflow Run Report

## Story

{state["story"]}

## Phase

{state["phase"]}

## Execution

{execution_text}

## Status

{state["status"]}

## Graph nodes visited

{format_bullet_list(graph_nodes_visited)}
## Planned safe steps

{format_safe_steps(planned_steps)}
## Executed safe steps

{format_bullet_list(state["safe_steps_executed"])}
## Step result summary

{format_step_results(step_results)}
## Safety reminders

- This runner only uses the hardcoded safe local workflow steps for the selected phase.
- It did not execute agents or generated agent prompts.
- It did not call cloud models or GitHub APIs.
- It did not commit, push, merge, deploy, or run destructive commands.
- It did not run arbitrary commands from user input.
- Human final approval is always required before merge.

## Next recommended action

{state["next_action"]}
"""
    report_path.write_text(content, encoding="utf-8")


def determine_next_action(phase: str, status: str) -> str:
    if status != "completed":
        return "Fix the failed local step results, then rerun workflow-run with --execute."

    if phase == PREPARE_PHASE:
        return (
            "Review workflow_preview_report.md, then run the generated agent prompts "
            "manually through the configured agent runtime."
        )

    return "Review workflow_run_report.md and continue to manual review."


def format_safe_steps(steps: list[SafeStep]) -> str:
    if not steps:
        return "- None.\n"

    return "\n".join(
        f"- {step.name}: `{format_command(step.command)}` - {step.description}" for step in steps
    ) + "\n"


def format_step_results(step_results: list[SafeStepResult]) -> str:
    if not step_results:
        return "- No command results. Dry run mode only planned the safe steps.\n"

    lines: list[str] = []
    for result in step_results:
        lines.append(f"- {result.step}: {result.status} (exit {result.returncode})")
        lines.append(f"  - command: `{result.command}`")
        lines.append(f"  - summary: {result.summary}")
        if result.result_path is not None:
            lines.append(f"  - result: `{result.result_path}`")
        if result.report_path is not None:
            lines.append(f"  - report: `{result.report_path}`")
    return "\n".join(lines) + "\n"


def serialize_step_result(result: SafeStepResult) -> dict[str, Any]:
    return {
        "step": result.step,
        "command": result.command,
        "ran": result.ran,
        "status": result.status,
        "returncode": result.returncode,
        "summary": result.summary,
        "result_path": str(result.result_path) if result.result_path else None,
        "report_path": str(result.report_path) if result.report_path else None,
    }


def format_terminal_summary(
    story: str,
    phase: str,
    executed: bool,
    status: str,
    result_path: Path,
    report_path: Path,
    graph_nodes_visited: list[str],
) -> str:
    execution = "executed safe local steps" if executed else "planned safe local steps only"
    return "\n".join(
        [
            f"Workflow run for {story}:",
            f"Phase: {phase}",
            f"Mode: {execution}",
            "Route: " + " -> ".join(graph_nodes_visited),
            f"Status: {status}",
            "Safety: no agents, cloud models, GitHub APIs, merge, or deployment ran.",
            f"Result written to: {result_path}",
            f"Report written to: {report_path}",
        ]
    )


def append_node(state: WorkflowRunState, node_name: str) -> list[str]:
    return [*state.get("graph_nodes_visited", []), node_name]


def format_command(command: tuple[str, ...]) -> str:
    return " ".join(command)
