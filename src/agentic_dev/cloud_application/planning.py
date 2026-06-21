from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.cloud_application.graph import RuntimeGraphDiff, diff_runtime_graph
from agentic_dev.cloud_application.models import (
    ActiveRevisionPointer,
    ApplicationOperation,
    RuntimePlanRevision,
    TaskSnapshot,
)
from agentic_dev.cloud_application.persistence import (
    load_active_pointer,
    load_runtime_revision,
    revision_path,
    runtime_active_pointer_path,
)
from agentic_dev.cloud_application.validation import (
    validate_active_pointer,
    validate_context_budget,
    validate_dependency_graph,
    validate_path_overlap,
    validate_requirement_coverage,
    validate_requirement_drift,
    validate_writable_paths_exact,
)
from agentic_dev.cloud_queue.models import CloudQueueRequest, CloudQueueResponse
from agentic_dev.cloud_queue.validation import normalize_relative_path


SUPPORTED_OPERATION_TYPES = {
    "replace_task_with_subtasks",
    "update_task_metadata",
}


@dataclass(frozen=True)
class RuntimeState:
    pointer: ActiveRevisionPointer
    revision: RuntimePlanRevision


@dataclass(frozen=True)
class PlannedApplication:
    operation: ApplicationOperation
    proposed_tasks: tuple[TaskSnapshot, ...]
    diff: RuntimeGraphDiff
    response_requirements: tuple[str, ...]
    response_writable_paths: tuple[str, ...]
    operation_type: str


def load_active_runtime_state(project_path: Path) -> RuntimeState:
    pointer_path = runtime_active_pointer_path(project_path)
    if not pointer_path.exists():
        raise FileNotFoundError(f"Active runtime pointer does not exist: {pointer_path}")
    pointer = load_active_pointer(pointer_path)
    revision_file = revision_path(project_path, pointer.active_revision_id)
    if not revision_file.exists():
        raise FileNotFoundError(f"Active runtime revision does not exist: {revision_file}")
    revision = load_runtime_revision(revision_file)
    validate_active_pointer(pointer, revision.revision_id, revision.revision_checksum)
    return RuntimeState(pointer=pointer, revision=revision)


def resolve_source_task(
    state: RuntimeState,
    request: CloudQueueRequest,
) -> TaskSnapshot:
    if not request.source_task_id.strip():
        raise ValueError("Cloud queue request does not identify a source task.")
    if request.source_plan_revision and request.source_plan_revision != state.revision.revision_id:
        raise ValueError("Request source revision does not match the active revision.")
    for task in state.revision.task_graph:
        if task.task_id == request.source_task_id:
            if task.status in {"superseded", "cancelled", "canceled"}:
                raise ValueError("Source task is no longer eligible for application.")
            return task
    raise FileNotFoundError(f"Source task was not found in the active runtime revision: {request.source_task_id}")


def supported_operation_type(response: CloudQueueResponse) -> str:
    operation_type = str(response.claims.get("operation_type", "replace_task_with_subtasks")).strip()
    if not operation_type:
        operation_type = "replace_task_with_subtasks"
    if operation_type not in SUPPORTED_OPERATION_TYPES:
        raise ValueError(f"Unsupported application operation: {operation_type}")
    return operation_type


def build_planned_application(
    request: CloudQueueRequest,
    response: CloudQueueResponse,
    source_task: TaskSnapshot,
    state: RuntimeState,
) -> PlannedApplication:
    operation_type = supported_operation_type(response)
    response_requirements = tuple(
        str(item)
        for item in response.claims.get("applicable_requirements", []) or list(request.requirements)
    )
    response_writable_paths = tuple(
        normalize_relative_path(str(item))
        for item in response.claims.get("writable_paths", []) or list(request.writable_paths)
    )

    if operation_type == "replace_task_with_subtasks":
        proposed_tasks = tuple(_build_subtask_children(response, source_task))
    else:
        proposed_tasks = tuple(_build_metadata_update_task(response, source_task))

    if not proposed_tasks:
        raise ValueError("Proposed tasks are required for application planning.")

    validate_dependency_graph(list(proposed_tasks))
    validate_path_overlap(list(proposed_tasks))
    validate_requirement_coverage(source_task, list(proposed_tasks), list(request.requirements))
    validate_requirement_drift(list(request.requirements), list(response_requirements))
    validate_writable_paths_exact(list(request.writable_paths), list(response_writable_paths))
    for task in proposed_tasks:
        validate_context_budget(task)

    diff = diff_runtime_graph(source_task, list(proposed_tasks), list(state.revision.task_graph))
    operation = ApplicationOperation(
        operation_type=operation_type,
        affected_task_ids=(source_task.task_id,),
        proposed_task_ids=tuple(task.task_id for task in proposed_tasks),
        preserved_requirement_ids=tuple(request.requirements),
        dependency_changes=diff.dependency_changes,
        writable_paths=tuple(diff.writable_path_diff),
        expected_outputs=tuple(
            str(item) for item in response.claims.get("expected_outputs", []) or source_task.expected_outputs
        ),
        validation_steps=tuple(str(item) for item in response.claims.get("validation_steps", []) or source_task.validation_steps),
    )
    return PlannedApplication(
        operation=operation,
        proposed_tasks=proposed_tasks,
        diff=diff,
        response_requirements=response_requirements,
        response_writable_paths=response_writable_paths,
        operation_type=operation_type,
    )


def _build_subtask_children(response: CloudQueueResponse, source_task: TaskSnapshot) -> list[TaskSnapshot]:
    proposed_task_claims = response.claims.get("proposed_tasks")
    if not isinstance(proposed_task_claims, list) or not proposed_task_claims:
        raise ValueError("replace_task_with_subtasks requires explicit proposed_tasks.")

    proposed: list[TaskSnapshot] = []
    for index, entry in enumerate(proposed_task_claims, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"proposed_tasks[{index}] must be a mapping.")
        required_keys = {
            "task_id",
            "title",
            "role",
            "depends_on",
            "requirement_ids",
            "required_context",
            "writable_paths",
            "expected_outputs",
            "validation_steps",
            "token_estimate",
            "usable_input_tokens",
        }
        missing_keys = sorted(required_keys - set(entry))
        if missing_keys:
            raise ValueError(
                f"proposed_tasks[{index}] is missing required fields: {', '.join(missing_keys)}",
            )
        task_id = str(entry.get("task_id", "")).strip()
        title = str(entry.get("title", "")).strip()
        role = str(entry.get("role", source_task.role)).strip()
        requirement_ids = tuple(str(item).strip() for item in entry.get("requirement_ids", []) or [])
        depends_on = tuple(str(item).strip() for item in entry.get("depends_on", []) or [])
        required_context = tuple(str(item).strip() for item in entry.get("required_context", []) or [])
        writable_paths = tuple(normalize_relative_path(str(item)) for item in entry.get("writable_paths", []) or [])
        expected_outputs = tuple(str(item).strip() for item in entry.get("expected_outputs", []) or [])
        validation_steps = tuple(str(item).strip() for item in entry.get("validation_steps", []) or [])
        token_estimate = entry.get("token_estimate")
        usable_input_tokens = entry.get("usable_input_tokens")
        if not task_id:
            raise ValueError("proposed_tasks entries require a task_id.")
        if not title:
            raise ValueError("proposed_tasks entries require a title.")
        if not requirement_ids:
            raise ValueError(f"proposed_tasks[{task_id}] requires requirement_ids.")
        if index > 1 and not depends_on:
            raise ValueError(f"proposed_tasks[{task_id}] requires dependencies.")
        if not writable_paths:
            raise ValueError(f"proposed_tasks[{task_id}] requires writable_paths.")
        if not expected_outputs:
            raise ValueError(f"proposed_tasks[{task_id}] requires expected_outputs.")
        if not validation_steps:
            raise ValueError(f"proposed_tasks[{task_id}] requires validation_steps.")
        if token_estimate is None:
            raise ValueError(f"proposed_tasks[{task_id}] requires token_estimate.")
        if usable_input_tokens is None:
            raise ValueError(f"proposed_tasks[{task_id}] requires usable_input_tokens.")
        proposed.append(
            TaskSnapshot(
                task_id=task_id,
                title=title,
                role=role or source_task.role,
                depends_on=depends_on,
                requirement_ids=requirement_ids,
                required_context=required_context,
                writable_paths=writable_paths,
                expected_outputs=expected_outputs,
                validation_steps=validation_steps,
                token_estimate=int(token_estimate),
                usable_input_tokens=int(usable_input_tokens),
                status=str(entry.get("status", "ready")),
                source_task_id=source_task.task_id,
                history=(source_task.task_id,),
            ),
        )
    if len({task.task_id for task in proposed}) != len(proposed):
        raise ValueError("Duplicate task IDs are not allowed in the proposed revision.")
    return proposed


def _build_metadata_update_task(response: CloudQueueResponse, source_task: TaskSnapshot) -> list[TaskSnapshot]:
    metadata = response.claims.get("task_metadata")
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError("update_task_metadata requires task_metadata.")
    allowed_keys = {
        "title",
        "role",
        "required_context",
        "writable_paths",
        "expected_outputs",
        "validation_steps",
        "token_estimate",
        "usable_input_tokens",
        "depends_on",
        "requirement_ids",
    }
    disallowed = set(metadata) - allowed_keys
    if disallowed:
        raise ValueError(f"update_task_metadata contains unsupported fields: {', '.join(sorted(disallowed))}")

    updated = TaskSnapshot.from_dict(
        {
            **source_task.to_dict(),
            "title": str(metadata.get("title", source_task.title)).strip() or source_task.title,
            "role": str(metadata.get("role", source_task.role)).strip() or source_task.role,
            "required_context": list(str(item).strip() for item in metadata.get("required_context", []) or source_task.required_context),
            "writable_paths": list(normalize_relative_path(str(item)) for item in metadata.get("writable_paths", []) or source_task.writable_paths),
            "expected_outputs": list(str(item).strip() for item in metadata.get("expected_outputs", []) or source_task.expected_outputs),
            "validation_steps": list(str(item).strip() for item in metadata.get("validation_steps", []) or source_task.validation_steps),
            "token_estimate": metadata.get("token_estimate", source_task.token_estimate),
            "usable_input_tokens": metadata.get("usable_input_tokens", source_task.usable_input_tokens),
            "depends_on": list(source_task.depends_on),
            "requirement_ids": list(source_task.requirement_ids),
            "status": source_task.status,
            "source_task_id": source_task.source_task_id or source_task.task_id,
            "history": list(source_task.history or (source_task.task_id,)),
        }
    )
    return [updated]
