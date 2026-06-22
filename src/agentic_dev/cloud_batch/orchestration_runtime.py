from __future__ import annotations

from pathlib import Path
from typing import Callable

import yaml

from agentic_dev.cloud_application import ApplicationService
from agentic_dev.cloud_application.planning import load_active_runtime_state
from agentic_dev.cloud_application.persistence import load_execution_leases
from agentic_dev.cloud_batch.audit import BatchAuditEvent, append_batch_audit_event
from agentic_dev.cloud_batch.conflicts import detect_batch_conflicts
from agentic_dev.cloud_batch.graph import batch_dependency_ready_set, batch_dependency_topological_order
from agentic_dev.cloud_batch.models import BatchItem, BatchRecord, ItemResult, OrchestrationPlan
from agentic_dev.cloud_batch.persistence import load_batch_record, load_orchestration_plan, save_batch_record
from agentic_dev.cloud_batch.planning import derive_batch_progress, derive_batch_result, build_resume_groups
from agentic_dev.cloud_batch.service import BatchApplyResult, BatchResumeResult
from agentic_dev.cloud_queue.imports import imported_response_path
from agentic_dev.cloud_queue.models import CloudQueueRequest, CloudQueueResponse
from agentic_dev.cloud_queue.persistence import checksum_text, now_iso


SUCCESS_ITEM_STATUSES = {"applied", "resumed"}
TERMINAL_ITEM_STATUSES = {"applied", "resumed", "failed", "rolled_back", "cancelled", "superseded"}
RESUME_TERMINAL_ITEM_STATUSES = {"resumed", "failed", "rolled_back", "cancelled", "superseded"}
FAILURE_ITEM_STATUSES = {"failed", "partially_failed", "cancelled", "superseded", "validation_partial"}


def run_dependency_aware_batch_apply(
    project_path: Path,
    batch_id: str,
    *,
    now_factory: Callable[[], str] | None = None,
    dry_run: bool = False,
) -> BatchApplyResult:
    now_factory = now_factory or now_iso
    batch = load_batch_record(project_path, batch_id)
    plan = load_orchestration_plan(project_path, batch_id)
    _validate_plan_snapshot(batch, plan)

    item_map = {item.item_id: item for item in batch.items}
    application_records = []
    application_plans = []
    item_results: list[ItemResult] = []
    expected_active_revision_id = load_active_runtime_state(project_path).revision.revision_id
    commit_waves = tuple(wave for wave in plan.execution_waves if wave.phase == "commit") or plan.execution_waves[-1:]

    for wave in commit_waves:
        batch = load_batch_record(project_path, batch_id)
        plan = load_orchestration_plan(project_path, batch_id)
        _validate_plan_snapshot(batch, plan)
        item_map = {item.item_id: item for item in batch.items}
        runtime_state = load_active_runtime_state(project_path)
        if expected_active_revision_id is not None and runtime_state.revision.revision_id != expected_active_revision_id:
            raise ValueError("Active runtime revision changed between batch items.")
        detect_batch_conflicts(list(item_map.values()))

        for item_id in wave.item_ids:
            item = item_map[item_id]
            if item.status in TERMINAL_ITEM_STATUSES or item.status == "cancelled":
                continue
            blocker_ids = _dependency_blockers(item, item_map)
            if blocker_ids:
                if _dependency_blocked(item_map, blocker_ids):
                    item_map[item_id] = _blocked_item(item, blocker_ids)
                    batch = _persist_batch(project_path, batch, plan, item_map, item_results, now_factory=now_factory, event_type="batch_apply_blocked", details={"item_id": item_id, "blocked_by": list(blocker_ids)}, persist=not dry_run)
                continue
            ready_set = set(batch_dependency_ready_set(list(item_map.values()), completed=_successful_item_ids(item_map)))
            if item_id not in ready_set:
                continue
            runtime_state = load_active_runtime_state(project_path)
            if expected_active_revision_id is not None and runtime_state.revision.revision_id != expected_active_revision_id:
                raise ValueError("Active runtime revision changed between batch items.")
            service = _make_application_service(project_path, batch_id, item)
            try:
                _validate_batch_item_snapshot(project_path, item)
                result = service.plan_apply(item.request_id, dry_run=dry_run)
                application_records.append(result.application)
                application_plans.append(result.plan)
                item_results.append(
                    ItemResult(
                        item_id=item.item_id,
                        outcome="dry_run" if dry_run else "applied",
                        message="no mutation" if dry_run else "applied",
                        request_checksum=result.application.request_checksum,
                        response_checksum=result.application.response_checksum,
                        approval_checksum=result.application.approval_checksum or "",
                        plan_checksum=result.plan.plan_checksum,
                        application_id=result.application.application_id,
                        revision_id=result.application.revision_id or "",
                        attempt_id=f"{batch_id}-{item.item_id}-attempt",
                    ),
                )
                item_map[item_id] = _applied_item(item, result.application.application_id, result.application.revision_id or "", result.plan.plan_checksum, result.application.response_checksum, result.application.approval_checksum or item.approval_checksum)
                batch = _persist_batch(project_path, batch, plan, item_map, item_results, now_factory=now_factory, event_type="batch_apply_item", details={"item_id": item_id, "wave_id": wave.wave_id}, persist=not dry_run)
                if not dry_run:
                    expected_active_revision_id = load_active_runtime_state(project_path).revision.revision_id
            except Exception as error:  # noqa: BLE001
                item_results.append(
                    ItemResult(
                        item_id=item.item_id,
                        outcome="failed",
                        message=_safe_message(error),
                        request_checksum=item.request_checksum,
                        response_checksum=item.response_checksum,
                        approval_checksum=item.approval_checksum,
                        plan_checksum=item.plan_checksum,
                        attempt_id=f"{batch_id}-{item.item_id}-attempt",
                        details={"error_type": type(error).__name__},
                ),
                )
                item_map[item_id] = _failed_item(item, error)
                _propagate_dependency_blocks(item_map, item_id)
                batch = _persist_batch(project_path, batch, plan, item_map, item_results, now_factory=now_factory, event_type="batch_apply_item_failed", details={"item_id": item_id, "failed_item_id": item_id, "wave_id": wave.wave_id, "error_type": type(error).__name__}, persist=not dry_run)

    final_items = [item_map[item.item_id] for item in batch.items]
    final_result = derive_batch_result(batch_id, final_items, item_results)
    final_progress = derive_batch_progress(final_items)
    if dry_run:
        final_result = BatchApplyResult(
            batch_id=batch_id,
            plan=plan,
            application_records=tuple(application_records),
            application_plans=tuple(application_plans),
            item_results=tuple(item_results),
            status=final_result.status,
            dry_run=True,
        )
        return final_result
    _persist_batch(project_path, batch, plan, item_map, item_results, now_factory=now_factory, status_override=final_result.status, event_type="batch_apply_complete", details={"item_count": len(item_results)}, persist=True, progress_override=final_progress)
    return BatchApplyResult(
        batch_id=batch_id,
        plan=plan,
        application_records=tuple(application_records),
        application_plans=tuple(application_plans),
        item_results=tuple(item_results),
        status=final_result.status,
        dry_run=False,
    )


def run_dependency_aware_batch_resume(
    project_path: Path,
    batch_id: str,
    *,
    now_factory: Callable[[], str] | None = None,
) -> BatchResumeResult:
    now_factory = now_factory or now_iso
    batch = load_batch_record(project_path, batch_id)
    plan = load_orchestration_plan(project_path, batch_id)
    _validate_plan_snapshot(batch, plan)
    item_map = {item.item_id: item for item in batch.items}
    groups = build_resume_groups(batch_id, list(plan.items))
    item_results: list[ItemResult] = []
    active_state = load_active_runtime_state(project_path)
    expected_active_revision_id = active_state.revision.revision_id
    expected_active_revision_checksum = active_state.revision.revision_checksum
    halted = False

    for group_index, group in enumerate(groups):
        if halted:
            break
        batch = load_batch_record(project_path, batch_id)
        plan = load_orchestration_plan(project_path, batch_id)
        _validate_plan_snapshot(batch, plan)
        runtime_state = load_active_runtime_state(project_path)
        if runtime_state.revision.revision_id != expected_active_revision_id or runtime_state.revision.revision_checksum != expected_active_revision_checksum:
            remaining_ids = _remaining_resume_item_ids(groups, group_index, 0, item_map)
            _mark_remaining_resume_items(item_map, remaining_ids, reason="active_revision_changed")
            batch = _persist_batch(
                project_path,
                batch,
                plan,
                item_map,
                item_results,
                now_factory=now_factory,
                event_type="batch_resume_stale",
                details={
                    "group_id": group.wave_id,
                    "expected_revision_id": expected_active_revision_id,
                    "expected_revision_checksum": expected_active_revision_checksum,
                    "actual_revision_id": runtime_state.revision.revision_id,
                    "actual_revision_checksum": runtime_state.revision.revision_checksum,
                },
                persist=True,
            )
            break
        for item_index, item_id in enumerate(group.item_ids):
            item = item_map[item_id]
            if item.status in RESUME_TERMINAL_ITEM_STATUSES:
                continue
            runtime_state = load_active_runtime_state(project_path)
            if runtime_state.revision.revision_id != expected_active_revision_id or runtime_state.revision.revision_checksum != expected_active_revision_checksum:
                remaining_ids = (item_id,) + _remaining_resume_item_ids(groups, group_index, item_index, item_map)
                _mark_remaining_resume_items(item_map, remaining_ids, reason="active_revision_changed")
                batch = _persist_batch(
                    project_path,
                    batch,
                    plan,
                    item_map,
                    item_results,
                    now_factory=now_factory,
                    event_type="batch_resume_stale",
                    details={
                        "item_id": item_id,
                        "group_id": group.wave_id,
                        "expected_revision_id": expected_active_revision_id,
                        "expected_revision_checksum": expected_active_revision_checksum,
                        "actual_revision_id": runtime_state.revision.revision_id,
                        "actual_revision_checksum": runtime_state.revision.revision_checksum,
                    },
                    persist=True,
                )
                halted = True
                break
            if _resume_item_lease_conflict(project_path, item, runtime_state):
                item_map[item_id] = _blocked_item(item, ("lease_conflict",))
                remaining_ids = _remaining_resume_item_ids(groups, group_index, item_index, item_map)
                _mark_remaining_resume_items(item_map, remaining_ids, reason="lease_conflict")
                batch = _persist_batch(
                    project_path,
                    batch,
                    plan,
                    item_map,
                    item_results,
                    now_factory=now_factory,
                    event_type="batch_resume_lease_conflict",
                    details={"item_id": item_id, "group_id": group.wave_id},
                    persist=True,
                )
                halted = True
                break
            if not _resume_writable_paths_are_compatible(project_path, item, runtime_state):
                item_map[item_id] = _blocked_item(item, ("writable_path_conflict",))
                remaining_ids = _remaining_resume_item_ids(groups, group_index, item_index, item_map)
                _mark_remaining_resume_items(item_map, remaining_ids, reason="writable_path_conflict")
                batch = _persist_batch(
                    project_path,
                    batch,
                    plan,
                    item_map,
                    item_results,
                    now_factory=now_factory,
                    event_type="batch_resume_writable_path_conflict",
                    details={"item_id": item_id, "group_id": group.wave_id},
                    persist=True,
                )
                halted = True
                break
            blocker_ids = _dependency_blockers(item, item_map)
            if blocker_ids:
                item_map[item_id] = _blocked_item(item, blocker_ids)
                continue
            if item.status not in {"applied", "partially_applied", "resumed", "partially_resumed"}:
                continue
            try:
                service = _make_application_service(project_path, batch_id, item)
                result = service.resume(item.request_id)
                item_results.append(
                    ItemResult(
                        item_id=item.item_id,
                        outcome=result.status,
                        message="resumed",
                        request_checksum=item.request_checksum,
                        response_checksum=item.response_checksum,
                        application_id=item.application_id,
                        revision_id=item.revision_id,
                        lease_ids=result.lease_ids,
                        attempt_id=f"{batch_id}-{item.item_id}-resume",
                    ),
                )
                item_map[item_id] = type(item).from_dict(
                    {
                        **item.to_dict(),
                        "status": "resumed",
                        "lease_id": result.lease_ids[0] if result.lease_ids else item.lease_id,
                        "result": {"status": result.status},
                    },
                )
                batch = _persist_batch(project_path, batch, plan, item_map, item_results, now_factory=now_factory, event_type="batch_resume_item", details={"item_id": item_id, "group_id": group.wave_id}, persist=True)
                active_state = load_active_runtime_state(project_path)
                expected_active_revision_id = active_state.revision.revision_id
                expected_active_revision_checksum = active_state.revision.revision_checksum
            except Exception as error:  # noqa: BLE001
                item_results.append(
                    ItemResult(
                        item_id=item.item_id,
                        outcome="failed",
                        message=_safe_message(error),
                        request_checksum=item.request_checksum,
                        response_checksum=item.response_checksum,
                        application_id=item.application_id,
                        revision_id=item.revision_id,
                        attempt_id=f"{batch_id}-{item.item_id}-resume",
                        details={"error_type": type(error).__name__, "failed_item_id": item_id},
                    ),
                )
                item_map[item_id] = _failed_item(item, error)
                _propagate_dependency_blocks(item_map, item_id)
                batch = _persist_batch(project_path, batch, plan, item_map, item_results, now_factory=now_factory, event_type="batch_resume_item_failed", details={"item_id": item_id, "failed_item_id": item_id, "group_id": group.wave_id, "error_type": type(error).__name__}, persist=True)

    final_items = [item_map[item.item_id] for item in batch.items]
    final_result = derive_batch_result(batch_id, final_items, item_results)
    _persist_batch(project_path, batch, plan, item_map, item_results, now_factory=now_factory, status_override=final_result.status, event_type="batch_resume_complete", details={"group_count": len(groups)}, persist=True)
    return BatchResumeResult(
        batch_id=batch_id,
        resume_groups=tuple(tuple(group.item_ids) for group in groups),
        item_results=tuple(item_results),
        status=final_result.status,
    )


def _persist_batch(
    project_path: Path,
    batch: BatchRecord,
    plan: OrchestrationPlan,
    item_map: dict[str, BatchItem],
    item_results: list[ItemResult],
    *,
    now_factory: Callable[[], str],
    event_type: str,
    details: dict[str, object],
    persist: bool,
    status_override: str | None = None,
    progress_override=None,
) -> BatchRecord:
    items = [item_map[item.item_id] for item in batch.items]
    progress = progress_override or derive_batch_progress(items)
    result = derive_batch_result(batch.batch_id, items, item_results)
    updated = type(batch).from_dict(
        {
            **batch.to_dict(),
            "status": status_override or result.status,
            "progress": progress.to_dict(),
            "results": {
                **result.to_dict(),
                "status": status_override or result.status,
                "item_results": [item.to_dict() for item in item_results],
            },
            "latest_plan_id": plan.plan_id,
            "items": [item.to_dict() for item in items],
            "checksums": {
                **batch.checksums,
                "plan": plan.checksums.get("plan", batch.checksums.get("plan", "")),
                "dependency_graph": plan.checksums.get("dependency_graph", batch.checksums.get("dependency_graph", "")),
                "result": checksum_text(str([item.to_dict() for item in items])),
            },
        },
    )
    if persist:
        save_batch_record(project_path, updated)
        append_batch_audit_event(
            project_path,
            BatchAuditEvent(
                event_id="",
                event_type=event_type,
                batch_id=batch.batch_id,
                prior_state=batch.status,
                new_state=updated.status,
                timestamp=now_factory(),
                details=details,
            ),
        )
    return updated


def _validate_plan_snapshot(batch: BatchRecord, plan: OrchestrationPlan) -> None:
    if batch.latest_plan_id and batch.latest_plan_id != plan.plan_id:
        raise ValueError("Stale batch plan identifier.")
    if batch.checksums.get("plan") and batch.checksums.get("plan") != plan.checksums.get("plan", ""):
        raise ValueError("Stale batch plan checksum.")
    if batch.checksums.get("dependency_graph") and batch.checksums.get("dependency_graph") != plan.checksums.get("dependency_graph", ""):
        raise ValueError("Stale dependency graph checksum.")
    if tuple(batch.item_ids) != tuple(plan.item_ids):
        raise ValueError("Batch membership changed since planning.")
    if len(batch.items) != len(plan.items):
        raise ValueError("Batch item plan count changed since planning.")
    for batch_item, plan_item in zip(batch.items, plan.items):
        if batch_item.item_id != plan_item.item_id or batch_item.request_id != plan_item.request_id:
            raise ValueError("Batch item plan membership changed since planning.")
        if batch_item.plan_checksum and plan_item.plan_checksum and batch_item.plan_checksum != plan_item.plan_checksum:
            raise ValueError("Stale item plan checksum.")
        if batch_item.response_checksum and plan_item.response_checksum and batch_item.response_checksum != plan_item.response_checksum:
            raise ValueError("Stale response checksum.")
        if batch_item.approval_checksum and plan_item.approval_checksum and batch_item.approval_checksum != plan_item.approval_checksum:
            raise ValueError("Stale approval state.")


def _make_application_service(project_path: Path, batch_id: str, item: BatchItem) -> ApplicationService:
    return ApplicationService(
        project_path,
        application_id_factory=lambda: item.application_id or f"{batch_id}-{item.item_id}-application",
        revision_id_factory=lambda: item.revision_id or f"{batch_id}-{item.item_id}-revision",
        lease_id_factory=lambda: item.lease_id or f"{batch_id}-{item.item_id}-lease",
        attempt_id_factory=lambda: f"{batch_id}-{item.item_id}-attempt",
    )


def _validate_batch_item_snapshot(project_path: Path, item: BatchItem) -> None:
    requests_root = project_path.resolve() / ".agentic" / "cloud_queue" / "requests"
    if not requests_root.exists():
        raise FileNotFoundError(f"Cloud queue request was not found: {item.request_id}")
    request_path = next(iter(sorted(requests_root.rglob(f"{item.request_id}.yaml"))), None)
    if request_path is None:
        raise FileNotFoundError(f"Cloud queue request was not found: {item.request_id}")
    loaded_request = yaml.safe_load(request_path.read_text(encoding="utf-8"))
    if not isinstance(loaded_request, dict):
        raise ValueError(f"Request file must contain a YAML mapping: {request_path}")
    request = CloudQueueRequest.from_dict(loaded_request)
    if item.request_checksum and request.packet_checksum and item.request_checksum != request.packet_checksum:
        raise ValueError("Stale request checksum.")
    approval_path = project_path.resolve() / ".agentic" / "cloud_queue" / "approvals" / f"{item.request_id}.yaml"
    if approval_path.exists():
        loaded_approval = yaml.safe_load(approval_path.read_text(encoding="utf-8"))
        if isinstance(loaded_approval, dict):
            approval_checksum = str(loaded_approval.get("normalized_response_checksum", ""))
            if item.approval_checksum and approval_checksum and item.approval_checksum != approval_checksum:
                raise ValueError("Stale approval state.")
    response_path = imported_response_path(project_path, item.request_id)
    if not response_path.exists():
        return
    loaded_response = yaml.safe_load(response_path.read_text(encoding="utf-8"))
    if not isinstance(loaded_response, dict):
        raise ValueError(f"Imported response must be a YAML mapping: {response_path}")
    response = CloudQueueResponse.from_dict(loaded_response, source_file=response_path)
    if item.response_checksum and response.checksum and item.response_checksum != response.checksum:
        raise ValueError("Stale response checksum.")


def _successful_item_ids(item_map: dict[str, BatchItem]) -> tuple[str, ...]:
    return tuple(sorted(item_id for item_id, item in item_map.items() if item.status in SUCCESS_ITEM_STATUSES))


def _dependency_blockers(item: BatchItem, item_map: dict[str, BatchItem]) -> tuple[str, ...]:
    blockers = [dependency for dependency in item.dependencies if dependency in item_map and item_map[dependency].status not in SUCCESS_ITEM_STATUSES]
    return tuple(sorted(dict.fromkeys(blockers)))


def _dependency_blocked(item_map: dict[str, BatchItem], blocker_ids: tuple[str, ...]) -> bool:
    return any(item_map[blocker_id].status in FAILURE_ITEM_STATUSES for blocker_id in blocker_ids if blocker_id in item_map)


def _propagate_dependency_blocks(item_map: dict[str, BatchItem], failed_item_id: str) -> None:
    ordered_ids = batch_dependency_topological_order(list(item_map.values()))
    failed_ids = {failed_item_id}
    changed = True
    while changed:
        changed = False
        for item_id in ordered_ids:
            item = item_map[item_id]
            if item.status in TERMINAL_ITEM_STATUSES:
                continue
            blockers = tuple(
                sorted(
                    dependency
                    for dependency in item.dependencies
                    if dependency in item_map and item_map[dependency].status in FAILURE_ITEM_STATUSES and dependency in failed_ids
                ),
            )
            if blockers:
                blocked_item = _blocked_item(item, blockers)
                if blocked_item != item:
                    item_map[item_id] = blocked_item
                    changed = True
                failed_ids.add(item_id)


def _remaining_resume_item_ids(
    groups: tuple,
    group_index: int,
    item_index: int,
    item_map: dict[str, BatchItem],
) -> tuple[str, ...]:
    remaining: list[str] = []
    for current_group_index, group in enumerate(groups):
        if current_group_index < group_index:
            continue
        start_index = item_index + 1 if current_group_index == group_index else 0
        for candidate_item_id in group.item_ids[start_index:]:
            if candidate_item_id in item_map and item_map[candidate_item_id].status not in RESUME_TERMINAL_ITEM_STATUSES:
                remaining.append(candidate_item_id)
    return tuple(remaining)


def _mark_remaining_resume_items(item_map: dict[str, BatchItem], remaining_item_ids: tuple[str, ...], *, reason: str) -> None:
    for item_id in remaining_item_ids:
        item = item_map[item_id]
        if item.status in RESUME_TERMINAL_ITEM_STATUSES:
            continue
        item_map[item_id] = _blocked_item(item, (reason,))


def _resume_item_lease_conflict(project_path: Path, item: BatchItem, runtime_state) -> bool:
    if not item.lease_id:
        return False
    for lease in load_execution_leases(project_path):
        if lease.runtime_revision_id != runtime_state.revision.revision_id:
            continue
        if lease.lease_id == item.lease_id:
            continue
        if lease.lease_state != "active":
            continue
        if lease.task_id == item.item_id:
            return True
    return False


def _resume_writable_paths_are_compatible(project_path: Path, item: BatchItem, runtime_state) -> bool:
    item_paths = set(item.writable_paths)
    if not item_paths:
        return True
    for lease in load_execution_leases(project_path):
        if lease.runtime_revision_id != runtime_state.revision.revision_id or lease.lease_state != "active":
            continue
        if lease.lease_id == item.lease_id:
            continue
        lease_paths = set(lease.writable_paths)
        for item_path in item_paths:
            for lease_path in lease_paths:
                if _paths_conflict(item_path, lease_path):
                    return False
    return True


def _paths_conflict(left: str, right: str) -> bool:
    left = left.rstrip("/")
    right = right.rstrip("/")
    return left == right or left.startswith(right.rstrip("/*")) or right.startswith(left.rstrip("/*"))


def _blocked_item(item: BatchItem, blocked_by: tuple[str, ...]) -> BatchItem:
    if item.status == "validation_partial" and item.result.get("status") == "blocked" and item.result.get("blocked_by") == list(blocked_by):
        return item
    return type(item).from_dict(
        {
            **item.to_dict(),
            "status": "validation_partial",
            "result": {"status": "blocked", "blocked_by": list(blocked_by)},
        },
    )


def _failed_item(item: BatchItem, error: Exception) -> BatchItem:
    return type(item).from_dict(
        {
            **item.to_dict(),
            "status": "failed",
            "result": {
                "status": "failed",
                "error_type": type(error).__name__,
                "message": _safe_message(error),
            },
        },
    )


def _applied_item(item: BatchItem, application_id: str, revision_id: str, plan_checksum: str, response_checksum: str, approval_checksum: str) -> BatchItem:
    return type(item).from_dict(
        {
            **item.to_dict(),
            "status": "applied",
            "application_id": application_id,
            "revision_id": revision_id,
            "response_checksum": response_checksum,
            "approval_checksum": approval_checksum,
            "plan_checksum": plan_checksum,
            "result": {
                "status": "applied",
                "application_id": application_id,
                "revision_id": revision_id,
            },
        },
    )


def _safe_message(error: Exception) -> str:
    return str(error).strip()[:240]
