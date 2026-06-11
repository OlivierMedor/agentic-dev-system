from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.prompt_pack import load_agent_plan, ordered_assigned_agents, text_value


CODEX_TASK_STATUS_READY = "CODEX_TASKS_READY"
CODEX_TASK_STATUS_READY_WITH_WARNINGS = "CODEX_TASKS_READY_WITH_WARNINGS"

BUILD_CONTEXT_HINT = "agentic build-context --story {story} --all --force"

STANDARD_AGENT_EXECUTION_ORDER = [
    "research_agent",
    "planner_agent",
    "developer_agent",
    "test_agent",
    "docs_agent",
    "security_quality_agent",
    "local_reviewer_agent",
]

DO_NOT_DO_ITEMS = [
    "do not merge",
    "do not deploy",
    "do not call cloud models",
    "do not commit secrets",
    "do not modify unrelated files",
    "do not bypass artifact-policy",
]

VALIDATION_COMMANDS = [
    "docker compose run --rm dev pytest",
    "docker compose run --rm dev ruff check .",
    "docker compose run --rm dev agentic artifact-policy",
    "docker compose run --rm dev agentic public-readiness",
    "docker compose run --rm dev agentic runtime-config validate",
    "docker compose run --rm dev agentic project-status",
]


@dataclass(frozen=True)
class CodexTaskEntry:
    agent_id: str
    path: Path
    status: str
    model_recommendation: str
    required_output_report_path: str
    execution_position: int | None
    previous_agent: str | None
    next_agent: str | None
    warnings: list[str]


@dataclass(frozen=True)
class CodexTaskResult:
    project_path: Path
    story: str
    status: str
    generated_files: list[Path]
    skipped_files: list[Path]
    warnings: list[str]
    recommended_execution_order: list[str]
    tasks: list[CodexTaskEntry]
    result_path: Path
    report_path: Path
    codex_tasks_path: Path

    @property
    def terminal_summary(self) -> str:
        lines = [
            f"Codex tasks created for: {self.story}",
            f"Status: {self.status}",
            f"Generated files: {len(self.generated_files)}",
            f"Skipped files: {len(self.skipped_files)}",
            f"Result: {self.result_path}",
            f"Report: {self.report_path}",
            f"Task folder: {self.codex_tasks_path}",
            "Safety: Codex was not invoked; no cloud models, agents, GitHub APIs, commits, merges, or deploys were called.",
        ]

        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"  - {warning}" for warning in self.warnings)

        return "\n".join(lines)


def create_codex_tasks(
    project_path: Path,
    story: str,
    *,
    agent: str | None = None,
    all_agents: bool = False,
    force: bool = False,
    model: str | None = None,
) -> CodexTaskResult:
    """Create Codex-ready task files from existing role context packets."""
    resolved_project_path = project_path.resolve()
    story_path = resolved_project_path / "stories" / story

    if not story_path.exists() or not story_path.is_dir():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if agent and all_agents:
        raise ValueError("Use either --agent or --all, not both.")

    role_context_path = story_path / "reports" / "role_context"
    agent_plan_context = load_agent_plan_context(story_path)
    selected_context_packets = select_context_packets(
        role_context_path,
        story,
        agent,
        agent_plan_context.recommended_execution_order,
    )

    codex_tasks_path = story_path / "reports" / "codex_tasks"
    codex_tasks_path.mkdir(parents=True, exist_ok=True)
    (codex_tasks_path / ".gitkeep").touch()

    runtime_models, runtime_warnings = load_runtime_model_recommendations(resolved_project_path)

    tasks: list[CodexTaskEntry] = []
    generated_files: list[Path] = []
    skipped_files: list[Path] = []
    warnings: list[str] = [*runtime_warnings]

    for context_path in selected_context_packets:
        agent_id = context_path.name.removesuffix("_context.md")
        task_path = codex_tasks_path / f"{agent_id}_codex_task.md"
        context_content = context_path.read_text(encoding="utf-8")
        metadata = agent_plan_context.agent_metadata.get(agent_id, {})
        model_recommendation = select_model_recommendation(agent_id, model, runtime_models)
        order_context = execution_order_context(
            agent_id,
            agent_plan_context.recommended_execution_order,
        )
        required_output_path = text_value(
            metadata,
            "expected_output",
            parse_markdown_section(context_content, "Expected Output"),
        ).strip()
        role_objective = text_value(
            metadata,
            "responsibility",
            parse_markdown_section(context_content, "Role Responsibility"),
        ).strip()

        if task_path.exists() and not force:
            warning = f"Codex task already exists and was not overwritten: {task_path}"
            skipped_files.append(task_path)
            warnings.append(warning)
            tasks.append(
                CodexTaskEntry(
                    agent_id=agent_id,
                    path=task_path,
                    status="skipped_existing",
                    model_recommendation=model_recommendation,
                    required_output_report_path=required_output_path,
                    execution_position=order_context.position,
                    previous_agent=order_context.previous_agent,
                    next_agent=order_context.next_agent,
                    warnings=[warning],
                ),
            )
            continue

        task_path.write_text(
            format_codex_task_file(
                story=story,
                agent_id=agent_id,
                model_recommendation=model_recommendation,
                order_context=order_context,
                role_objective=role_objective,
                required_output_report_path=required_output_path,
                context_content=context_content,
            ),
            encoding="utf-8",
        )
        generated_files.append(task_path)
        tasks.append(
            CodexTaskEntry(
                agent_id=agent_id,
                path=task_path,
                status="written",
                model_recommendation=model_recommendation,
                required_output_report_path=required_output_path,
                execution_position=order_context.position,
                previous_agent=order_context.previous_agent,
                next_agent=order_context.next_agent,
                warnings=[],
            ),
        )

    status = CODEX_TASK_STATUS_READY_WITH_WARNINGS if warnings else CODEX_TASK_STATUS_READY
    result_path = story_path / "reports" / "codex_task_result.yaml"
    report_path = story_path / "reports" / "codex_task_report.md"

    result = CodexTaskResult(
        project_path=resolved_project_path,
        story=story,
        status=status,
        generated_files=generated_files,
        skipped_files=skipped_files,
        warnings=dedupe_preserve_order(warnings),
        recommended_execution_order=agent_plan_context.recommended_execution_order,
        tasks=tasks,
        result_path=result_path,
        report_path=report_path,
        codex_tasks_path=codex_tasks_path,
    )

    result_path.write_text(format_codex_task_result_yaml(result), encoding="utf-8")
    report_path.write_text(format_codex_task_report(result), encoding="utf-8")

    return result


def select_context_packets(
    role_context_path: Path,
    story: str,
    agent: str | None,
    recommended_execution_order: list[str],
) -> list[Path]:
    if agent is not None:
        context_path = role_context_path / f"{agent}_context.md"
        if not context_path.exists():
            raise FileNotFoundError(
                f"Role context packet is missing: {context_path}. "
                f"Run: {BUILD_CONTEXT_HINT.format(story=story)}",
            )
        return [context_path]

    if not role_context_path.exists():
        raise FileNotFoundError(
            f"Role context folder is missing: {role_context_path}. "
            f"Run: {BUILD_CONTEXT_HINT.format(story=story)}",
        )

    context_packets = sorted(
        role_context_path.glob("*_context.md"),
        key=lambda path: context_packet_sort_key(path, recommended_execution_order),
    )
    if not context_packets:
        raise FileNotFoundError(
            f"No role context packets found in: {role_context_path}. "
            f"Run: {BUILD_CONTEXT_HINT.format(story=story)}",
        )

    return context_packets


@dataclass(frozen=True)
class AgentPlanContext:
    agent_metadata: dict[str, dict[str, Any]]
    recommended_execution_order: list[str]


@dataclass(frozen=True)
class ExecutionOrderContext:
    position: int | None
    previous_agent: str | None
    next_agent: str | None


def load_agent_plan_context(story_path: Path) -> AgentPlanContext:
    agent_plan_path = story_path / "agent_plan.yaml"
    if not agent_plan_path.exists():
        return AgentPlanContext(
            agent_metadata={},
            recommended_execution_order=STANDARD_AGENT_EXECUTION_ORDER,
        )

    agent_plan = load_agent_plan(agent_plan_path)
    metadata = {
        text_value(assigned_agent, "id", ""): assigned_agent
        for assigned_agent in ordered_assigned_agents(agent_plan)
    }
    execution_order = agent_plan.get("execution_order")
    if isinstance(execution_order, list) and any(isinstance(item, str) for item in execution_order):
        recommended_execution_order = [
            item.strip()
            for item in execution_order
            if isinstance(item, str) and item.strip()
        ]
    else:
        recommended_execution_order = STANDARD_AGENT_EXECUTION_ORDER

    return AgentPlanContext(
        agent_metadata=metadata,
        recommended_execution_order=recommended_execution_order,
    )


def context_packet_sort_key(path: Path, recommended_execution_order: list[str]) -> tuple[int, str]:
    agent_id = path.name.removesuffix("_context.md")
    try:
        return recommended_execution_order.index(agent_id), agent_id
    except ValueError:
        return len(recommended_execution_order), agent_id


def execution_order_context(
    agent_id: str,
    recommended_execution_order: list[str],
) -> ExecutionOrderContext:
    if agent_id not in recommended_execution_order:
        return ExecutionOrderContext(
            position=None,
            previous_agent=None,
            next_agent=None,
        )

    index = recommended_execution_order.index(agent_id)
    previous_agent = recommended_execution_order[index - 1] if index > 0 else None
    next_agent = (
        recommended_execution_order[index + 1]
        if index < len(recommended_execution_order) - 1
        else None
    )
    return ExecutionOrderContext(
        position=index + 1,
        previous_agent=previous_agent,
        next_agent=next_agent,
    )


def load_runtime_model_recommendations(project_path: Path) -> tuple[dict[str, str], list[str]]:
    runtime_path = project_path / ".agentic" / "agent_runtime.yaml"
    if not runtime_path.exists():
        return {}, []

    try:
        loaded = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        return {}, [f"Could not read model recommendations from {runtime_path}: {error}"]

    if not isinstance(loaded, dict):
        return {}, [f"Runtime config is not a YAML mapping: {runtime_path}"]

    agents = loaded.get("agents")
    if not isinstance(agents, dict):
        return {}, [f"Runtime config has no agents mapping: {runtime_path}"]

    recommendations: dict[str, str] = {}
    for agent_id, agent_config in agents.items():
        if not isinstance(agent_id, str) or not isinstance(agent_config, dict):
            continue

        model = agent_config.get("model")
        provider = agent_config.get("provider")
        if isinstance(model, str) and model.strip():
            recommendation = model.strip()
            if isinstance(provider, str) and provider.strip():
                recommendation = f"{recommendation} ({provider.strip()})"
            recommendations[agent_id] = recommendation

    return recommendations, []


def select_model_recommendation(
    agent_id: str,
    override_model: str | None,
    runtime_models: dict[str, str],
) -> str:
    if override_model is not None and override_model.strip():
        return override_model.strip()

    return runtime_models.get(agent_id, "configured Codex runtime")


def format_codex_task_file(
    *,
    story: str,
    agent_id: str,
    model_recommendation: str,
    order_context: ExecutionOrderContext,
    role_objective: str,
    required_output_report_path: str,
    context_content: str,
) -> str:
    return f"""# Codex Task: {agent_id}

## Agent Identity

- Agent ID: `{agent_id}`
- Runtime: Codex

## Story Slug

`{story}`

## Model Recommendation

{model_recommendation}

This is only a written recommendation. This task file does not switch the active Codex model.

## Recommended Execution Order Context

- Position: {format_position(order_context.position)}
- Usually comes before this agent: {order_context.previous_agent or "None"}
- Usually comes after this agent: {order_context.next_agent or "None"}
- Role reminder: only do `{agent_id}` work for this story.

## Safety Rules

- Treat the context packet as local deterministic input.
- Make only changes required by the role objective.
- Keep generated runtime artifacts out of Git unless policy explicitly allows a `.gitkeep`.
- Human review is still required before merge.
- This file was generated without invoking Codex, cloud models, agents, GitHub APIs, commits, merges, or deploys.

## Context Packet Content

```markdown
{context_content.rstrip()}
```

## Exact Role Objective

{role_objective or "Use the role context packet to complete the assigned agent responsibility."}

## Required Output Report Path

`{required_output_report_path or "reports/developer_report.md"}`

## Validation Commands

{format_bullets(VALIDATION_COMMANDS)}

## Do-Not-Do List

{format_bullets(DO_NOT_DO_ITEMS)}
"""


def format_codex_task_result_yaml(result: CodexTaskResult) -> str:
    data = {
        "story": result.story,
        "status": result.status,
        "generated_files": [
            relative_to_project(result.project_path, path) for path in result.generated_files
        ],
        "skipped_files": [
            relative_to_project(result.project_path, path) for path in result.skipped_files
        ],
        "warnings": result.warnings,
        "recommended_execution_order": result.recommended_execution_order,
        "tasks": [
            {
                "agent": task.agent_id,
                "path": relative_to_project(result.project_path, task.path),
                "status": task.status,
                "model_recommendation": task.model_recommendation,
                "required_output_report_path": task.required_output_report_path,
                "execution_position": task.execution_position,
                "previous_agent": task.previous_agent,
                "next_agent": task.next_agent,
                "warnings": task.warnings,
            }
            for task in result.tasks
        ],
        "safety_flags": safety_flags(),
    }

    return yaml.safe_dump(data, sort_keys=False)


def format_codex_task_report(result: CodexTaskResult) -> str:
    lines = [
        "# Codex Task Report",
        "",
        f"- Story: `{result.story}`",
        f"- Status: {result.status}",
        f"- Generated files: {len(result.generated_files)}",
        f"- Skipped files: {len(result.skipped_files)}",
        "",
        "## Recommended Execution Order",
        "",
        format_numbered_order(result.recommended_execution_order),
        "",
        "## Tasks",
        "",
    ]

    for task in result.tasks:
        lines.extend(
            [
                f"### {task.agent_id}",
                "",
                f"- Status: {task.status}",
                f"- Path: `{relative_to_project(result.project_path, task.path)}`",
                f"- Model recommendation: {task.model_recommendation}",
                f"- Required output report path: `{task.required_output_report_path}`",
                f"- Execution position: {format_position(task.execution_position)}",
                f"- Usually comes before: {task.previous_agent or 'None'}",
                f"- Usually comes after: {task.next_agent or 'None'}",
                "",
            ],
        )

    lines.extend(
        [
            "## Warnings",
            "",
            format_bullets(result.warnings),
            "",
            "## Safety Flags",
            "",
            *[f"- {key}: false" for key in safety_flags()],
            "",
        ],
    )

    return "\n".join(lines)


def parse_markdown_section(markdown: str, heading: str) -> str:
    marker = f"## {heading}"
    lines = markdown.splitlines()
    in_section = False
    section_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if in_section:
                break
            in_section = line.strip() == marker
            continue

        if in_section:
            section_lines.append(line)

    return "\n".join(section_lines).strip()


def safety_flags() -> dict[str, bool]:
    return {
        "called_codex": False,
        "called_cloud_models": False,
        "executed_agents": False,
        "called_github_apis": False,
        "committed_or_merged": False,
        "deployed": False,
    }


def format_position(position: int | None) -> str:
    if position is None:
        return "Not listed in recommended_execution_order"
    return str(position)


def format_numbered_order(items: list[str]) -> str:
    if not items:
        return "No recommended execution order recorded."

    return "\n".join(f"{index}. {agent_id}" for index, agent_id in enumerate(items, start=1))


def format_bullets(items: list[str]) -> str:
    if not items:
        return "- None."
    return "\n".join(f"- {item}" for item in items)


def relative_to_project(project_path: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_path.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped
