from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from agentic_dev.cloud_application import ApplicationService
from agentic_dev.cloud_application.models import ApplicationPlan, ApplicationRecord
from agentic_dev.cloud_batch.conflicts import ConflictResult, detect_batch_conflicts
from agentic_dev.cloud_batch.graph import batch_dependency_ready_set, batch_dependency_topological_order, validate_batch_dependency_graph
from agentic_dev.cloud_batch.models import (
    BATCH_SCHEMA_VERSION,
    BatchDependencyGraph,
    BatchItem,
    BatchRecord,
    BatchResult,
    ExecutionWave,
    ItemResult,
    OrchestrationPlan,
)
from agentic_dev.cloud_batch.progress import derive_batch_progress
from agentic_dev.cloud_queue import dependencies_resolved, load_imported_response, show_cloud_queue_request
from agentic_dev.cloud_queue.classification import APPROVAL_REQUIRED
from agentic_dev.cloud_queue.imports import imported_response_path
from agentic_dev.cloud_queue.persistence import checksum_text, now_iso


@dataclass(frozen=True)
class BatchPlanningResult:
    batch_record: BatchRecord
    orchestration_plan: OrchestrationPlan
    application_records: tuple[ApplicationRecord, ...]
    application_plans: tuple[ApplicationPlan, ...]
    blocked_item_ids: tuple[str, ...]
    conflict_result: ConflictResult
    item_results: tuple[ItemResult, ...]


def build_batch_orchestration_plan(
    project_path: Path,
    batch_record: BatchRecord,
    *,
    application_service_factory: Callable[[BatchItem], ApplicationService] | None = None,
    persist_item_plans: bool = True,
    now_factory: Callable[[], str] | None = None,
) -> BatchPlanningResult:
    now_factory = now_factory or now_iso
    validate_batch_dependency_graph(list(batch_record.items))
    conflict_result = detect_batch_conflicts(list(batch_record.items))
    if batch_record.execution_policy.max_concurrency <= 0:
        raise ValueError("Execution policy max_concurrency must be positive.")

    application_records: list[ApplicationRecord] = []
    application_plans: list[ApplicationPlan] = []
    item_results: list[ItemResult] = []
    blocked_item_ids: list[str] = []
    service_factory = application_service_factory or _default_application_service_factory(project_path, batch_record)

    for item in sorted(batch_record.items, key=lambda value: value.request_id):
        request = show_cloud_queue_request(project_path, item.request_id).request
        if not dependencies_resolved(project_path, request):
            blocked_item_ids.append(item.item_id)
            item_results.append(
                ItemResult(
                    item_id=item.item_id,
                    outcome="blocked",
                    message="dependencies unresolved",
                    request_checksum=request.packet_checksum,
                ),
            )
            continue

        response_path = imported_response_path(project_path, request.request_id)
        if not response_path.exists():
            blocked_item_ids.append(item.item_id)
            item_results.append(
                ItemResult(
                    item_id=item.item_id,
                    outcome="pending",
                    message="response not imported",
                    request_checksum=request.packet_checksum,
                ),
            )
            continue

        response = load_imported_response(project_path, request.request_id)
        if request.classification == APPROVAL_REQUIRED and not request.approval_checksum:
            blocked_item_ids.append(item.item_id)
            item_results.append(
                ItemResult(
                    item_id=item.item_id,
                    outcome="blocked",
                    message="approval required before planning",
                    request_checksum=request.packet_checksum,
                    response_checksum=response.checksum,
                ),
            )
            continue
        if request.state in {"validated_failed", "rejected", "canceled", "failed"}:
            blocked_item_ids.append(item.item_id)
            item_results.append(
                ItemResult(
                    item_id=item.item_id,
                    outcome="blocked",
                    message=f"request is not eligible: {request.state}",
                    request_checksum=request.packet_checksum,
                    response_checksum=response.checksum,
                ),
            )
            continue

        service = service_factory(item)
        if persist_item_plans:
            planned = service.plan_apply(request.request_id, dry_run=True)
            application_records.append(planned.application)
            application_plans.append(planned.plan)
            item_results.append(
                ItemResult(
                    item_id=item.item_id,
                    outcome="planned",
                    message="application plan created",
                    request_checksum=planned.application.request_checksum,
                    response_checksum=planned.application.response_checksum,
                    approval_checksum=planned.application.approval_checksum or "",
                    plan_checksum=planned.plan.plan_checksum,
                    application_id=planned.application.application_id,
                    revision_id=planned.plan.proposed_revision_id,
                    details={
                        "application_path": str(planned.application_path),
                        "plan_path": str(planned.plan_path),
                    },
                ),
            )
        else:
            item_results.append(
                ItemResult(
                    item_id=item.item_id,
                    outcome="planned",
                    message="dry-run plan preview only",
                    request_checksum=request.packet_checksum,
                    response_checksum=response.checksum,
                ),
            )

    progress = derive_batch_progress(list(batch_record.items))
    if not item_results:
        item_results = [
            ItemResult(item_id=item.item_id, outcome=item.status, message="no operation performed")
            for item in batch_record.items
        ]
    dependency_graph = BatchDependencyGraph(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id=batch_record.batch_id,
        node_ids=tuple(item.item_id for item in batch_record.items),
        dependency_map={item.item_id: item.dependencies for item in batch_record.items},
        topological_order=batch_dependency_topological_order(list(batch_record.items)),
        ready_set=batch_dependency_ready_set(list(batch_record.items)),
        checksum=checksum_text(yaml.safe_dump([item.to_dict() for item in batch_record.items], sort_keys=True)),
    )
    waves = build_execution_waves(batch_record.batch_id, list(batch_record.items), conflict_result)
    plan = OrchestrationPlan(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id=batch_record.batch_id,
        plan_id=f"batch-plan-{batch_record.batch_id}",
        batch_type=batch_record.batch_type,
        created_at=now_factory(),
        item_ids=batch_record.item_ids,
        items=batch_record.items,
        dependency_graph=dependency_graph,
        execution_policy=batch_record.execution_policy,
        execution_waves=waves,
        conflict_graph=tuple(conflict.to_dict() for conflict in conflict_result.conflicts),
        expected_revision_chain=tuple(item.revision_id for item in batch_record.items if item.revision_id),
        checksums={
            "plan": checksum_text(yaml.safe_dump(
                {
                    "batch_id": batch_record.batch_id,
                    "items": [item.to_dict() for item in batch_record.items],
                    "waves": [wave.to_dict() for wave in waves],
                    "conflicts": [conflict.to_dict() for conflict in conflict_result.conflicts],
                },
                sort_keys=True,
            )),
            "dependency_graph": dependency_graph.checksum,
        },
        progress=progress,
        status="planned",
        dry_run=not persist_item_plans,
        details={
            "blocked_item_ids": list(blocked_item_ids),
            "application_count": len(application_plans),
        },
    )
    return BatchPlanningResult(
        batch_record=batch_record,
        orchestration_plan=plan,
        application_records=tuple(application_records),
        application_plans=tuple(application_plans),
        blocked_item_ids=tuple(blocked_item_ids),
        conflict_result=conflict_result,
        item_results=tuple(item_results),
    )


def build_execution_waves(batch_id: str, items: list[BatchItem], conflict_result: ConflictResult) -> tuple[ExecutionWave, ...]:
    order = batch_dependency_topological_order(items)
    waves: list[ExecutionWave] = []
    layers: list[list[str]] = []
    for item_id in order:
        item = next(candidate for candidate in items if candidate.item_id == item_id)
        placed = False
        for layer in layers:
            if not _has_path_overlap(layer, item, items):
                layer.append(item_id)
                placed = True
                break
        if not placed:
            layers.append([item_id])

    phases = ("validation", "preparation", "commit", "resume")
    for phase in phases:
        for index, layer in enumerate(layers, start=1):
            waves.append(
                ExecutionWave(
                    wave_id=f"{batch_id}-{phase}-{index:02d}",
                    phase=phase,
                    item_ids=tuple(layer),
                    checksum=checksum_text(yaml.safe_dump({"phase": phase, "item_ids": layer}, sort_keys=True)),
                ),
            )
    return tuple(waves)


def build_resume_groups(batch_id: str, items: list[BatchItem]) -> tuple[ExecutionWave, ...]:
    ordered = batch_dependency_topological_order(items)
    groups: list[list[str]] = []
    for item_id in ordered:
        item = next(candidate for candidate in items if candidate.item_id == item_id)
        placed = False
        for group in groups:
            if not _has_path_overlap(group, item, items):
                group.append(item_id)
                placed = True
                break
        if not placed:
            groups.append([item_id])
    return tuple(
        ExecutionWave(
            wave_id=f"{batch_id}-resume-{index:02d}",
            phase="resume",
            item_ids=tuple(group),
            checksum=checksum_text(yaml.safe_dump({"phase": "resume", "item_ids": group}, sort_keys=True)),
        )
        for index, group in enumerate(groups, start=1)
    )


def derive_batch_result(batch_id: str, items: list[BatchItem], item_results: list[ItemResult]) -> BatchResult:
    from agentic_dev.cloud_batch.progress import derive_batch_result as _derive

    return _derive(batch_id, items, item_results)


def _default_application_service_factory(project_path: Path, batch_record: BatchRecord) -> Callable[[BatchItem], ApplicationService]:
    def factory(item: BatchItem) -> ApplicationService:
        return ApplicationService(
            project_path,
            application_id_factory=lambda: item.application_id or f"{batch_record.batch_id}-{item.item_id}-application",
            revision_id_factory=lambda: item.revision_id or f"{batch_record.batch_id}-{item.item_id}-revision",
            lease_id_factory=lambda: item.lease_id or f"{batch_record.batch_id}-{item.item_id}-lease",
            attempt_id_factory=lambda: f"{batch_record.batch_id}-{item.item_id}-attempt",
        )

    return factory


def _has_path_overlap(group: list[str], item: BatchItem, items: list[BatchItem]) -> bool:
    item_paths = set(item.writable_paths)
    for group_id in group:
        other = next(candidate for candidate in items if candidate.item_id == group_id)
        other_paths = set(other.writable_paths)
        if any(_path_conflict(left, right) for left in item_paths for right in other_paths):
            return True
    return False


def _path_conflict(left: str, right: str) -> bool:
    return left == right or left.startswith(right.rstrip("/*")) or right.startswith(left.rstrip("/*"))
