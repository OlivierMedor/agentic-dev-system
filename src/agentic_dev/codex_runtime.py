from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.prompt_pack import load_agent_plan, ordered_assigned_agents, text_value
from agentic_dev.runtime_config import CodexRuntimeConfig, load_codex_runtime_config


CODEX_TASK_STATUS_READY = "CODEX_TASKS_READY"
CODEX_TASK_STATUS_READY_WITH_WARNINGS = "CODEX_TASKS_READY_WITH_WARNINGS"
CODEX_RUNTIME_RESULT_FILENAME = "codex_runtime_execution_result.yaml"
CODEX_RUNTIME_REPORT_FILENAME = "codex_runtime_execution_report.md"

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


@dataclass(frozen=True)
class CodexRuntimeTaskExecution:
    agent_id: str
    status: str
    command: list[str]
    task_file: Path
    expected_report: Path
    exit_code: int | None
    stdout_path: Path | None
    stderr_path: Path | None
    duration_seconds: float | None
    summary: str


@dataclass(frozen=True)
class CodexRuntimeExecutionResult:
    project_path: Path
    story: str
    status: str
    config_path: Path
    result_path: Path
    report_path: Path
    executions: list[CodexRuntimeTaskExecution]

    @property
    def blocked(self) -> bool:
        return self.status.startswith("BLOCKED") or self.status == "FAILED"


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


def run_codex_task_runtime(
    project_path: Path,
    story: str,
) -> CodexRuntimeExecutionResult:
    resolved_project_path = project_path.resolve()
    story_path = resolved_project_path / "stories" / story
    if not story_path.exists() or not story_path.is_dir():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    config_path, config = load_codex_runtime_config(resolved_project_path)
    runtime_path = story_path / "reports" / "codex_runtime"
    runtime_path.mkdir(parents=True, exist_ok=True)

    executions: list[CodexRuntimeTaskExecution] = []
    status = "PASSED"

    for assigned_agent in ordered_assigned_agents(load_agent_plan(story_path / "agent_plan.yaml")):
        agent_id = text_value(assigned_agent, "id", "")
        expected_output = text_value(assigned_agent, "expected_output", "")
        expected_report = resolve_codex_runtime_expected_report(story_path, expected_output)
        if not agent_id or expected_report is None:
            continue

        task_file = story_path / "reports" / "codex_tasks" / f"{agent_id}_codex_task.md"
        command = render_codex_runtime_command(config, task_file)

        if expected_report.is_file():
            executions.append(
                CodexRuntimeTaskExecution(
                    agent_id=agent_id,
                    status="SKIPPED_EXISTING_REPORT",
                    command=command,
                    task_file=task_file,
                    expected_report=expected_report,
                    exit_code=None,
                    stdout_path=None,
                    stderr_path=None,
                    duration_seconds=None,
                    summary=f"Report already exists: {expected_report}",
                )
            )
            continue

        if not task_file.is_file():
            status = "BLOCKED_MISSING_CODEX_TASK"
            executions.append(
                CodexRuntimeTaskExecution(
                    agent_id=agent_id,
                    status=status,
                    command=command,
                    task_file=task_file,
                    expected_report=expected_report,
                    exit_code=None,
                    stdout_path=None,
                    stderr_path=None,
                    duration_seconds=None,
                    summary=f"Codex task file is missing: {task_file}",
                )
            )
            break

        execution = run_one_codex_task(
            project_path=resolved_project_path,
            runtime_path=runtime_path,
            agent_id=agent_id,
            config=config,
            task_file=task_file,
            expected_report=expected_report,
        )
        executions.append(execution)
        if execution.status.startswith("BLOCKED") or execution.status == "FAILED":
            status = execution.status
            break

    result_path = story_path / "reports" / CODEX_RUNTIME_RESULT_FILENAME
    report_path = story_path / "reports" / CODEX_RUNTIME_REPORT_FILENAME
    result = CodexRuntimeExecutionResult(
        project_path=resolved_project_path,
        story=story,
        status=status,
        config_path=config_path,
        result_path=result_path,
        report_path=report_path,
        executions=executions,
    )
    result_path.write_text(format_codex_runtime_execution_result(result), encoding="utf-8")
    report_path.write_text(format_codex_runtime_execution_report(result), encoding="utf-8")
    return result


def run_one_codex_task(
    *,
    project_path: Path,
    runtime_path: Path,
    agent_id: str,
    config: CodexRuntimeConfig,
    task_file: Path,
    expected_report: Path,
) -> CodexRuntimeTaskExecution:
    command = render_codex_runtime_command(config, task_file)
    stdout_path = runtime_path / f"{agent_id}_stdout.txt"
    stderr_path = runtime_path / f"{agent_id}_stderr.txt"
    start = time.monotonic()

    try:
        completed = subprocess.run(
            command,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        duration = time.monotonic() - start
        write_text_artifact(stdout_path, "")
        write_text_artifact(stderr_path, f"Command not found: {config.command}\n")
        return CodexRuntimeTaskExecution(
            agent_id=agent_id,
            status="BLOCKED_CODEX_COMMAND_NOT_FOUND",
            command=command,
            task_file=task_file,
            expected_report=expected_report,
            exit_code=None,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            duration_seconds=duration,
            summary=f"Codex command was not found: {config.command}",
        )
    except subprocess.TimeoutExpired as error:
        duration = time.monotonic() - start
        write_text_artifact(stdout_path, normalize_subprocess_text(error.stdout))
        write_text_artifact(stderr_path, normalize_subprocess_text(error.stderr))
        return CodexRuntimeTaskExecution(
            agent_id=agent_id,
            status="BLOCKED_CODEX_TIMEOUT",
            command=command,
            task_file=task_file,
            expected_report=expected_report,
            exit_code=None,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            duration_seconds=duration,
            summary=f"Codex timed out after {config.timeout_seconds} second(s).",
        )

    duration = time.monotonic() - start
    write_text_artifact(stdout_path, completed.stdout)
    write_text_artifact(stderr_path, completed.stderr)

    if completed.returncode != 0:
        return CodexRuntimeTaskExecution(
            agent_id=agent_id,
            status="BLOCKED_CODEX_NONZERO_EXIT",
            command=command,
            task_file=task_file,
            expected_report=expected_report,
            exit_code=completed.returncode,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            duration_seconds=duration,
            summary=f"Codex exited with code {completed.returncode} for {agent_id}.",
        )

    if not expected_report.is_file():
        return CodexRuntimeTaskExecution(
            agent_id=agent_id,
            status="BLOCKED_MISSING_CODEX_REPORT",
            command=command,
            task_file=task_file,
            expected_report=expected_report,
            exit_code=completed.returncode,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            duration_seconds=duration,
            summary=(
                "Codex exited successfully but did not create the expected report: "
                f"{expected_report}"
            ),
        )

    return CodexRuntimeTaskExecution(
        agent_id=agent_id,
        status="PASSED",
        command=command,
        task_file=task_file,
        expected_report=expected_report,
        exit_code=completed.returncode,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        duration_seconds=duration,
        summary=f"Codex completed {agent_id}; expected report exists.",
    )


def render_codex_runtime_command(config: CodexRuntimeConfig, task_file: Path) -> list[str]:
    resolved_task_file = str(task_file.resolve())
    return [
        config.command,
        *[argument.replace("{task_file}", resolved_task_file) for argument in config.args],
    ]


def resolve_codex_runtime_expected_report(
    story_path: Path,
    expected_output: str,
) -> Path | None:
    if not expected_output:
        return None
    path = Path(expected_output)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "reports":
        return story_path / path
    return None


def write_text_artifact(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def normalize_subprocess_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def format_codex_runtime_execution_result(result: CodexRuntimeExecutionResult) -> str:
    data = {
        "story": result.story,
        "status": result.status,
        "config_path": relative_to_project(result.project_path, result.config_path),
        "executions": [
            {
                "agent": execution.agent_id,
                "status": execution.status,
                "command": redact_command_paths(result.project_path, execution.command),
                "task_file": relative_to_project(result.project_path, execution.task_file),
                "expected_report": relative_to_project(
                    result.project_path,
                    execution.expected_report,
                ),
                "exit_code": execution.exit_code,
                "stdout_path": (
                    relative_to_project(result.project_path, execution.stdout_path)
                    if execution.stdout_path is not None
                    else None
                ),
                "stderr_path": (
                    relative_to_project(result.project_path, execution.stderr_path)
                    if execution.stderr_path is not None
                    else None
                ),
                "duration_seconds": execution.duration_seconds,
                "summary": execution.summary,
            }
            for execution in result.executions
        ],
        "safety_flags": {
            "called_codex": any(
                execution.exit_code is not None or execution.stdout_path is not None
                for execution in result.executions
            ),
            "called_github_apis": False,
            "committed_or_merged": False,
            "pushed": False,
            "merged": False,
            "deployed": False,
            "opened_pr": False,
            "ran_destructive_commands": False,
        },
    }
    return yaml.safe_dump(data, sort_keys=False)


def format_codex_runtime_execution_report(result: CodexRuntimeExecutionResult) -> str:
    lines = [
        "# Codex Runtime Execution Report",
        "",
        f"- Story: `{result.story}`",
        f"- Status: {result.status}",
        f"- Runtime config: `{relative_to_project(result.project_path, result.config_path)}`",
        "",
        "## Executions",
        "",
    ]
    if not result.executions:
        lines.append("- None.")
    for execution in result.executions:
        lines.extend(
            [
                f"### {execution.agent_id}",
                "",
                f"- Status: {execution.status}",
                f"- Command: `{format_command_for_report(result.project_path, execution.command)}`",
                f"- Task file: `{relative_to_project(result.project_path, execution.task_file)}`",
                "- Expected report: "
                f"`{relative_to_project(result.project_path, execution.expected_report)}`",
                f"- Exit code: {execution.exit_code if execution.exit_code is not None else 'None'}",
                f"- Summary: {execution.summary}",
                "",
            ],
        )
        if execution.stdout_path is not None:
            lines.append(
                f"- Stdout: `{relative_to_project(result.project_path, execution.stdout_path)}`"
            )
        if execution.stderr_path is not None:
            lines.append(
                f"- Stderr: `{relative_to_project(result.project_path, execution.stderr_path)}`"
            )
        lines.append("")

    lines.extend(
        [
            "## Safety",
            "",
            "- Used the allowlisted Codex command template from runtime config.",
            "- Ran one role task at a time.",
            "- Did not call GitHub APIs.",
            "- Did not commit, push, merge, deploy, or open a PR.",
            "- Stopped before merge.",
            "",
        ]
    )
    return "\n".join(lines)


def format_command_for_report(project_path: Path, command: list[str]) -> str:
    return " ".join(redact_command_paths(project_path, command))


def redact_command_paths(project_path: Path, command: list[str]) -> list[str]:
    return [relative_to_project(project_path, Path(part)) if looks_like_path(part) else part for part in command]


def looks_like_path(value: str) -> bool:
    return "/" in value or "\\" in value


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
