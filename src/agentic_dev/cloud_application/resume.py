from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_dev.cloud_application.models import RuntimePlanRevision, TaskSnapshot
from agentic_dev.local_execution import LocalExecutionResult, run_subtask_local_execution
from agentic_dev.subtask_execution import (
    BlueprintSubtask,
    ContextBudget,
    RequiredContext,
)


@dataclass(frozen=True)
class RuntimeResumeExecution:
    result: LocalExecutionResult
    ready_task_ids: tuple[str, ...]
    blocked_task_ids: tuple[str, ...]
    completed_task_ids: tuple[str, ...]


def run_runtime_revision_execution(
    project_path: Path,
    story_name: str,
    revision: RuntimePlanRevision,
    *,
    role: str | None = None,
    resume: bool = True,
    dry_run: bool = False,
    resume_task_ids: tuple[str, ...] | None = None,
    initial_state: dict[str, Any] | None = None,
    http_client: Any | None = None,
) -> RuntimeResumeExecution:
    blueprint_story = {
        "goal": f"Runtime execution for {story_name}",
        "acceptance_criteria": [mapping.requirement_id for mapping in revision.requirement_mappings],
        "subtasks": [task.to_dict() for task in revision.task_graph],
    }
    subtasks = [to_blueprint_subtask(task) for task in revision.task_graph]
    if resume_task_ids is not None:
        selected_task_ids = list(resume_task_ids)
        by_id = {task.id: task for task in subtasks}
        missing = [task_id for task_id in selected_task_ids if task_id not in by_id]
        if missing:
            raise ValueError(f"Resume tasks are missing from the active revision: {', '.join(missing)}")
        subtasks = [by_id[task_id] for task_id in selected_task_ids]
    result = run_subtask_local_execution(
        project_path,
        story_name,
        project_path / "stories" / story_name,
        blueprint_story,
        subtasks,
        role=role,
        resume=resume,
        dry_run=dry_run,
        initial_state=initial_state,
        http_client=http_client,
    )
    ready = tuple(task.task_id for task in revision.task_graph if task.status == "ready")
    blocked = tuple(task.task_id for task in revision.task_graph if task.status == "blocked")
    completed = tuple(task.task_id for task in revision.task_graph if task.status == "completed")
    return RuntimeResumeExecution(
        result=result,
        ready_task_ids=ready,
        blocked_task_ids=blocked,
        completed_task_ids=completed,
    )


def to_blueprint_subtask(task: TaskSnapshot) -> BlueprintSubtask:
    required_context = RequiredContext(
        files=[item for item in task.required_context if item],
        summaries=[],
        prior_task_outputs=[],
        architecture_decisions=[],
    )
    context_budget = ContextBudget(
        max_input_tokens=task.usable_input_tokens or 0,
        reserved_output_tokens=0,
        required_context_must_fit=True,
        allow_required_context_trimming=False,
        oversized_task_policy="reject_for_cloud_redecomposition",
    )
    return BlueprintSubtask(
        id=task.task_id,
        title=task.title,
        role=task.role,
        depends_on=list(task.depends_on),
        requirement_ids=list(task.requirement_ids),
        required_context=required_context,
        writable_paths=list(task.writable_paths),
        expected_outputs=list(task.expected_outputs),
        validation=list(task.validation_steps),
        context_budget=context_budget,
    )
