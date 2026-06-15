from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.codex_runtime import create_codex_tasks, run_codex_task_runtime
from agentic_dev.finalize_story import finalize_story
from agentic_dev.local_model_runtime import run_local_agent_draft
from agentic_dev.prepare_story import prepare_story
from agentic_dev.prompt_pack import load_agent_plan, ordered_assigned_agents, text_value
from agentic_dev.quality_gate import run_quality_gate
from agentic_dev.role_context import build_role_context
from agentic_dev.runtime_config import load_runtime_config


RUNNER_RESULT_FILENAME = "story_runner_result.yaml"
RUNNER_REPORT_FILENAME = "story_runner_report.md"

COMPLETED_STATUSES = {
    "ready_for_review",
    "READY_FOR_REVIEW",
    "READY_FOR_HUMAN_MERGE_DECISION",
    "READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION",
    "merged",
    "closed",
    "done",
    "complete",
    "completed",
}
BLOCKED_STATUSES = {"blocked", "BLOCKED"}

LOCAL_RUNTIME_AGENT_MAP = {
    "developer_agent": "developer_agent",
    "test_agent": "test_agent",
    "docs_agent": "docs_agent",
    "local_reviewer_agent": "reviewer_agent",
}


@dataclass(frozen=True)
class StoryResolution:
    project_path: Path
    story: str
    story_path: Path
    matched_by: str
    slug: str | None


@dataclass(frozen=True)
class StoryRunnerStep:
    name: str
    description: str


@dataclass(frozen=True)
class StoryRunnerStepResult:
    step: str
    status: str
    summary: str
    path: Path | None = None


@dataclass(frozen=True)
class StoryRunnerResult:
    story: str
    project_path: Path
    story_path: Path
    executed: bool
    status: str
    result_path: Path
    report_path: Path
    planned_steps: list[str]
    step_results: list[StoryRunnerStepResult]
    missing_reports: list[str]
    next_action: str
    terminal_summary: str


RuntimeRunner = Callable[[Path, str], list[StoryRunnerStepResult]]


def run_story(
    project_path: Path,
    story_ref: str,
    *,
    execute: bool = False,
    runtime_runner: RuntimeRunner | None = None,
) -> StoryRunnerResult:
    resolved = resolve_story(project_path, story_ref)
    reports_path = resolved.story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    planned_steps = build_story_runner_plan()
    step_results: list[StoryRunnerStepResult] = []
    missing_reports: list[str] = []
    status = "planned"
    next_action = "Review the planned story workflow. Rerun with --execute to run it."

    if execute:
        step_results = execute_story_steps(resolved, runtime_runner)
        failed_step = first_blocking_step(step_results)
        missing_reports = missing_required_agent_reports(resolved.story_path)

        if failed_step is not None:
            status = failed_step.status
            next_action = failed_step.summary
        elif missing_reports:
            status = "BLOCKED_MISSING_REPORTS"
            next_action = (
                "Required agent reports are missing: "
                + ", ".join(missing_reports)
                + ". Run the configured agent runtime or add the reports, then rerun run-story."
            )
            step_results.append(
                StoryRunnerStepResult(
                    step="verify-required-agent-reports",
                    status=status,
                    summary=next_action,
                )
            )
        else:
            finalize_result = finalize_story(resolved.project_path, resolved.story)
            step_results.append(
                StoryRunnerStepResult(
                    step="local-finalize",
                    status="PASSED" if finalize_result.ready_for_review else "REQUEST_CHANGES",
                    summary=f"finalize-story status: {finalize_result.status}",
                    path=finalize_result.finalize_result_path,
                )
            )
            quality_result = run_quality_gate(resolved.project_path, resolved.story)
            step_results.append(
                StoryRunnerStepResult(
                    step="quality-gate",
                    status=quality_result.status,
                    summary=f"quality-gate status: {quality_result.status}",
                    path=quality_result.result_path,
                )
            )
            status = "completed" if quality_result.ready_for_review else "REQUEST_CHANGES"
            next_action = (
                "Stop before merge. Human owner should review the story evidence."
                if quality_result.ready_for_review
                else quality_result.next_action
            )

    result_path = reports_path / RUNNER_RESULT_FILENAME
    report_path = reports_path / RUNNER_REPORT_FILENAME
    result = StoryRunnerResult(
        story=resolved.story,
        project_path=resolved.project_path,
        story_path=resolved.story_path,
        executed=execute,
        status=status,
        result_path=result_path,
        report_path=report_path,
        planned_steps=[step.name for step in planned_steps],
        step_results=step_results,
        missing_reports=missing_reports,
        next_action=next_action,
        terminal_summary=format_terminal_summary(
            resolved.story,
            resolved.project_path,
            execute,
            status,
            planned_steps,
            result_path,
            report_path,
            next_action,
        ),
    )
    write_story_runner_result(result)
    write_story_runner_report(result, resolved, planned_steps)
    return result


def run_next_story(
    project_path: Path,
    *,
    execute: bool = False,
    runtime_runner: RuntimeRunner | None = None,
) -> StoryRunnerResult:
    resolved_project_path = project_path.resolve()
    next_story = select_next_story(resolved_project_path)
    return run_story(
        resolved_project_path,
        next_story.story,
        execute=execute,
        runtime_runner=runtime_runner,
    )


def execute_story_steps(
    resolved: StoryResolution,
    runtime_runner: RuntimeRunner | None,
) -> list[StoryRunnerStepResult]:
    results: list[StoryRunnerStepResult] = []

    prepare_result = prepare_story(resolved.project_path, resolved.story)
    results.append(
        StoryRunnerStepResult(
            step="prepare-story",
            status="PASSED",
            summary=(
                "Prepared story workspace; "
                f"created or updated {len(prepare_result.prompt_files_created)} prompt file(s)."
            ),
            path=prepare_result.report_path,
        )
    )

    context_result = build_role_context(
        resolved.project_path,
        resolved.story,
        all_agents=True,
        force=False,
    )
    results.append(
        StoryRunnerStepResult(
            step="build-context",
            status=context_result.status,
            summary=f"Built or reused role context for {len(context_result.context_packets)} agent(s).",
            path=context_result.result_path,
        )
    )

    codex_result = create_codex_tasks(
        resolved.project_path,
        resolved.story,
        all_agents=True,
        force=False,
    )
    results.append(
        StoryRunnerStepResult(
            step="codex-task-create",
            status=codex_result.status,
            summary=f"Created or reused {len(codex_result.tasks)} Codex task file(s).",
            path=codex_result.result_path,
        )
    )

    missing_reports = missing_required_agent_reports(resolved.story_path)
    if not missing_reports:
        results.append(
            StoryRunnerStepResult(
                step="automatic-agent-runtime",
                status="SKIPPED_EXISTING_REPORTS",
                summary="All required agent reports already exist; skipping automatic runtime.",
            )
        )
        results.append(
            StoryRunnerStepResult(
                step="verify-required-agent-reports",
                status="PASSED",
                summary="All required agent reports exist.",
            )
        )
        return results

    try:
        runtime_results = (
            runtime_runner(resolved.project_path, resolved.story)
            if runtime_runner is not None
            else run_configured_runtime(resolved.project_path, resolved.story)
        )
    except (FileNotFoundError, ValueError) as error:
        results.append(
            StoryRunnerStepResult(
                step="automatic-agent-runtime",
                status="BLOCKED_MISSING_RUNTIME",
                summary=str(error),
            )
        )
        return results

    results.extend(runtime_results)
    if first_blocking_step(runtime_results) is not None:
        return results

    results.append(
        StoryRunnerStepResult(
            step="verify-required-agent-reports",
            status="PASSED",
            summary="Required agent reports will be checked before finalization.",
        )
    )
    return results


def run_configured_runtime(project_path: Path, story: str) -> list[StoryRunnerStepResult]:
    _, runtime_config = load_runtime_config(project_path)
    codex_runtime = runtime_config.get("codex_runtime")
    if isinstance(codex_runtime, dict) and codex_runtime.get("enabled") is True:
        return codex_runtime_step_results(project_path, story)

    local_model_runtime = runtime_config.get("local_model_runtime")
    if not isinstance(local_model_runtime, dict) or local_model_runtime.get("enabled") is not True:
        raise ValueError(
            "No automatic agent runtime is configured. Enable codex_runtime.enabled "
            "or local_model_runtime.enabled in .agentic/agent_runtime.yaml, or run the "
            "generated Codex task files manually and rerun run-story after required "
            "reports exist."
        )

    story_path = project_path.resolve() / "stories" / story
    results: list[StoryRunnerStepResult] = []
    for assigned_agent in load_ordered_agents(story_path):
        agent_id = text_value(assigned_agent, "id", "")
        local_agent = LOCAL_RUNTIME_AGENT_MAP.get(agent_id)
        expected_output = text_value(assigned_agent, "expected_output", "")
        output_path = resolve_expected_report_path(story_path, expected_output)

        if local_agent is None or output_path is None:
            results.append(
                StoryRunnerStepResult(
                    step=f"automatic-agent-runtime:{agent_id}",
                    status="SKIPPED_UNSUPPORTED_AGENT",
                    summary=f"No local automatic runtime mapping exists for {agent_id}.",
                )
            )
            continue

        if output_path.exists():
            results.append(
                StoryRunnerStepResult(
                    step=f"automatic-agent-runtime:{agent_id}",
                    status="SKIPPED_EXISTING_REPORT",
                    summary=f"Report already exists: {output_path}",
                    path=output_path,
                )
            )
            continue

        result = run_local_agent_draft(
            project_path=project_path,
            story=story,
            agent=local_agent,
            output_file=output_path.relative_to(project_path.resolve()),
            prompt_mode="slim",
            force=False,
        )
        results.append(
            StoryRunnerStepResult(
                step=f"automatic-agent-runtime:{agent_id}",
                status=result.status,
                summary=f"Local model draft saved to {result.output_file}",
                path=result.output_file,
            )
        )

    return results


def codex_runtime_step_results(project_path: Path, story: str) -> list[StoryRunnerStepResult]:
    result = run_codex_task_runtime(project_path, story)
    results: list[StoryRunnerStepResult] = []

    for execution in result.executions:
        results.append(
            StoryRunnerStepResult(
                step=f"automatic-agent-runtime:{execution.agent_id}",
                status=execution.status,
                summary=execution.summary,
                path=execution.expected_report if execution.expected_report.is_file() else None,
            )
        )

    results.append(
        StoryRunnerStepResult(
            step="automatic-agent-runtime:codex",
            status=result.status,
            summary=f"Codex runtime execution status: {result.status}",
            path=result.report_path,
        )
    )

    return results


def resolve_story(project_path: Path, story_ref: str) -> StoryResolution:
    resolved_project_path = project_path.resolve()
    stories_path = resolved_project_path / "stories"
    if not stories_path.exists() or not stories_path.is_dir():
        raise FileNotFoundError(f"Stories folder does not exist: {stories_path}")

    exact_path = stories_path / story_ref
    if exact_path.exists() and exact_path.is_dir():
        status_data = load_optional_yaml(exact_path / "status.yaml")
        return StoryResolution(
            project_path=resolved_project_path,
            story=exact_path.name,
            story_path=exact_path,
            matched_by="folder",
            slug=optional_text(status_data.get("slug")),
        )

    matches: list[StoryResolution] = []
    for story_path in sorted(path for path in stories_path.iterdir() if path.is_dir()):
        status_data = load_optional_yaml(story_path / "status.yaml")
        slug = optional_text(status_data.get("slug"))
        story_id = optional_text(status_data.get("story_id") or status_data.get("id"))
        if story_ref in {slug, story_id}:
            matches.append(
                StoryResolution(
                    project_path=resolved_project_path,
                    story=story_path.name,
                    story_path=story_path,
                    matched_by="slug" if story_ref == slug else "story_id",
                    slug=slug,
                )
            )

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(match.story for match in matches)
        raise ValueError(f"Story reference is ambiguous: {story_ref}. Matches: {names}")

    raise FileNotFoundError(
        f"Could not resolve story {story_ref!r} by folder name, slug, or story_id."
    )


def select_next_story(project_path: Path) -> StoryResolution:
    stories_path = project_path.resolve() / "stories"
    if not stories_path.exists() or not stories_path.is_dir():
        raise FileNotFoundError(f"Stories folder does not exist: {stories_path}")

    dependencies = load_blueprint_dependencies(project_path)
    candidates = [
        story_path
        for story_path in stories_path.iterdir()
        if story_path.is_dir()
        and story_is_runnable(story_path)
        and dependencies_satisfied(project_path, story_path, dependencies)
    ]
    if not candidates:
        raise ValueError("No runnable story was found.")

    order = load_blueprint_order(project_path)
    if order:
        candidates = [
            story_path
            for story_path in candidates
            if story_has_blueprint_order(story_path, order)
        ]
        if not candidates:
            raise ValueError(
                "No runnable story with blueprint order and satisfied dependencies was found. "
                "Run a specific story with run-story --story <story-folder-or-slug>."
            )

    ordered = sorted(candidates, key=lambda path: story_order_key(path, order))
    return resolve_story(project_path, ordered[0].name)


def story_is_runnable(story_path: Path) -> bool:
    status_data = load_optional_yaml(story_path / "status.yaml")
    status = optional_text(status_data.get("status")) or ""
    if status in COMPLETED_STATUSES or status in BLOCKED_STATUSES:
        return False
    if status_data.get("ready_for_review") is True:
        return False
    return (story_path / "story.md").exists()


def load_blueprint_order(project_path: Path) -> dict[str, int]:
    return {key: value["order"] for key, value in load_blueprint_metadata(project_path).items()}


def load_blueprint_dependencies(project_path: Path) -> dict[str, list[str]]:
    return {
        key: value["dependencies"]
        for key, value in load_blueprint_metadata(project_path).items()
        if value["dependencies"]
    }


def load_blueprint_metadata(project_path: Path) -> dict[str, dict[str, Any]]:
    blueprint_path = project_path.resolve() / "blueprints" / "blueprint.yaml"
    if not blueprint_path.exists():
        return {}

    try:
        loaded = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    if not isinstance(loaded, dict) or not isinstance(loaded.get("stories"), list):
        return {}

    metadata: dict[str, dict[str, Any]] = {}
    for index, story in enumerate(loaded["stories"]):
        if not isinstance(story, dict):
            continue
        dependencies = story_dependencies_from_blueprint(story)
        for key in ("slug", "id"):
            value = optional_text(story.get(key))
            if value is not None and value not in metadata:
                metadata[value] = {
                    "order": index,
                    "dependencies": dependencies,
                }
    return metadata


def story_dependencies_from_blueprint(story: dict[str, Any]) -> list[str]:
    for key in ("depends_on", "dependencies"):
        value = story.get(key)
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        if isinstance(value, list):
            return [
                item.strip()
                for item in value
                if isinstance(item, str) and item.strip()
            ]
    return []


def dependencies_satisfied(
    project_path: Path,
    story_path: Path,
    dependencies: dict[str, list[str]],
) -> bool:
    status_data = load_optional_yaml(story_path / "status.yaml")
    refs = [
        story_path.name,
        optional_text(status_data.get("slug")),
        optional_text(status_data.get("story_id") or status_data.get("id")),
    ]
    story_dependencies: list[str] = []
    for ref in refs:
        if ref in dependencies:
            story_dependencies = dependencies[ref]
            break
    if not story_dependencies:
        return True

    return all(dependency_complete(project_path, dependency) for dependency in story_dependencies)


def dependency_complete(project_path: Path, dependency: str) -> bool:
    try:
        resolved = resolve_story(project_path, dependency)
    except (FileNotFoundError, ValueError):
        return False
    status_data = load_optional_yaml(resolved.story_path / "status.yaml")
    status = optional_text(status_data.get("status")) or ""
    return status in COMPLETED_STATUSES or status_data.get("ready_for_review") is True


def story_order_key(story_path: Path, blueprint_order: dict[str, int]) -> tuple[int, int, str]:
    status_data = load_optional_yaml(story_path / "status.yaml")
    refs = [
        story_path.name,
        optional_text(status_data.get("slug")),
        optional_text(status_data.get("story_id") or status_data.get("id")),
    ]
    order_values = [blueprint_order[ref] for ref in refs if ref in blueprint_order]
    order = min(order_values) if order_values else 10_000
    return order, story_number(story_path, status_data), story_path.name


def story_has_blueprint_order(story_path: Path, blueprint_order: dict[str, int]) -> bool:
    status_data = load_optional_yaml(story_path / "status.yaml")
    refs = [
        story_path.name,
        optional_text(status_data.get("slug")),
        optional_text(status_data.get("story_id") or status_data.get("id")),
    ]
    return any(ref in blueprint_order for ref in refs)


def story_number(story_path: Path, status_data: dict[str, Any]) -> int:
    id_value = status_data.get("id") or status_data.get("story_id")
    if isinstance(id_value, int):
        return id_value
    if isinstance(id_value, str):
        digits = "".join(character for character in id_value if character.isdigit())
        if digits:
            return int(digits)
    digits = "".join(character for character in story_path.name if character.isdigit())
    return int(digits) if digits else 10_000


def build_story_runner_plan() -> list[StoryRunnerStep]:
    return [
        StoryRunnerStep(
            "prepare-story",
            "Prepare story, assigning agents and generating prompts only when needed.",
        ),
        StoryRunnerStep(
            "build-context",
            "Build role-specific context packets only when needed.",
        ),
        StoryRunnerStep(
            "codex-task-create",
            "Create Codex/local-agent task files only when needed.",
        ),
        StoryRunnerStep(
            "automatic-agent-runtime",
            "Attempt the configured automatic agent runtime if available.",
        ),
        StoryRunnerStep(
            "verify-required-agent-reports",
            "Stop clearly if required agent reports are missing.",
        ),
        StoryRunnerStep(
            "local-finalize",
            "Run local finalize after required reports exist.",
        ),
        StoryRunnerStep(
            "quality-gate",
            "Run the quality gate and stop before merge.",
        ),
    ]


def missing_required_agent_reports(story_path: Path) -> list[str]:
    return [
        relative_path.as_posix()
        for relative_path in required_agent_report_paths(story_path)
        if not (story_path / relative_path).is_file()
    ]


def required_agent_report_paths(story_path: Path) -> list[Path]:
    agent_plan_path = story_path / "agent_plan.yaml"
    if not agent_plan_path.exists():
        return [
            Path("reports/developer_report.md"),
            Path("reports/test_report.md"),
            Path("reports/local_review_report.md"),
        ]

    paths: list[Path] = []
    for assigned_agent in load_ordered_agents(story_path):
        expected_output = text_value(assigned_agent, "expected_output", "")
        report_path = resolve_expected_report_path(story_path, expected_output)
        if report_path is None:
            continue
        paths.append(report_path.relative_to(story_path))
    return dedupe_paths(paths)


def resolve_expected_report_path(story_path: Path, expected_output: str) -> Path | None:
    if not expected_output:
        return None
    path = Path(expected_output)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "reports":
        return story_path / path
    return None


def load_ordered_agents(story_path: Path) -> list[dict[str, Any]]:
    agent_plan = load_agent_plan(story_path / "agent_plan.yaml")
    return ordered_assigned_agents(agent_plan)


def first_blocking_step(
    step_results: list[StoryRunnerStepResult],
) -> StoryRunnerStepResult | None:
    for result in step_results:
        if result.status.startswith("BLOCKED") or result.status in {"FAILED", "REQUEST_CHANGES"}:
            return result
    return None


def write_story_runner_result(result: StoryRunnerResult) -> None:
    data = {
        "story": result.story,
        "executed": result.executed,
        "status": result.status,
        "planned_steps": result.planned_steps,
        "step_results": [
            {
                "step": step.step,
                "status": step.status,
                "summary": step.summary,
                "path": str(step.path) if step.path else None,
            }
            for step in result.step_results
        ],
        "missing_reports": result.missing_reports,
        "safety_flags": {
            "called_codex": any("codex" in step.step for step in result.step_results),
            "called_cloud_models": False,
            "called_github_apis": False,
            "committed_or_merged": False,
            "pushed": False,
            "merged": False,
            "deployed": False,
            "opened_pr": False,
            "ran_destructive_commands": False,
        },
        "next_action": result.next_action,
    }
    result.result_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def write_story_runner_report(
    result: StoryRunnerResult,
    resolved: StoryResolution,
    planned_steps: list[StoryRunnerStep],
) -> None:
    execution = (
        "Execution happened because `--execute` was provided."
        if result.executed
        else "Dry run only. No workflow steps ran because `--execute` was not provided."
    )
    content = f"""# Story Runner Report

## Story

{result.story}

## Resolved By

{resolved.matched_by}

## Execution

{execution}

## Status

{result.status}

## Planned Steps

{format_planned_steps(planned_steps)}
## Step Results

{format_step_results(result.step_results)}
## Missing Required Reports

{format_bullets(result.missing_reports)}
## Safety

- Did not merge.
- Did not push.
- Did not deploy.
- Did not open a PR.
- Did not call GitHub APIs.
- Stopped before merge.

## Next Action

{result.next_action}
"""
    result.report_path.write_text(content, encoding="utf-8")


def format_terminal_summary(
    story: str,
    project_path: Path,
    execute: bool,
    status: str,
    planned_steps: list[StoryRunnerStep],
    result_path: Path,
    report_path: Path,
    next_action: str,
) -> str:
    mode = "execute" if execute else "dry-run"
    lines = [
        f"Story runner for {story}:",
        f"Project: {project_path}",
        f"Mode: {mode}",
        f"Execute mode: {'on' if execute else 'off'}",
        f"Status: {status}",
        "Planned safe workflow steps:",
    ]
    lines.extend(f"  - {step.name}: {step.description}" for step in planned_steps)
    lines.extend(
        [
            "Safety: stopped before merge; no merge, push, force-push, deploy, PR, "
            "or GitHub API call.",
            f"Next action: {next_action}",
            f"Result written to: {result_path}",
            f"Report written to: {report_path}",
        ]
    )
    return "\n".join(lines)


def format_planned_steps(steps: list[StoryRunnerStep]) -> str:
    return "\n".join(f"- {step.name}: {step.description}" for step in steps) + "\n"


def format_step_results(step_results: list[StoryRunnerStepResult]) -> str:
    if not step_results:
        return "- None. Dry-run mode only planned the workflow.\n"
    lines: list[str] = []
    for step in step_results:
        lines.append(f"- {step.step}: {step.status}")
        lines.append(f"  - summary: {step.summary}")
        if step.path is not None:
            lines.append(f"  - path: `{step.path}`")
    return "\n".join(lines) + "\n"


def format_bullets(items: list[str]) -> str:
    if not items:
        return "- None.\n"
    return "\n".join(f"- {item}" for item in items) + "\n"


def load_optional_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in {path}: {error}") from error
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return loaded


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    deduped: list[Path] = []
    for path in paths:
        key = path.as_posix()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped
