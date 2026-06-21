from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any

import yaml

from agentic_dev.agent_assignment import AGENT_ID_TO_ROLE, ROLE_TO_AGENT_ID
from agentic_dev.local_model_runtime import (
    LocalModelHttpClient,
    call_local_model,
    extract_finish_reason,
    extract_response_text,
    load_local_model_runtime_config,
)
from agentic_dev.prompt_pack import load_agent_plan, ordered_assigned_agents, text_value
from agentic_dev.role_context import build_role_context
from agentic_dev.runtime_config import load_runtime_config
from agentic_dev.story_blueprint import load_blueprint_story
from agentic_dev.subtask_execution import (
    AssembledSubtaskContext,
    BlueprintSubtask,
    assemble_subtask_context,
    parse_blueprint_subtasks,
    ready_subtasks,
    topological_subtasks,
)


LOCAL_EXECUTION_FOLDER = Path("reports") / "local_execution"
STATE_FILENAME = "state.yaml"
ROLE_CONTEXT_FILENAME_TEMPLATE = "{agent_id}_context.md"


@dataclass(frozen=True)
class ResolvedRoleModel:
    role: str
    agent_id: str
    model: str | None
    source: str


@dataclass(frozen=True)
class ResolvedSubtaskModel:
    task_id: str
    title: str
    role: str
    model: str | None
    source: str
    estimated_input_tokens: int | None = None
    usable_input_tokens: int | None = None
    status: str = "pending"


@dataclass(frozen=True)
class LocalExecutionResult:
    story: str
    story_path: Path
    status: str
    state_path: Path
    roles: list[ResolvedRoleModel]
    subtasks: list[ResolvedSubtaskModel] | None = None

    @property
    def terminal_summary(self) -> str:
        lines = [
            f"Local execution for {self.story}:",
            f"Status: {self.status}",
            f"State: {self.state_path}",
        ]
        if self.subtasks is not None:
            for index, task in enumerate(self.subtasks, start=1):
                model = task.model or "UNRESOLVED"
                estimate = (
                    "unknown"
                    if task.estimated_input_tokens is None
                    else str(task.estimated_input_tokens)
                )
                limit = "unknown" if task.usable_input_tokens is None else str(task.usable_input_tokens)
                lines.append(
                    f"{index}. {task.task_id}: {task.status}; role={task.role}; "
                    f"model={model} ({task.source}); estimated_input_tokens={estimate}; "
                    f"usable_input_tokens={limit}",
                )
            return "\n".join(lines)
        for index, role in enumerate(self.roles, start=1):
            model = role.model or "UNRESOLVED"
            lines.append(f"{index}. {role.role}: {model} ({role.source})")
        return "\n".join(lines)


def run_local_execution(
    project_path: Path,
    story: str,
    *,
    role: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
    http_client: LocalModelHttpClient | None = None,
) -> LocalExecutionResult:
    resolved_project_path = project_path.resolve()
    story_path = resolved_project_path / "stories" / story
    if not story_path.exists() or not story_path.is_dir():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    blueprint_story = load_blueprint_story(resolved_project_path, story_path)
    subtasks = parse_blueprint_subtasks(blueprint_story)
    if subtasks:
        return run_subtask_local_execution(
            resolved_project_path,
            story,
            story_path,
            blueprint_story or {},
            subtasks,
            role=role,
            resume=resume,
            dry_run=dry_run,
            http_client=http_client,
        )

    execution_path = story_path / LOCAL_EXECUTION_FOLDER
    execution_path.mkdir(parents=True, exist_ok=True)
    (execution_path / ".gitkeep").touch()
    state_path = execution_path / STATE_FILENAME

    ordered_agents = selected_agents(story_path, role)
    resolved_roles = [
        resolve_role_model(resolved_project_path, agent)
        for agent in ordered_agents
    ]

    if dry_run:
        return LocalExecutionResult(
            story=story,
            story_path=story_path,
            status="dry_run",
            state_path=state_path,
            roles=resolved_roles,
        )

    state = load_execution_state(state_path) if resume else {}
    state = initialize_state(state, story, ordered_agents)
    write_state(state_path, state)

    for agent in ordered_agents:
        role_name = canonical_role(agent)
        if state.get("executions", {}).get(role_name, {}).get("status") == "completed":
            continue

        resolved = resolve_role_model(resolved_project_path, agent)
        attempt = int(state.get("executions", {}).get(role_name, {}).get("attempt", 0)) + 1
        role_path = execution_path / role_name
        role_path.mkdir(parents=True, exist_ok=True)

        audit = base_audit_metadata(role_name, resolved.model, attempt)
        state["status"] = "running"
        state["current_role"] = role_name
        state.setdefault("executions", {})[role_name] = audit
        write_state(state_path, state)

        if resolved.model is None:
            finalize_failure(
                state,
                state_path,
                role_name,
                audit,
                "unresolved_model",
                "No local model could be resolved for this role.",
            )
            break

        output_path = role_path / "output.md"
        execution_yaml_path = role_path / "execution.yaml"
        started = perf_counter()
        audit["started_at"] = utcnow()
        attempted_paths: list[str] = []

        try:
            build_role_context(
                resolved_project_path,
                story,
                agent=resolved.agent_id,
                force=False,
            )
            context_file = story_path / "reports" / "role_context" / ROLE_CONTEXT_FILENAME_TEMPLATE.format(
                agent_id=resolved.agent_id,
            )
            prompt = build_local_execution_prompt(
                story=story,
                agent=agent,
                model=resolved.model,
                writable_paths=effective_writable_paths(resolved_project_path, story_path, agent),
                context_file=context_file,
            )
            audit["context_files"] = [relative_to_project(resolved_project_path, context_file)]
            audit["prompt_hash"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

            _, local_runtime_config = load_local_model_runtime_config(resolved_project_path)
            raw_response = call_local_model(local_runtime_config, prompt, http_client, model=resolved.model)
            response_text = extract_response_text(raw_response)
            finish_reason = extract_finish_reason(raw_response)
            output_path.write_text(response_text, encoding="utf-8")
            audit["finish_reason"] = finish_reason

            if not response_text.strip():
                raise ValueError("Local model returned an empty response.")

            parsed = parse_execution_response(response_text)
            report_target = expected_report_target(story_path, agent)
            attempted_paths = [file_entry["path"] for file_entry in parsed["files"]]
            if report_target is not None:
                attempted_paths.append(relative_to_project(resolved_project_path, report_target))
            unauthorized = unauthorized_paths(
                attempted_paths,
                effective_writable_paths(resolved_project_path, story_path, agent),
            )
            if unauthorized:
                audit["attempted_paths"] = attempted_paths
                audit["unauthorized_paths"] = unauthorized
                raise PermissionError(
                    "Unauthorized writes requested: " + ", ".join(unauthorized),
                )

            applied_paths = apply_execution_writes(
                resolved_project_path,
                parsed["files"],
                report_target,
                parsed["report"],
            )
            audit["status"] = "completed"
            audit["failure_type"] = None
            audit["applied_paths"] = [
                relative_to_project(resolved_project_path, path) for path in applied_paths
            ]
            complete_role(state, role_name)
        except PermissionError as error:
            audit["attempted_paths"] = attempted_paths
            finalize_failure(
                state,
                state_path,
                role_name,
                audit,
                "file_boundary_violation",
                str(error),
            )
            execution_yaml_path.write_text(yaml.safe_dump(audit, sort_keys=False), encoding="utf-8")
            break
        except ValueError as error:
            failure_type = (
                "context_preparation_error"
                if not audit.get("prompt_hash")
                else classify_value_error(error)
            )
            finalize_failure(
                state,
                state_path,
                role_name,
                audit,
                failure_type,
                str(error),
            )
            execution_yaml_path.write_text(yaml.safe_dump(audit, sort_keys=False), encoding="utf-8")
            break
        except Exception as error:  # noqa: BLE001
            failure_type = "context_preparation_error" if not audit.get("prompt_hash") else "runtime_unavailable"
            finalize_failure(
                state,
                state_path,
                role_name,
                audit,
                failure_type,
                f"{type(error).__name__}: {error}",
            )
            execution_yaml_path.write_text(yaml.safe_dump(audit, sort_keys=False), encoding="utf-8")
            break
        finally:
            audit["completed_at"] = utcnow()
            audit["duration_seconds"] = round(perf_counter() - started, 3)
            state.setdefault("executions", {})[role_name] = audit
            execution_yaml_path.write_text(yaml.safe_dump(audit, sort_keys=False), encoding="utf-8")
            write_state(state_path, state)

    if state.get("blocked_roles"):
        state["status"] = "blocked"
    elif len(state.get("completed_roles", [])) == len(ordered_agents):
        state["status"] = "completed"
        state["current_role"] = None
    write_state(state_path, state)

    return LocalExecutionResult(
        story=story,
        story_path=story_path,
        status=str(state["status"]),
        state_path=state_path,
        roles=resolved_roles,
    )


def run_subtask_local_execution(
    project_path: Path,
    story: str,
    story_path: Path,
    blueprint_story: dict[str, Any],
    subtasks: list[BlueprintSubtask],
    *,
    role: str | None,
    resume: bool,
    dry_run: bool,
    initial_state: dict[str, Any] | None = None,
    http_client: LocalModelHttpClient | None,
) -> LocalExecutionResult:
    execution_path = story_path / LOCAL_EXECUTION_FOLDER
    execution_path.mkdir(parents=True, exist_ok=True)
    (execution_path / ".gitkeep").touch()
    state_path = execution_path / STATE_FILENAME
    selected = selected_subtasks(subtasks, role)
    ordered_tasks = topological_subtasks(selected)

    resolved_tasks: list[ResolvedSubtaskModel] = []
    empty_state: dict[str, Any] = {"tasks": {}}
    for task in ordered_tasks:
        resolved = resolve_subtask_model(project_path, task)
        try:
            assembled = assemble_subtask_context(
                project_path,
                story_path,
                story,
                blueprint_story,
                task,
                empty_state,
            )
            estimate = assembled.estimated_input_tokens
            limit = assembled.usable_input_tokens
            status = "ready" if assembled.fits and resolved.model is not None else "blocked"
        except (FileNotFoundError, ValueError):
            estimate = None
            limit = task.context_budget.usable_input_tokens
            status = "blocked"
        resolved_tasks.append(
            ResolvedSubtaskModel(
                task_id=task.id,
                title=task.title,
                role=task.role,
                model=resolved.model,
                source=resolved.source,
                estimated_input_tokens=estimate,
                usable_input_tokens=limit,
                status=status,
            )
        )

    if dry_run:
        return LocalExecutionResult(
            story=story,
            story_path=story_path,
            status="dry_run",
            state_path=state_path,
            roles=[],
            subtasks=resolved_tasks,
        )

    state = initial_state if initial_state is not None else load_execution_state(state_path) if resume else {}
    state = initialize_subtask_state(state, story, ordered_tasks)
    write_state(state_path, state)

    for task in ordered_tasks:
        task_state = state.setdefault("tasks", {}).setdefault(task.id, initial_task_state(task))
        if task_state.get("status") == "completed":
            continue
        if task_state.get("status") == "cloud_redecomposition_required" and resume:
            continue

        blocked_dependency = first_blocking_dependency(task, state)
        if blocked_dependency is not None:
            block_subtask(
                state,
                state_path,
                task,
                "blocked_by_dependency",
                f"Dependency is not completed: {blocked_dependency}",
            )
            continue

        resolved = resolve_subtask_model(project_path, task)
        attempt = int(task_state.get("attempt", 0)) + 1
        task_path = execution_path / "tasks" / task.id
        task_path.mkdir(parents=True, exist_ok=True)
        execution_yaml_path = task_path / "execution.yaml"
        output_path = task_path / "output.md"
        context_path = task_path / "context.md"

        audit = base_subtask_audit(task, resolved.model, resolved.source, attempt)
        state["status"] = "running"
        state["current_task"] = task.id
        state["tasks"][task.id] = audit
        write_state(state_path, state)

        started = perf_counter()
        audit["started_at"] = utcnow()
        attempted_paths: list[str] = []
        try:
            if resolved.model is None:
                raise ValueError("No local model could be resolved for this sub-task role.")

            assembled = assemble_subtask_context(
                project_path,
                story_path,
                story,
                blueprint_story,
                task,
                state,
            )
            audit_context(audit, assembled, context_path, project_path)
            if not assembled.fits:
                mark_cloud_redecomposition_required(state, state_path, task, audit)
                execution_yaml_path.write_text(yaml.safe_dump(audit, sort_keys=False), encoding="utf-8")
                continue

            _, local_runtime_config = load_local_model_runtime_config(project_path)
            raw_response = call_local_model(
                local_runtime_config,
                assembled.prompt,
                http_client,
                model=resolved.model,
            )
            response_text = extract_response_text(raw_response)
            finish_reason = extract_finish_reason(raw_response)
            output_path.write_text(response_text, encoding="utf-8")
            audit["finish_reason"] = finish_reason

            if not response_text.strip():
                raise ValueError("Local model returned an empty response.")

            parsed = parse_subtask_execution_response(response_text)
            attempted_paths = [file_entry["path"] for file_entry in parsed["files"]]
            unauthorized = unauthorized_paths(attempted_paths, task.writable_paths)
            if unauthorized:
                audit["attempted_paths"] = attempted_paths
                audit["unauthorized_paths"] = unauthorized
                raise PermissionError("Unauthorized writes requested: " + ", ".join(unauthorized))

            applied_paths = apply_execution_writes(project_path, parsed["files"], None, "")
            audit["status"] = "completed"
            audit["failure_type"] = None
            audit["outputs"] = [
                relative_to_project(project_path, path)
                for path in [output_path, *applied_paths]
            ]
            audit["applied_paths"] = [
                relative_to_project(project_path, path) for path in applied_paths
            ]
            audit["handoff_summary"] = normalized_handoff_summary(
                parsed.get("handoff_summary"),
                audit["applied_paths"],
            )
            audit["validation_result"] = completed_subtask_validation_result(task, audit)
            complete_subtask(state, task.id)
        except PermissionError as error:
            audit["attempted_paths"] = attempted_paths
            fail_subtask(
                state,
                state_path,
                task,
                audit,
                "file_boundary_violation",
                str(error),
            )
        except ValueError as error:
            failure_type = (
                "unresolved_model"
                if "No local model could be resolved" in str(error)
                else "context_preparation_error"
                if not audit.get("prompt_hash")
                else classify_value_error(error)
            )
            fail_subtask(state, state_path, task, audit, failure_type, str(error))
        except Exception as error:  # noqa: BLE001
            failure_type = "context_preparation_error" if not audit.get("prompt_hash") else "runtime_unavailable"
            fail_subtask(
                state,
                state_path,
                task,
                audit,
                failure_type,
                f"{type(error).__name__}: {error}",
            )
        finally:
            audit["completed_at"] = utcnow()
            audit["duration_seconds"] = round(perf_counter() - started, 3)
            state.setdefault("tasks", {})[task.id] = audit
            execution_yaml_path.write_text(yaml.safe_dump(audit, sort_keys=False), encoding="utf-8")
            write_state(state_path, state)

    finalize_subtask_story_state(state, ordered_tasks, blueprint_story)
    write_state(state_path, state)

    return LocalExecutionResult(
        story=story,
        story_path=story_path,
        status=str(state["status"]),
        state_path=state_path,
        roles=[],
        subtasks=result_subtask_models(project_path, ordered_tasks, state),
    )


def selected_agents(story_path: Path, role: str | None) -> list[dict[str, Any]]:
    agent_plan = load_agent_plan(story_path / "agent_plan.yaml")
    ordered_agents = ordered_assigned_agents(agent_plan)
    if role is None:
        return ordered_agents

    requested = normalize_role_name(role)
    selected = [agent for agent in ordered_agents if canonical_role(agent) == requested]
    if selected:
        return selected

    available = ", ".join(canonical_role(agent) for agent in ordered_agents)
    raise ValueError(f"Role is not assigned to this story: {role}. Available roles: {available}")


def selected_subtasks(subtasks: list[BlueprintSubtask], role: str | None) -> list[BlueprintSubtask]:
    if role is None:
        return subtasks
    requested = normalize_role_name(role)
    selected_ids = {task.id for task in subtasks if task.role == requested}
    if selected_ids:
        by_id = {task.id: task for task in subtasks}
        needed = set(selected_ids)
        changed = True
        while changed:
            changed = False
            for task_id in list(needed):
                for dependency in by_id[task_id].depends_on:
                    if dependency not in needed:
                        needed.add(dependency)
                        changed = True
        return [task for task in subtasks if task.id in needed]
    available = ", ".join(sorted({task.role for task in subtasks}))
    raise ValueError(f"Role is not assigned to any sub-task: {role}. Available roles: {available}")


def resolve_subtask_model(project_path: Path, task: BlueprintSubtask) -> ResolvedRoleModel:
    return resolve_role_model(
        project_path,
        {
            "id": ROLE_TO_AGENT_ID.get(task.role, task.role),
            "role": task.role,
        },
    )


def resolve_role_model(project_path: Path, agent: dict[str, Any]) -> ResolvedRoleModel:
    _, runtime_config = load_runtime_config(project_path)
    role_name = canonical_role(agent)
    agent_id = text_value(agent, "id", "")

    blueprint_model = text_value(agent, "model", "").strip()
    if blueprint_model:
        return ResolvedRoleModel(role_name, agent_id, blueprint_model, "blueprint override")

    local_execution = runtime_config.get("local_execution")
    role_defaults = {}
    global_default_model: str | None = None
    if isinstance(local_execution, dict):
        role_defaults = local_execution.get("role_defaults") or {}
        global_default_model = local_execution.get("global_default_model")

    if isinstance(role_defaults, dict):
        role_model = role_defaults.get(role_name)
        if isinstance(role_model, str) and role_model.strip():
            return ResolvedRoleModel(role_name, agent_id, role_model.strip(), "runtime role default")

    if isinstance(global_default_model, str) and global_default_model.strip():
        return ResolvedRoleModel(role_name, agent_id, global_default_model.strip(), "global local-model default")

    return ResolvedRoleModel(role_name, agent_id, None, "unresolved")


def initialize_state(
    existing_state: dict[str, Any],
    story: str,
    ordered_agents: list[dict[str, Any]],
) -> dict[str, Any]:
    if existing_state:
        return existing_state

    return {
        "story": story,
        "status": "running",
        "current_role": None,
        "completed_roles": [],
        "blocked_roles": [],
        "executions": {},
    }


def initialize_subtask_state(
    existing_state: dict[str, Any],
    story: str,
    ordered_tasks: list[BlueprintSubtask],
) -> dict[str, Any]:
    if existing_state:
        existing_state.setdefault("tasks", {})
        for task in ordered_tasks:
            existing_state["tasks"].setdefault(task.id, initial_task_state(task))
        return existing_state

    return {
        "story": story,
        "status": "pending",
        "current_task": None,
        "completed_tasks": [],
        "blocked_tasks": [],
        "cloud_redecomposition_required_tasks": [],
        "execution_order": [task.id for task in ordered_tasks],
        "tasks": {task.id: initial_task_state(task) for task in ordered_tasks},
        "final_validation": {
            "status": "pending",
            "requirements_checked": [],
            "missing_requirements": [],
        },
    }


def initial_task_state(task: BlueprintSubtask) -> dict[str, Any]:
    return {
        "task_id": task.id,
        "title": task.title,
        "role": task.role,
        "dependencies": task.depends_on,
        "status": "pending",
        "attempt": 0,
        "outputs": [],
        "handoff_summary": {},
    }


def load_execution_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    loaded = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        return loaded
    return {}


def write_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")


def base_audit_metadata(role: str, model: str | None, attempt: int) -> dict[str, Any]:
    return {
        "role": role,
        "provider": "local",
        "model": model,
        "attempt": attempt,
        "started_at": "",
        "completed_at": "",
        "duration_seconds": 0,
        "prompt_hash": "",
        "context_files": [],
        "estimated_input_tokens": None,
        "actual_input_tokens": None,
        "output_tokens": None,
        "finish_reason": None,
        "status": "running",
        "failure_type": None,
    }


def base_subtask_audit(
    task: BlueprintSubtask,
    model: str | None,
    model_source: str,
    attempt: int,
) -> dict[str, Any]:
    return {
        "task_id": task.id,
        "title": task.title,
        "role": task.role,
        "provider": "local",
        "model": model,
        "model_source": model_source,
        "dependencies": task.depends_on,
        "requirement_ids": task.requirement_ids,
        "attempt": attempt,
        "started_at": "",
        "completed_at": "",
        "duration_seconds": 0,
        "prompt_hash": "",
        "context_file": "",
        "estimated_input_tokens": None,
        "usable_input_tokens": task.context_budget.usable_input_tokens,
        "reserved_output_tokens": task.context_budget.reserved_output_tokens,
        "required_context_must_fit": task.context_budget.required_context_must_fit,
        "allow_required_context_trimming": task.context_budget.allow_required_context_trimming,
        "oversized_task_policy": task.context_budget.oversized_task_policy,
        "finish_reason": None,
        "status": "running",
        "failure_type": None,
        "blocking_reason": None,
        "outputs": [],
        "handoff_summary": {},
        "validation_result": {"status": "pending", "checks": task.validation},
    }


def audit_context(
    audit: dict[str, Any],
    assembled: AssembledSubtaskContext,
    context_path: Path,
    project_path: Path,
) -> None:
    context_path.write_text(assembled.prompt, encoding="utf-8")
    audit["context_file"] = relative_to_project(project_path, context_path)
    audit["context_sections"] = [
        {
            "name": section.name,
            "provenance": section.provenance,
            "mandatory": section.mandatory,
        }
        for section in assembled.sections
    ]
    audit["estimated_input_tokens"] = assembled.estimated_input_tokens
    audit["usable_input_tokens"] = assembled.usable_input_tokens
    audit["prompt_hash"] = hashlib.sha256(assembled.prompt.encode("utf-8")).hexdigest()


def build_local_execution_prompt(
    *,
    story: str,
    agent: dict[str, Any],
    model: str,
    writable_paths: list[str],
    context_file: Path,
) -> str:
    context = context_file.read_text(encoding="utf-8")
    writable = "\n".join(f"- {path}" for path in writable_paths) if writable_paths else "- reports/**"
    return f"""# Local Execution Task

Story: {story}
Role: {canonical_role(agent)}
Agent ID: {text_value(agent, 'id', '')}
Resolved model: {model}
Responsibility: {text_value(agent, 'responsibility', '')}
Expected output: {text_value(agent, 'expected_output', '')}

Writable paths:
{writable}

Return YAML only with this shape:

report: |
  markdown report content
files:
  - path: relative/path/to/file
    content: |
      full file content

Rules:
- Use relative project paths only.
- Do not return files outside the writable paths.
- If no source files should change, return an empty files list.
- Keep the report focused on the work completed for this role.

## Context Packet

{context}
"""


def parse_execution_response(response_text: str) -> dict[str, Any]:
    normalized_response = normalize_execution_response(response_text)
    try:
        loaded = yaml.safe_load(normalized_response)
    except yaml.YAMLError as error:
        raise ValueError(f"Local execution response was not valid YAML: {error}") from error
    if not isinstance(loaded, dict):
        raise ValueError("Local execution response must be a YAML mapping.")

    report = loaded.get("report")
    if not isinstance(report, str) or not report.strip():
        raise ValueError("Local execution response must include a non-empty report field.")

    files = loaded.get("files")
    if files is None:
        files = []
    if not isinstance(files, list):
        raise ValueError("Local execution response files field must be a list.")

    normalized_files: list[dict[str, str]] = []
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("Each local execution file entry must be a mapping.")
        path = entry.get("path")
        content = entry.get("content")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("Each local execution file entry must include a non-empty path.")
        if not isinstance(content, str):
            raise ValueError("Each local execution file entry must include string content.")
        normalized_files.append({"path": normalize_relative_path(path), "content": content})

    return {"report": report, "files": normalized_files}


def parse_subtask_execution_response(response_text: str) -> dict[str, Any]:
    parsed = parse_execution_response(response_text)
    loaded = yaml.safe_load(normalize_execution_response(response_text))
    handoff_summary = loaded.get("handoff_summary") if isinstance(loaded, dict) else None
    if handoff_summary is not None and not isinstance(handoff_summary, dict):
        raise ValueError("Local sub-task response handoff_summary field must be a mapping.")
    parsed["handoff_summary"] = handoff_summary or {}
    return parsed


def normalize_execution_response(response_text: str) -> str:
    stripped = response_text.strip()
    if not stripped:
        return stripped

    lines = stripped.splitlines()
    opening_fence = lines[0].strip()
    if not opening_fence.startswith("```"):
        return stripped

    language = opening_fence[3:].strip().lower()
    if language not in {"", "yaml", "yml"}:
        raise ValueError(
            "Local execution response must be raw YAML or a single outer ```yaml fenced YAML document.",
        )

    if len(lines) < 2:
        raise ValueError("Local execution response fence is incomplete.")

    closing_fence = lines[-1].strip()
    if closing_fence != "```":
        raise ValueError(
            "Local execution response contained prose or extra content outside the outer YAML fence.",
        )

    return "\n".join(lines[1:-1]).strip()


def unauthorized_paths(paths: list[str], writable_paths: list[str]) -> list[str]:
    if not writable_paths:
        return list(paths)
    return [
        path
        for path in paths
        if not any(fnmatch.fnmatchcase(path, pattern) for pattern in writable_paths)
    ]


def apply_execution_writes(
    project_path: Path,
    files: list[dict[str, str]],
    report_path: Path | None,
    report_text: str,
) -> list[Path]:
    resolved_project_path = project_path.resolve()
    planned_writes = [
        (project_path / PurePosixPath(file_entry["path"]), file_entry["content"])
        for file_entry in files
    ]
    if report_path is not None:
        planned_writes.append((report_path, report_text))

    for path, _ in planned_writes:
        validate_write_destination(resolved_project_path, path)

    applied: list[Path] = []
    for path, content in planned_writes:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        applied.append(path)

    return applied


def validate_write_destination(resolved_project_path: Path, destination: Path) -> None:
    resolved_destination = destination.resolve(strict=False)
    if not is_relative_to(resolved_destination, resolved_project_path):
        raise PermissionError(f"Write destination escapes project root: {destination}")

    existing_parent = destination if destination.exists() else destination.parent
    while not existing_parent.exists() and existing_parent != existing_parent.parent:
        existing_parent = existing_parent.parent

    resolved_existing_parent = existing_parent.resolve()
    if not is_relative_to(resolved_existing_parent, resolved_project_path):
        raise PermissionError(f"Write destination parent escapes project root: {destination}")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def expected_report_target(story_path: Path, agent: dict[str, Any]) -> Path | None:
    expected_output = text_value(agent, "expected_output", "")
    if not expected_output:
        return None
    return story_path / PurePosixPath(expected_output)


def classify_value_error(error: ValueError) -> str:
    message = str(error).lower()
    if "empty response" in message:
        return "empty_response"
    if "enabled must be true" in message:
        return "runtime_disabled"
    if (
        "must be configured before calling a local model" in message
        or "runtime validation failed" in message
        or "request failed" in message
        or "response was not valid json" in message
    ):
        return "configuration_error"
    return "malformed_response"


def finalize_failure(
    state: dict[str, Any],
    state_path: Path,
    role_name: str,
    audit: dict[str, Any],
    failure_type: str,
    summary: str,
) -> None:
    audit["status"] = "blocked"
    audit["failure_type"] = failure_type
    audit["summary"] = summary
    state["status"] = "blocked"
    state["current_role"] = role_name
    blocked_roles = list(state.get("blocked_roles", []))
    if role_name not in blocked_roles:
        blocked_roles.append(role_name)
    state["blocked_roles"] = blocked_roles
    state.setdefault("executions", {})[role_name] = audit
    write_state(state_path, state)


def first_blocking_dependency(task: BlueprintSubtask, state: dict[str, Any]) -> str | None:
    task_states = state.get("tasks") if isinstance(state.get("tasks"), dict) else {}
    for dependency in task.depends_on:
        dependency_state = task_states.get(dependency, {}) if isinstance(task_states, dict) else {}
        if dependency_state.get("status") != "completed":
            return dependency
    return None


def block_subtask(
    state: dict[str, Any],
    state_path: Path,
    task: BlueprintSubtask,
    failure_type: str,
    summary: str,
) -> None:
    task_state = state.setdefault("tasks", {}).setdefault(task.id, initial_task_state(task))
    task_state["status"] = "blocked"
    task_state["failure_type"] = failure_type
    task_state["blocking_reason"] = summary
    task_state["summary"] = summary
    blocked_tasks = list(state.get("blocked_tasks", []))
    if task.id not in blocked_tasks:
        blocked_tasks.append(task.id)
    state["blocked_tasks"] = blocked_tasks
    state["status"] = "blocked"
    state["current_task"] = task.id
    write_state(state_path, state)


def fail_subtask(
    state: dict[str, Any],
    state_path: Path,
    task: BlueprintSubtask,
    audit: dict[str, Any],
    failure_type: str,
    summary: str,
) -> None:
    audit["status"] = "failed" if failure_type != "file_boundary_violation" else "blocked"
    audit["failure_type"] = failure_type
    audit["summary"] = summary
    audit["blocking_reason"] = summary
    state["status"] = "blocked"
    state["current_task"] = task.id
    blocked_tasks = list(state.get("blocked_tasks", []))
    if task.id not in blocked_tasks:
        blocked_tasks.append(task.id)
    state["blocked_tasks"] = blocked_tasks
    state.setdefault("tasks", {})[task.id] = audit
    write_state(state_path, state)


def mark_cloud_redecomposition_required(
    state: dict[str, Any],
    state_path: Path,
    task: BlueprintSubtask,
    audit: dict[str, Any],
) -> None:
    reason = (
        "Required context estimate exceeds usable input budget; cloud "
        "redecomposition is required before local execution."
    )
    audit["status"] = "cloud_redecomposition_required"
    audit["failure_type"] = "context_over_budget"
    audit["blocking_reason"] = reason
    audit["summary"] = reason
    audit["local_agent_may_redecompose"] = False
    state["status"] = "blocked"
    state["current_task"] = task.id
    blocked_tasks = list(state.get("blocked_tasks", []))
    if task.id not in blocked_tasks:
        blocked_tasks.append(task.id)
    state["blocked_tasks"] = blocked_tasks
    redecomposition_tasks = list(state.get("cloud_redecomposition_required_tasks", []))
    if task.id not in redecomposition_tasks:
        redecomposition_tasks.append(task.id)
    state["cloud_redecomposition_required_tasks"] = redecomposition_tasks
    state.setdefault("tasks", {})[task.id] = audit
    write_state(state_path, state)


def complete_subtask(state: dict[str, Any], task_id: str) -> None:
    completed_tasks = list(state.get("completed_tasks", []))
    if task_id not in completed_tasks:
        completed_tasks.append(task_id)
    state["completed_tasks"] = completed_tasks
    state["blocked_tasks"] = [task for task in state.get("blocked_tasks", []) if task != task_id]
    state["cloud_redecomposition_required_tasks"] = [
        task
        for task in state.get("cloud_redecomposition_required_tasks", [])
        if task != task_id
    ]


def normalized_handoff_summary(value: Any, applied_paths: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        handoff = dict(value)
    else:
        handoff = {}
    handoff.setdefault("decisions", [])
    handoff.setdefault("files_changed", applied_paths)
    handoff.setdefault("outputs_produced", applied_paths)
    handoff.setdefault("tests_run", [])
    handoff.setdefault("unresolved_risks", [])
    handoff.setdefault("available_to_dependents", True)
    return handoff


def completed_subtask_validation_result(
    task: BlueprintSubtask,
    audit: dict[str, Any],
) -> dict[str, Any]:
    verified_checks: list[str] = []
    missing_checks: list[str] = []

    if audit.get("context_sections"):
        verified_checks.append("context_sections_recorded")
    else:
        missing_checks.append("context_sections_recorded")

    if audit.get("outputs"):
        verified_checks.append("outputs_recorded")
    else:
        missing_checks.append("outputs_recorded")

    handoff_summary = audit.get("handoff_summary")
    required_handoff_fields = {
        "decisions",
        "files_changed",
        "outputs_produced",
        "tests_run",
        "unresolved_risks",
        "available_to_dependents",
    }
    if isinstance(handoff_summary, dict) and required_handoff_fields.issubset(handoff_summary):
        verified_checks.append("handoff_summary_recorded")
    else:
        missing_checks.append("handoff_summary_recorded")

    if task.validation:
        verified_checks.append("declared_validation_checks_recorded")

    return {
        "status": "passed" if not missing_checks else "failed",
        "checks": task.validation,
        "verified": verified_checks,
        "missing": missing_checks,
    }


def finalize_subtask_story_state(
    state: dict[str, Any],
    ordered_tasks: list[BlueprintSubtask],
    blueprint_story: dict[str, Any],
) -> None:
    if state.get("cloud_redecomposition_required_tasks"):
        state["status"] = "blocked"
        return
    if state.get("blocked_tasks"):
        state["status"] = "blocked"
        return
    if all(state.get("tasks", {}).get(task.id, {}).get("status") == "completed" for task in ordered_tasks):
        final_validation = validate_story_requirements(ordered_tasks, blueprint_story, state)
        state["final_validation"] = final_validation
        state["status"] = "completed" if final_validation["status"] == "passed" else "blocked"
        state["current_task"] = None
        return
    ready = ready_subtasks(ordered_tasks, state.get("tasks", {}))
    state["status"] = "ready" if ready else "pending"


def validate_story_requirements(
    ordered_tasks: list[BlueprintSubtask],
    blueprint_story: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    criteria = blueprint_story.get("acceptance_criteria")
    requirement_ids: list[str] = []
    if isinstance(criteria, list):
        for criterion in criteria:
            text = str(criterion)
            if ":" in text:
                requirement_ids.append(text.split(":", 1)[0].strip())
    covered = sorted({requirement for task in ordered_tasks for requirement in task.requirement_ids})
    missing = [requirement_id for requirement_id in requirement_ids if requirement_id not in covered]
    task_states = state.get("tasks", {}) if isinstance(state.get("tasks"), dict) else {}
    tasks_missing_validation = [
        task.id
        for task in ordered_tasks
        if task_states.get(task.id, {}).get("validation_result", {}).get("status") != "passed"
    ]
    tasks_missing_outputs = [
        task.id for task in ordered_tasks if not task_states.get(task.id, {}).get("outputs")
    ]
    tasks_missing_handoffs = []
    for task in ordered_tasks:
        handoff_summary = task_states.get(task.id, {}).get("handoff_summary", {})
        if not isinstance(handoff_summary, dict) or "available_to_dependents" not in handoff_summary:
            tasks_missing_handoffs.append(task.id)
    return {
        "status": (
            "passed"
            if not missing and not tasks_missing_validation and not tasks_missing_outputs and not tasks_missing_handoffs
            else "failed"
        ),
        "requirements_checked": requirement_ids,
        "requirements_covered": covered,
        "missing_requirements": missing,
        "tasks_missing_validation": tasks_missing_validation,
        "tasks_missing_outputs": tasks_missing_outputs,
        "tasks_missing_handoffs": tasks_missing_handoffs,
    }


def result_subtask_models(
    project_path: Path,
    ordered_tasks: list[BlueprintSubtask],
    state: dict[str, Any],
) -> list[ResolvedSubtaskModel]:
    results: list[ResolvedSubtaskModel] = []
    for task in ordered_tasks:
        resolved = resolve_subtask_model(project_path, task)
        task_state = state.get("tasks", {}).get(task.id, {})
        results.append(
            ResolvedSubtaskModel(
                task_id=task.id,
                title=task.title,
                role=task.role,
                model=resolved.model,
                source=resolved.source,
                estimated_input_tokens=task_state.get("estimated_input_tokens"),
                usable_input_tokens=task_state.get("usable_input_tokens"),
                status=str(task_state.get("status", "pending")),
            )
        )
    return results


def complete_role(state: dict[str, Any], role_name: str) -> None:
    completed_roles = list(state.get("completed_roles", []))
    if role_name not in completed_roles:
        completed_roles.append(role_name)
    state["completed_roles"] = completed_roles
    state["blocked_roles"] = [role for role in state.get("blocked_roles", []) if role != role_name]


def canonical_role(agent: dict[str, Any]) -> str:
    role = text_value(agent, "role", "")
    if role:
        return normalize_role_name(role)
    return AGENT_ID_TO_ROLE.get(text_value(agent, "id", ""), text_value(agent, "id", ""))


def normalize_role_name(role: str) -> str:
    normalized = role.strip()
    if normalized in ROLE_TO_AGENT_ID:
        return AGENT_ID_TO_ROLE[ROLE_TO_AGENT_ID[normalized]]
    if normalized in AGENT_ID_TO_ROLE:
        return AGENT_ID_TO_ROLE[normalized]
    raise ValueError(f"Unsupported role: {role}")


def effective_writable_paths(
    project_path: Path,
    story_path: Path,
    agent: dict[str, Any],
) -> list[str]:
    writable_paths = agent.get("writable_paths")
    if isinstance(writable_paths, list):
        values = [path.strip() for path in writable_paths if isinstance(path, str) and path.strip()]
        if values:
            return values

    expected_output = text_value(agent, "expected_output", "")
    if expected_output:
        return [
            relative_to_project(
                project_path,
                story_path / PurePosixPath(normalize_relative_path(expected_output)),
            )
        ]
    return []


def normalize_relative_path(path: str) -> str:
    pure_path = PurePosixPath(path.replace("\\", "/"))
    if pure_path.is_absolute() or ".." in pure_path.parts:
        raise ValueError(f"Only relative project paths are allowed: {path}")
    return pure_path.as_posix()


def relative_to_project(project_path: Path, path: Path) -> str:
    return path.resolve().relative_to(project_path.resolve()).as_posix()


def utcnow() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
