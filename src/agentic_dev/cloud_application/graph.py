from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from agentic_dev.cloud_application.models import (
    DependencyChange,
    RequirementMapping,
    RuntimePlanRevision,
    TaskChange,
    TaskSnapshot,
)
from agentic_dev.cloud_application.validation import validate_dependency_graph, validate_path_overlap
from agentic_dev.cloud_queue.persistence import checksum_text


@dataclass(frozen=True)
class RuntimeGraphDiff:
    source_task_id: str
    affected_completed_tasks: tuple[str, ...]
    affected_pending_tasks: tuple[str, ...]
    resume_candidates: tuple[str, ...]
    dependency_changes: tuple[DependencyChange, ...]
    requirement_mappings: tuple[RequirementMapping, ...]
    task_changes: tuple[TaskChange, ...]
    writable_path_diff: tuple[str, ...]
    revised_tasks: tuple[TaskSnapshot, ...]


def build_runtime_graph_revision(
    *,
    revision_id: str,
    parent_revision_id: str | None,
    application_id: str,
    created_at: str,
    tasks: list[TaskSnapshot],
    requirement_mappings: list[RequirementMapping],
    dependency_changes: list[DependencyChange],
    change_summary: list[str],
    rollback_metadata: Any,
    audit_event_ids: list[str],
) -> RuntimePlanRevision:
    validate_dependency_graph(tasks)
    validate_path_overlap(tasks)
    graph_checksum = checksum_text(
        yaml.safe_dump([task.to_dict() for task in tasks], sort_keys=True),
    )
    revision = RuntimePlanRevision(
        schema_version=1,
        revision_id=revision_id,
        parent_revision_id=parent_revision_id,
        application_id=application_id,
        created_at=created_at,
        task_graph=tuple(tasks),
        task_statuses={task.task_id: task.status for task in tasks},
        requirement_mappings=tuple(requirement_mappings),
        dependency_mappings=tuple(dependency_changes),
        graph_checksum=graph_checksum,
        revision_checksum="",
        change_summary=tuple(change_summary),
        rollback_metadata=rollback_metadata,
        audit_event_ids=tuple(audit_event_ids),
    )
    revision_checksum = checksum_text(yaml.safe_dump(revision.to_dict(), sort_keys=True))
    return RuntimePlanRevision.from_dict({**revision.to_dict(), "revision_checksum": revision_checksum})


def diff_runtime_graph(
    source_task: TaskSnapshot,
    proposed_tasks: list[TaskSnapshot],
    existing_tasks: list[TaskSnapshot],
) -> RuntimeGraphDiff:
    revised_tasks = tuple(build_revised_task_graph(source_task, proposed_tasks, existing_tasks))
    existing_by_id = {task.task_id: task for task in existing_tasks}
    proposed_ids = {task.task_id for task in proposed_tasks}

    dependency_changes = tuple(
        DependencyChange(
            task_id=task.task_id,
            prior_dependencies=existing_by_id.get(task.task_id, task).depends_on,
            new_dependencies=task.depends_on,
            summary=(
                "dependency rewired after task replacement"
                if task.task_id not in proposed_ids
                else "new task dependencies"
            ),
        )
        for task in revised_tasks
        if task.task_id in proposed_ids or existing_by_id.get(task.task_id, task).depends_on != task.depends_on
    )

    task_changes = _build_task_changes(source_task, proposed_tasks, revised_tasks)
    affected_pending = tuple(task.task_id for task in revised_tasks if task.status != "completed")
    affected_completed = tuple(task.task_id for task in revised_tasks if task.status == "completed")
    resume_candidates = tuple(task.task_id for task in revised_tasks if task.status == "ready")
    requirement_mappings = tuple(
        RequirementMapping(
            requirement_id=requirement,
            task_ids=tuple(task.task_id for task in revised_tasks if requirement in task.requirement_ids),
        )
        for requirement in sorted({req for task in revised_tasks for req in task.requirement_ids})
    )
    writable_path_diff = tuple(sorted({path for task in proposed_tasks for path in task.writable_paths}))
    return RuntimeGraphDiff(
        source_task_id=source_task.task_id,
        affected_completed_tasks=affected_completed,
        affected_pending_tasks=affected_pending,
        resume_candidates=resume_candidates,
        dependency_changes=dependency_changes,
        requirement_mappings=requirement_mappings,
        task_changes=task_changes,
        writable_path_diff=writable_path_diff,
        revised_tasks=revised_tasks,
    )


def build_revised_task_graph(
    source_task: TaskSnapshot,
    proposed_tasks: list[TaskSnapshot],
    existing_tasks: list[TaskSnapshot],
) -> list[TaskSnapshot]:
    if not existing_tasks:
        return [source_task, *proposed_tasks]

    existing_ids = [task.task_id for task in existing_tasks]
    if len(set(existing_ids)) != len(existing_ids):
        raise ValueError("Task IDs must be unique in the source revision.")

    proposed_ids = [task.task_id for task in proposed_tasks]
    if len(set(proposed_ids)) != len(proposed_ids):
        raise ValueError("Duplicate task IDs are not allowed in the proposed revision.")

    source_is_replaced_in_place = len(proposed_tasks) == 1 and proposed_tasks[0].task_id == source_task.task_id
    if not source_is_replaced_in_place:
        collisions = sorted(
            task_id for task_id in proposed_ids if task_id != source_task.task_id and task_id in existing_ids
        )
        if collisions:
            raise ValueError(f"Proposed task IDs already exist in the runtime revision: {', '.join(collisions)}")

    if source_is_replaced_in_place:
        updated_tasks = _normalize_metadata_update_task(source_task, proposed_tasks[0])
        revised_tasks: list[TaskSnapshot] = []
        inserted = False
        for task in existing_tasks:
            if task.task_id == source_task.task_id:
                revised_tasks.append(updated_tasks)
                inserted = True
            else:
                revised_tasks.append(task)
        if not inserted:
            raise ValueError(f"Source task was not found in the active runtime revision: {source_task.task_id}")
        validate_dependency_graph(revised_tasks)
        validate_path_overlap(revised_tasks)
        return revised_tasks

    replacement_ids = tuple(_terminal_proposed_task_ids(proposed_tasks))
    normalized_proposed = [_normalize_proposed_task(source_task, task) for task in proposed_tasks]

    revised_tasks = []
    inserted = False
    for task in existing_tasks:
        if task.task_id == source_task.task_id:
            superseded = TaskSnapshot.from_dict(
                {
                    **task.to_dict(),
                    "status": "superseded",
                    "writable_paths": [],
                    "superseded_by": list(replacement_ids),
                    "history": list(dict.fromkeys([*task.history, task.task_id])),
                },
            )
            revised_tasks.append(superseded)
            revised_tasks.extend(normalized_proposed)
            inserted = True
            continue

        rewritten_depends = _rewire_dependencies(task.depends_on, source_task.task_id, replacement_ids)
        revised_tasks.append(
            _recalculate_task(
                task,
                rewritten_depends,
                revised_tasks,
                source_task.task_id,
            ),
        )

    if not inserted:
        raise ValueError(f"Source task was not found in the active runtime revision: {source_task.task_id}")

    validate_dependency_graph(revised_tasks)
    validate_path_overlap(revised_tasks)
    return revised_tasks


def _build_task_changes(
    source_task: TaskSnapshot,
    proposed_tasks: list[TaskSnapshot],
    revised_tasks: tuple[TaskSnapshot, ...],
) -> tuple[TaskChange, ...]:
    if len(proposed_tasks) == 1 and proposed_tasks[0].task_id == source_task.task_id:
        updated_task = proposed_tasks[0]
        return (
            TaskChange(
                task_id=source_task.task_id,
                change_type="updated",
                prior_status=source_task.status,
                new_status=updated_task.status,
                summary=f"{source_task.task_id} updated in place",
            ),
        )

    changes: list[TaskChange] = [
        TaskChange(
            task_id=source_task.task_id,
            change_type="superseded",
            prior_status=source_task.status,
            new_status="superseded",
            summary=f"{source_task.task_id} superseded by {', '.join(task.task_id for task in proposed_tasks)}",
        ),
    ]
    for task in proposed_tasks:
        changes.append(
            TaskChange(
                task_id=task.task_id,
                change_type="added",
                prior_status="",
                new_status=task.status,
                summary=f"{task.task_id} added to the replacement graph",
            ),
        )
    return tuple(changes)


def _normalize_proposed_task(source_task: TaskSnapshot, task: TaskSnapshot) -> TaskSnapshot:
    return TaskSnapshot.from_dict(
        {
            **task.to_dict(),
            "depends_on": [dependency for dependency in task.depends_on if dependency != source_task.task_id],
            "source_task_id": task.source_task_id or source_task.task_id,
            "history": list(dict.fromkeys([source_task.task_id, *task.history])),
        },
    )


def _normalize_metadata_update_task(source_task: TaskSnapshot, task: TaskSnapshot) -> TaskSnapshot:
    return TaskSnapshot.from_dict(
        {
            **task.to_dict(),
            "source_task_id": source_task.source_task_id or source_task.task_id,
            "history": list(dict.fromkeys([*source_task.history, source_task.task_id, *task.history])),
        },
    )


def _terminal_proposed_task_ids(proposed_tasks: list[TaskSnapshot]) -> list[str]:
    dependent_ids = {dependency for task in proposed_tasks for dependency in task.depends_on}
    return [task.task_id for task in proposed_tasks if task.task_id not in dependent_ids]


def _rewire_dependencies(
    dependencies: tuple[str, ...],
    source_task_id: str,
    replacement_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if source_task_id not in dependencies:
        return dependencies
    rewired: list[str] = []
    for dependency in dependencies:
        if dependency != source_task_id:
            rewired.append(dependency)
            continue
        for replacement_id in replacement_ids:
            if replacement_id not in rewired:
                rewired.append(replacement_id)
    return tuple(rewired)


def _recalculate_task(
    task: TaskSnapshot,
    rewritten_depends: tuple[str, ...],
    revised_tasks: list[TaskSnapshot],
    source_task_id: str,
) -> TaskSnapshot:
    if rewritten_depends == task.depends_on:
        return task
    if task.status in {"completed", "superseded"}:
        return task

    revised_map = {item.task_id: item for item in revised_tasks}
    if rewritten_depends and all(revised_map.get(dependency, task).status == "completed" for dependency in rewritten_depends):
        new_status = "ready"
    elif task.status == "ready" and source_task_id in task.depends_on:
        new_status = "blocked"
    else:
        new_status = task.status

    return TaskSnapshot.from_dict(
        {
            **task.to_dict(),
            "depends_on": list(rewritten_depends),
            "status": new_status,
        },
    )
