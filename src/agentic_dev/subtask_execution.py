from __future__ import annotations

import glob
import math
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


VALID_OVERSIZED_TASK_POLICY = "reject_for_cloud_redecomposition"
VALID_ROLES = {
    "research",
    "planner",
    "developer",
    "test",
    "documentation",
    "docs",
    "security_quality",
    "local_reviewer",
}
MANDATORY_CONTEXT_SECTIONS = (
    "system_and_safety_instructions",
    "role_instructions",
    "story_goal",
    "applicable_requirements",
    "required_context",
    "writable_path_rules",
    "expected_output_contract",
    "validation_instructions",
    "response_contract",
)


@dataclass(frozen=True)
class RequiredContext:
    files: list[str]
    summaries: list[str]
    prior_task_outputs: list[str]
    architecture_decisions: list[str]


@dataclass(frozen=True)
class ContextBudget:
    max_input_tokens: int
    reserved_output_tokens: int
    required_context_must_fit: bool
    allow_required_context_trimming: bool
    oversized_task_policy: str

    @property
    def usable_input_tokens(self) -> int:
        return self.max_input_tokens - self.reserved_output_tokens


@dataclass(frozen=True)
class BlueprintSubtask:
    id: str
    title: str
    role: str
    depends_on: list[str]
    requirement_ids: list[str]
    required_context: RequiredContext
    writable_paths: list[str]
    expected_outputs: list[str]
    validation: list[str]
    context_budget: ContextBudget


@dataclass(frozen=True)
class ContextSection:
    name: str
    provenance: str
    content: str
    mandatory: bool = True


@dataclass(frozen=True)
class AssembledSubtaskContext:
    task: BlueprintSubtask
    sections: list[ContextSection]
    prompt: str
    estimated_input_tokens: int
    usable_input_tokens: int

    @property
    def fits(self) -> bool:
        return self.estimated_input_tokens <= self.usable_input_tokens


def parse_blueprint_subtasks(blueprint_story: dict[str, Any] | None) -> list[BlueprintSubtask]:
    if blueprint_story is None:
        return []

    raw_subtasks = blueprint_story.get("subtasks")
    if raw_subtasks is None:
        return []
    if not isinstance(raw_subtasks, list):
        raise ValueError("blueprint subtasks must be a list.")

    subtasks: list[BlueprintSubtask] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_subtasks, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"subtasks[{index}] must be a mapping.")

        task_id = required_string(raw, "id", f"subtasks[{index}]")
        if task_id in seen:
            raise ValueError(f"Duplicate sub-task id: {task_id}")
        seen.add(task_id)

        role = required_string(raw, "role", f"subtasks[{index}]")
        if role not in VALID_ROLES:
            raise ValueError(f"Unsupported sub-task role for {task_id}: {role}")
        if role == "docs":
            role = "documentation"

        depends_on = string_list(raw.get("depends_on", []), f"subtasks[{index}].depends_on")
        if task_id in depends_on:
            raise ValueError(f"Sub-task cannot depend on itself: {task_id}")

        subtasks.append(
            BlueprintSubtask(
                id=task_id,
                title=required_string(raw, "title", f"subtasks[{index}]"),
                role=role,
                depends_on=depends_on,
                requirement_ids=string_list(
                    raw.get("requirement_ids", []),
                    f"subtasks[{index}].requirement_ids",
                ),
                required_context=parse_required_context(
                    raw.get("required_context"),
                    f"subtasks[{index}].required_context",
                ),
                writable_paths=string_list(
                    raw.get("writable_paths", []),
                    f"subtasks[{index}].writable_paths",
                ),
                expected_outputs=string_list(
                    raw.get("expected_outputs", []),
                    f"subtasks[{index}].expected_outputs",
                ),
                validation=string_list(raw.get("validation", []), f"subtasks[{index}].validation"),
                context_budget=parse_context_budget(
                    raw.get("context_budget"),
                    f"subtasks[{index}].context_budget",
                ),
            )
        )

    validate_dependency_graph(subtasks)
    return subtasks


def parse_required_context(value: Any, location: str) -> RequiredContext:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a mapping.")
    return RequiredContext(
        files=string_list(value.get("files", []), f"{location}.files"),
        summaries=string_list(value.get("summaries", []), f"{location}.summaries"),
        prior_task_outputs=string_list(
            value.get("prior_task_outputs", []),
            f"{location}.prior_task_outputs",
        ),
        architecture_decisions=string_list(
            value.get("architecture_decisions", []),
            f"{location}.architecture_decisions",
        ),
    )


def parse_context_budget(value: Any, location: str) -> ContextBudget:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a mapping.")

    budget = ContextBudget(
        max_input_tokens=positive_int(value.get("max_input_tokens"), f"{location}.max_input_tokens"),
        reserved_output_tokens=nonnegative_int(
            value.get("reserved_output_tokens"),
            f"{location}.reserved_output_tokens",
        ),
        required_context_must_fit=required_bool(
            value.get("required_context_must_fit"),
            f"{location}.required_context_must_fit",
        ),
        allow_required_context_trimming=required_bool(
            value.get("allow_required_context_trimming"),
            f"{location}.allow_required_context_trimming",
        ),
        oversized_task_policy=required_string(value, "oversized_task_policy", location),
    )
    validate_context_budget(budget, location)
    return budget


def validate_context_budget(budget: ContextBudget, location: str = "context_budget") -> None:
    if budget.usable_input_tokens <= 0:
        raise ValueError(f"{location} must leave a positive usable input budget.")
    if not budget.required_context_must_fit:
        raise ValueError(f"{location}.required_context_must_fit must be true.")
    if budget.allow_required_context_trimming:
        raise ValueError(f"{location}.allow_required_context_trimming must be false.")
    if budget.oversized_task_policy != VALID_OVERSIZED_TASK_POLICY:
        raise ValueError(
            f"{location}.oversized_task_policy must be {VALID_OVERSIZED_TASK_POLICY}.",
        )


def validate_dependency_graph(subtasks: list[BlueprintSubtask]) -> None:
    task_ids = {task.id for task in subtasks}
    for task in subtasks:
        missing = [dependency for dependency in task.depends_on if dependency not in task_ids]
        if missing:
            raise ValueError(
                f"Sub-task {task.id} has missing dependencies: {', '.join(missing)}",
            )
    topological_subtasks(subtasks)


def topological_subtasks(subtasks: list[BlueprintSubtask]) -> list[BlueprintSubtask]:
    by_id = {task.id: task for task in subtasks}
    remaining = {task.id for task in subtasks}
    completed: set[str] = set()
    ordered: list[BlueprintSubtask] = []

    while remaining:
        ready = [
            task
            for task in subtasks
            if task.id in remaining and all(dependency in completed for dependency in task.depends_on)
        ]
        if not ready:
            cycle_members = ", ".join(sorted(remaining))
            raise ValueError(f"Sub-task dependency cycle detected: {cycle_members}")
        for task in ready:
            ordered.append(by_id[task.id])
            completed.add(task.id)
            remaining.remove(task.id)

    return ordered


def ready_subtasks(
    subtasks: list[BlueprintSubtask],
    task_states: dict[str, dict[str, Any]],
) -> list[BlueprintSubtask]:
    ready: list[BlueprintSubtask] = []
    for task in topological_subtasks(subtasks):
        status = task_states.get(task.id, {}).get("status")
        if status == "completed":
            continue
        if all(task_states.get(dependency, {}).get("status") == "completed" for dependency in task.depends_on):
            ready.append(task)
    return ready


def assemble_subtask_context(
    project_path: Path,
    story_path: Path,
    story_name: str,
    blueprint_story: dict[str, Any],
    task: BlueprintSubtask,
    state: dict[str, Any] | None = None,
) -> AssembledSubtaskContext:
    state = state or {}
    sections = [
        ContextSection(
            "system_and_safety_instructions",
            "local execution policy",
            "\n".join(
                [
                    "Provider: local model only.",
                    "Do not call cloud models, Codex, GitHub APIs, deployment tools, or shells.",
                    "Do not redecompose cloud-authored tasks locally.",
                    "Do not silently trim required instructions or required context.",
                ]
            ),
        ),
        ContextSection(
            "role_instructions",
            f"role={task.role}",
            role_instruction(story_path, task.role),
        ),
        ContextSection(
            "story_goal",
            "blueprint story goal",
            str(blueprint_story.get("goal", "")).strip() or "Not specified.",
        ),
        ContextSection(
            "applicable_requirements",
            "blueprint acceptance criteria",
            requirement_text(blueprint_story, task.requirement_ids),
        ),
        ContextSection(
            "required_context",
            "blueprint required_context manifest",
            required_context_text(project_path, task, state),
        ),
        ContextSection(
            "writable_path_rules",
            "blueprint writable_paths",
            yaml.safe_dump(task.writable_paths, sort_keys=False).strip(),
        ),
        ContextSection(
            "expected_output_contract",
            "blueprint expected_outputs",
            yaml.safe_dump(task.expected_outputs, sort_keys=False).strip(),
        ),
        ContextSection(
            "validation_instructions",
            "blueprint validation",
            yaml.safe_dump(task.validation, sort_keys=False).strip(),
        ),
        ContextSection(
            "response_contract",
            "shared local sub-task execution contract",
            response_contract_text(task),
        ),
    ]
    prompt = format_subtask_prompt(story_name, task, sections)
    missing = missing_mandatory_sections(prompt)
    if missing:
        raise ValueError("Mandatory context sections missing: " + ", ".join(missing))
    estimate = estimate_input_tokens(prompt)
    return AssembledSubtaskContext(
        task=task,
        sections=sections,
        prompt=prompt,
        estimated_input_tokens=estimate,
        usable_input_tokens=task.context_budget.usable_input_tokens,
    )


def role_instruction(story_path: Path, role: str) -> str:
    filename_by_role = {
        "research": "research_agent.md",
        "planner": "planner_agent.md",
        "developer": "developer_agent.md",
        "test": "test_agent.md",
        "documentation": "docs_agent.md",
        "security_quality": "security_quality_agent.md",
        "local_reviewer": "local_reviewer_agent.md",
    }
    filename = filename_by_role.get(role)
    if filename is None:
        return f"Role: {role}"
    path = story_path / "instructions" / filename
    if not path.exists():
        return f"Instruction file not found for role: {role}"
    return path.read_text(encoding="utf-8").strip()


def requirement_text(blueprint_story: dict[str, Any], requirement_ids: list[str]) -> str:
    criteria = blueprint_story.get("acceptance_criteria")
    if not isinstance(criteria, list):
        return "[]"
    selected: list[str] = []
    for criterion in criteria:
        text = str(criterion)
        if not requirement_ids or any(text.startswith(f"{requirement_id}:") for requirement_id in requirement_ids):
            selected.append(text)
    return yaml.safe_dump(selected, sort_keys=False).strip()


def required_context_text(project_path: Path, task: BlueprintSubtask, state: dict[str, Any]) -> str:
    context: dict[str, Any] = {
        "summaries": task.required_context.summaries,
        "architecture_decisions": task.required_context.architecture_decisions,
        "files": [],
        "prior_task_outputs": [],
    }

    for file_pattern in task.required_context.files:
        matches = resolve_required_files(project_path, file_pattern)
        context["files"].extend(matches)

    tasks_state = state.get("tasks") if isinstance(state.get("tasks"), dict) else {}
    for task_id in task.required_context.prior_task_outputs:
        task_state = tasks_state.get(task_id, {}) if isinstance(tasks_state, dict) else {}
        context["prior_task_outputs"].append(
            {
                "task_id": task_id,
                "status": task_state.get("status", "unavailable"),
                "handoff_summary": task_state.get("handoff_summary", {}),
                "outputs": task_state.get("outputs", []),
            }
        )

    return yaml.safe_dump(context, sort_keys=False).strip()


def resolve_required_files(project_path: Path, file_pattern: str) -> list[dict[str, str]]:
    normalized = PurePosixPath(file_pattern.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError(f"Required context path must stay inside the project: {file_pattern}")

    pattern = (project_path / normalized).as_posix()
    paths = sorted(Path(path) for path in glob.glob(pattern, recursive=True))
    if not any(character in file_pattern for character in "*?[]") and not paths:
        raise FileNotFoundError(f"Required context file does not exist: {file_pattern}")

    results: list[dict[str, str]] = []
    for path in paths:
        if not path.is_file():
            continue
        relative = path.resolve().relative_to(project_path.resolve()).as_posix()
        results.append({"path": relative, "content": path.read_text(encoding="utf-8")})
    return results


def response_contract_text(task: BlueprintSubtask) -> str:
    return """Return YAML only. Do not include prose before or after the YAML document.
You may return raw YAML or a single outer ```yaml fenced YAML document.
The YAML must have exactly this shape:

report: |
  concise markdown summary for this task only
files:
  - path: relative/path/inside/allowed/writable/paths
    content: |
      full file content
handoff_summary:
  decisions:
    - concise downstream decision
  files_changed:
    - relative/path/inside/allowed/writable/paths
  outputs_produced:
    - relative/path/inside/allowed/writable/paths
  tests_run:
    - optional validation command or evidence
  unresolved_risks:
    - optional remaining risk
  available_to_dependents: true

Rules:
- Return files for this task only.
- Use sandbox-relative POSIX paths only.
- Do not use absolute paths.
- Do not use parent-directory traversal such as ..
- Every file entry must contain the complete final file contents.
- Every file path must stay within the allowed writable paths for this task.
- If no file should be written for this task, return files: [].
- Keep the report focused on work completed for this task only.
- The handoff_summary must be a YAML mapping with all listed fields.
- Expected outputs for this task: {expected_outputs}.
""".format(
        expected_outputs=", ".join(task.expected_outputs) if task.expected_outputs else "none declared",
    )


def format_subtask_prompt(
    story_name: str,
    task: BlueprintSubtask,
    sections: list[ContextSection],
) -> str:
    lines = [
        "# Context-Safe Local Sub-Task",
        "",
        f"story: {story_name}",
        f"task_id: {task.id}",
        f"title: {task.title}",
        f"role: {task.role}",
        "",
    ]
    for section in sections:
        lines.extend(
            [
                f"## {section.name}",
                "",
                f"provenance: {section.provenance}",
                "",
                section.content,
                "",
            ]
        )
    return "\n".join(lines)


def missing_mandatory_sections(prompt: str) -> list[str]:
    return [section for section in MANDATORY_CONTEXT_SECTIONS if f"## {section}" not in prompt]


def estimate_input_tokens(prompt: str) -> int:
    # Conservative deterministic estimate: four UTF-8 bytes per token, rounded up,
    # plus one token per line to account for separators and YAML/Markdown overhead.
    byte_tokens = math.ceil(len(prompt.encode("utf-8")) / 4)
    line_overhead = len(prompt.splitlines())
    return byte_tokens + line_overhead


def required_string(mapping: dict[str, Any], key: str, location: str) -> str:
    value = mapping.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(f"{location}.{key} must be a non-empty string.")


def string_list(value: Any, location: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{location} must be a list of non-empty strings.")
    return [item.strip() for item in value]


def positive_int(value: Any, location: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise ValueError(f"{location} must be a positive integer.")


def nonnegative_int(value: Any, location: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise ValueError(f"{location} must be a non-negative integer.")


def required_bool(value: Any, location: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{location} must be a boolean.")
