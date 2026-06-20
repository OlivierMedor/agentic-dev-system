from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentic_dev.cloud_application.models import (
    DependencyChange,
    RequirementMapping,
    RuntimePlanRevision,
    TaskChange,
    TaskSnapshot,
)
from agentic_dev.cloud_application.validation import validate_dependency_graph, validate_path_overlap
from agentic_dev.cloud_queue.persistence import checksum_text
import yaml


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
    affected_pending = tuple(task.task_id for task in existing_tasks if task.status != "completed")
    affected_completed = tuple(task.task_id for task in existing_tasks if task.status == "completed")
    resume_candidates = tuple(task.task_id for task in proposed_tasks if task.status == "ready")
    dependency_changes = tuple(
        DependencyChange(
            task_id=task.task_id,
            prior_dependencies=(),
            new_dependencies=task.depends_on,
            summary="new task dependencies",
        )
        for task in proposed_tasks
    )
    requirement_mappings = tuple(
        RequirementMapping(requirement_id=requirement, task_ids=tuple(task.task_id for task in proposed_tasks if requirement in task.requirement_ids))
        for requirement in sorted({req for task in proposed_tasks for req in task.requirement_ids})
    )
    task_changes = (
        TaskChange(
            task_id=source_task.task_id,
            change_type="superseded",
            prior_status=source_task.status,
            new_status="superseded",
            summary=f"{source_task.task_id} superseded by {', '.join(task.task_id for task in proposed_tasks)}",
        ),
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
    )
