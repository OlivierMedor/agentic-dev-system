from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import yaml

try:  # pragma: no cover - exercised only when langgraph is installed
    from langgraph.graph import StateGraph
except ModuleNotFoundError:  # pragma: no cover - offline fallback
    class _FallbackGraph:
        def __init__(self, nodes: dict[str, Any], entry_point: str, finish_point: str) -> None:
            self._nodes = nodes
            self._entry_point = entry_point
            self._finish_point = finish_point

        def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
            current = dict(state)
            current.update(self._nodes[self._entry_point](current))
            current.update(self._nodes["determine_next_action"](current))
            current.update(self._nodes[self._finish_point](current))
            return current

        def get_graph(self) -> Any:
            return type("FallbackGraph", (), {"nodes": {name: object() for name in self._nodes}})()

    class StateGraph:  # type: ignore[override]
        def __init__(self, _state_type: Any) -> None:
            self._nodes: dict[str, Any] = {}
            self._entry_point = ""
            self._finish_point = ""

        def add_node(self, name: str, func: Any) -> None:
            self._nodes[name] = func

        def set_entry_point(self, name: str) -> None:
            self._entry_point = name

        def add_edge(self, _source: str, _target: str) -> None:
            return None

        def set_finish_point(self, name: str) -> None:
            self._finish_point = name

        def compile(self) -> Any:
            return _FallbackGraph(self._nodes, self._entry_point, self._finish_point)

from agentic_dev.next_step import (
    NextStepRecommendation,
    StoryEvidence,
    choose_recommendation,
    format_bool,
    format_bullet_list,
    format_optional_bool,
    format_path_names,
    format_result_files,
    inspect_story,
    text_value,
    validate_story_folder,
)


WORKFLOW_PREVIEW_NODES = (
    "collect_story_state",
    "determine_next_action",
    "write_preview",
)


class WorkflowPreviewState(TypedDict, total=False):
    project_path: Path
    story: str
    story_path: Path
    reports_path: Path
    evidence: StoryEvidence
    current_state: dict[str, Any]
    evidence_inspected: list[str]
    recommendation: NextStepRecommendation
    recommended_next_action: str
    suggested_command: str | None
    next_action: str
    graph_nodes_visited: list[str]
    result_path: Path
    report_path: Path
    terminal_summary: str


@dataclass(frozen=True)
class WorkflowPreviewResult:
    story: str
    story_path: Path
    result_path: Path
    report_path: Path
    recommended_next_action: str
    suggested_command: str | None
    terminal_summary: str
    graph_nodes_visited: list[str]


def build_workflow_preview_graph():
    """Build the LangGraph preview graph without persistence or model calls."""
    graph = StateGraph(WorkflowPreviewState)
    graph.add_node("collect_story_state", collect_story_state)
    graph.add_node("determine_next_action", determine_next_action)
    graph.add_node("write_preview", write_preview)
    graph.set_entry_point("collect_story_state")
    graph.add_edge("collect_story_state", "determine_next_action")
    graph.add_edge("determine_next_action", "write_preview")
    graph.set_finish_point("write_preview")
    return graph.compile()


def run_workflow_preview(project_path: Path, story: str) -> WorkflowPreviewResult:
    """Preview the next workflow route for a story using a read-only LangGraph route."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story
    validate_story_folder(story_path)

    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    graph = build_workflow_preview_graph()
    final_state = graph.invoke(
        {
            "project_path": project_path,
            "story": story,
            "story_path": story_path,
            "reports_path": reports_path,
            "graph_nodes_visited": [],
        }
    )

    return WorkflowPreviewResult(
        story=story,
        story_path=story_path,
        result_path=final_state["result_path"],
        report_path=final_state["report_path"],
        recommended_next_action=final_state["recommended_next_action"],
        suggested_command=final_state.get("suggested_command"),
        terminal_summary=final_state["terminal_summary"],
        graph_nodes_visited=final_state["graph_nodes_visited"],
    )


def collect_story_state(state: WorkflowPreviewState) -> WorkflowPreviewState:
    project_path = state["project_path"]
    story_path = state["story_path"]
    story = state["story"]

    evidence = inspect_story(project_path, story_path, story)
    return {
        "evidence": evidence,
        "current_state": summarize_current_state(evidence),
        "evidence_inspected": list_evidence_inspected(evidence),
        "graph_nodes_visited": append_node(state, "collect_story_state"),
    }


def determine_next_action(state: WorkflowPreviewState) -> WorkflowPreviewState:
    recommendation = choose_recommendation(state["evidence"])
    return {
        "recommendation": recommendation,
        "recommended_next_action": recommendation.title,
        "suggested_command": recommendation.command,
        "next_action": recommendation.title,
        "graph_nodes_visited": append_node(state, "determine_next_action"),
    }


def write_preview(state: WorkflowPreviewState) -> WorkflowPreviewState:
    reports_path = state["reports_path"]
    result_path = reports_path / "workflow_preview_result.yaml"
    report_path = reports_path / "workflow_preview_report.md"
    graph_nodes_visited = append_node(state, "write_preview")

    result_data = {
        "story": state["story"],
        "current_state": state["current_state"],
        "recommended_next_action": state["recommended_next_action"],
        "suggested_command": state.get("suggested_command"),
        "graph_nodes_visited": graph_nodes_visited,
        "automation_level": "preview_only",
        "executed_agents": False,
        "called_cloud_models": False,
        "called_github_apis": False,
        "committed_or_merged": False,
        "deployed": False,
        "next_action": state["next_action"],
    }

    result_path.write_text(
        yaml.safe_dump(result_data, sort_keys=False),
        encoding="utf-8",
    )
    write_workflow_preview_report(report_path, state, graph_nodes_visited)

    terminal_summary = format_terminal_summary(
        state["story"],
        state["recommendation"],
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


def summarize_current_state(evidence: StoryEvidence) -> dict[str, Any]:
    return {
        "status": text_value(evidence.status_data.get("status")) or "missing",
        "ready_for_review": evidence.status_data.get("ready_for_review"),
        "blocked_by": text_value(evidence.status_data.get("blocked_by")),
        "agent_plan_exists": evidence.agent_plan_exists,
        "prompt_pack_exists": evidence.prompt_pack_exists,
        "prompt_file_count": len(evidence.prompt_files),
        "report_files": [path.name for path in evidence.reports],
        "review_bundle_file_count": len(evidence.review_bundle_files),
        "cloud_review_export_exists": evidence.cloud_review_export_exists,
        "remote_dev_packet_exists": evidence.remote_dev_packet_exists,
        "test_plan_uses_layers": evidence.test_plan_uses_layers,
        "result_files": sorted(evidence.result_data),
        "warnings": evidence.warnings,
    }


def list_evidence_inspected(evidence: StoryEvidence) -> list[str]:
    inspected = [
        "story.md",
        "status.yaml",
        "test_plan.yaml",
        "agent_plan.yaml" if evidence.agent_plan_exists else "agent_plan.yaml missing",
        "prompt_pack/" if evidence.prompt_pack_exists else "prompt_pack/ missing",
    ]
    inspected.extend(f"prompt_pack/{path.name}" for path in evidence.prompt_files)
    inspected.extend(f"reports/{path.name}" for path in evidence.reports)
    inspected.extend(f"review_bundle/{path.name}" for path in evidence.review_bundle_files)
    if evidence.cloud_review_export_exists:
        inspected.append("cloud_review_packet/cloud_review_export.md")
    if evidence.remote_dev_packet_exists:
        inspected.append("remote_dev_validation/remote_dev_packet.md")
    return inspected


def write_workflow_preview_report(
    report_path: Path,
    state: WorkflowPreviewState,
    graph_nodes_visited: list[str],
) -> None:
    evidence = state["evidence"]
    recommendation = state["recommendation"]
    content = f"""# Workflow Preview Report

## Story

{state["story"]}

## Why LangGraph is being used here

This is the first LangGraph integration for the workflow. It is a preview graph only: it reads
story state, routes through explicit nodes, and explains the next safe action without executing
agents or calling models. LangGraph is being introduced here so future orchestration can reuse the
same route shape after the workflow rules are clear.

## Graph nodes visited

{format_bullet_list(graph_nodes_visited)}
## Evidence inspected

{format_bullet_list(state["evidence_inspected"])}
## Current state

- status.yaml status: {text_value(evidence.status_data.get("status")) or "missing"}
- ready_for_review: {format_optional_bool(evidence.status_data.get("ready_for_review"))}
- agent_plan.yaml: {format_bool(evidence.agent_plan_exists)}
- prompt_pack: {format_bool(evidence.prompt_pack_exists)} ({len(evidence.prompt_files)} prompt file(s))
- reports: {format_path_names(evidence.reports)}
- review_bundle: {format_path_names(evidence.review_bundle_files)}
- cloud_review_packet/cloud_review_export.md: {format_bool(evidence.cloud_review_export_exists)}
- remote_dev_validation/remote_dev_packet.md: {format_bool(evidence.remote_dev_packet_exists)}
- test_plan.yaml uses test_layers_version: 1: {format_bool(evidence.test_plan_uses_layers)}
- result files: {format_result_files(evidence.result_data)}

## Recommended next action

{recommendation.title}

## Suggested command

{recommendation.command or "No command. Human review or manual correction is required."}

## Why

{recommendation.reason}

## Details

{format_bullet_list(recommendation.details)}
## Warnings

{format_bullet_list(evidence.warnings or ["None."])}
## Safety reminders

- This is a preview graph only.
- It did not execute agents through the configured agent runtime.
- It did not call cloud models or GitHub APIs.
- It did not run shell commands, commit, push, merge, or deploy.
- It does not recommend automatic merge or automatic deployment.
- Human final approval is always required before merge.

## Future orchestration notes

Later LangGraph workflows may orchestrate prepare-story, configured agent runtime execution,
finalize-story, cloud review packet creation, merge readiness, remote-dev evidence routing, and
support queue pauses. This preview does not use LangGraph persistence, checkpointing, or
human-in-the-loop pause/resume yet.
"""
    report_path.write_text(content, encoding="utf-8")


def format_terminal_summary(
    story: str,
    recommendation: NextStepRecommendation,
    result_path: Path,
    report_path: Path,
    graph_nodes_visited: list[str],
) -> str:
    lines = [
        f"Workflow preview for {story}:",
        "Route: " + " -> ".join(graph_nodes_visited),
        f"Recommended next action: {recommendation.title}",
        f"Why: {recommendation.reason}",
    ]
    if recommendation.command:
        lines.append(f"Suggested command: {recommendation.command}")
    else:
        lines.append("Suggested command: none")
    lines.extend(
        [
            "Safety: preview only. No agents, cloud models, GitHub APIs, merge, or deployment ran.",
            "Human final approval is always required before merge.",
            f"Result written to: {result_path}",
            f"Report written to: {report_path}",
        ]
    )
    return "\n".join(lines)


def append_node(state: WorkflowPreviewState, node_name: str) -> list[str]:
    return [*state.get("graph_nodes_visited", []), node_name]
