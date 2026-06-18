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
class LocalExecutionResult:
    story: str
    story_path: Path
    status: str
    state_path: Path
    roles: list[ResolvedRoleModel]

    @property
    def terminal_summary(self) -> str:
        lines = [
            f"Local execution for {self.story}:",
            f"Status: {self.status}",
            f"State: {self.state_path}",
        ]
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
