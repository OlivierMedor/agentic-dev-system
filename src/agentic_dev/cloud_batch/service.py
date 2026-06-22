from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agentic_dev.cloud_application import ApplicationService
from agentic_dev.cloud_application.models import ApplicationPlan, ApplicationRecord
from agentic_dev.cloud_application.planning import load_active_runtime_state
from agentic_dev.cloud_batch.audit import BatchAuditEvent, append_batch_audit_event
from agentic_dev.cloud_batch.cancellation import CancellationResult, cancel_batch
from agentic_dev.cloud_batch.concurrency import acquire_batch_lock
from agentic_dev.cloud_batch.export import BatchExportResult, export_batch
from agentic_dev.cloud_batch.import_bundle import BatchImportResult, import_response_bundle
from agentic_dev.cloud_batch.models import (
    BatchItem,
    BatchRecord,
    ItemResult,
    OrchestrationPlan,
)
from agentic_dev.cloud_batch.conflicts import detect_batch_conflicts
from agentic_dev.cloud_batch.persistence import (
    ensure_batch_dirs,
    load_batch_record,
    load_orchestration_plan,
    save_batch_record,
    save_orchestration_plan,
)
from agentic_dev.cloud_batch.planning import (
    build_batch_orchestration_plan,
    build_resume_groups,
    derive_batch_progress,
    derive_batch_result,
)
from agentic_dev.cloud_batch.recovery import BatchRecoveryResult, recover_batch
from agentic_dev.cloud_batch.retry import retry_batch
from agentic_dev.cloud_batch.rollback import RollbackResult, rollback_batch
from agentic_dev.cloud_batch.graph import batch_dependency_ready_set, batch_dependency_topological_order
from agentic_dev.cloud_queue.persistence import checksum_text, now_iso


@dataclass(frozen=True)
class BatchApplyPlanResult:
    batch_id: str
    plan: OrchestrationPlan
    status: str


@dataclass(frozen=True)
class BatchApplyResult:
    batch_id: str
    plan: OrchestrationPlan
    application_records: tuple[ApplicationRecord, ...]
    application_plans: tuple[ApplicationPlan, ...]
    item_results: tuple[ItemResult, ...]
    status: str
    dry_run: bool


@dataclass(frozen=True)
class BatchResumeResult:
    batch_id: str
    resume_groups: tuple[tuple[str, ...], ...]
    item_results: tuple[ItemResult, ...]
    status: str


@dataclass(frozen=True)
class BatchStatusResult:
    batches: tuple[BatchRecord, ...]
    counts_by_state: dict[str, int]


class BatchService:
    def __init__(
        self,
        project_path: Path,
        *,
        now_factory: Callable[[], str] | None = None,
    ) -> None:
        self.project_path = project_path.resolve()
        self.now_factory = now_factory or now_iso

    def list_batches(self) -> tuple[BatchRecord, ...]:
        paths = ensure_batch_dirs(self.project_path)
        records = []
        if paths.records.exists():
            for path in sorted(paths.records.glob("*.yaml")):
                records.append(load_batch_record(self.project_path, path.stem))
        return tuple(records)

    def show(self, batch_id: str) -> BatchRecord:
        return load_batch_record(self.project_path, batch_id)

    def status(self) -> BatchStatusResult:
        batches = self.list_batches()
        counts: dict[str, int] = {}
        for batch in batches:
            counts[batch.status] = counts.get(batch.status, 0) + 1
        return BatchStatusResult(batches=batches, counts_by_state=counts)

    def export(self, *, request_ids: list[str] | None = None, all_ready: bool = False, batch_id: str | None = None) -> BatchExportResult:
        result = export_batch(self.project_path, request_ids=request_ids, all_ready=all_ready, batch_id=batch_id)
        return result

    def import_bundle(self, bundle_path: Path, *, batch_id: str | None = None) -> BatchImportResult:
        return import_response_bundle(self.project_path, bundle_path, batch_id=batch_id)

    def plan_apply(self, batch_id: str, *, dry_run: bool = False) -> BatchApplyPlanResult:
        if dry_run:
            batch = self.show(batch_id)
            planning_result = build_batch_orchestration_plan(
                self.project_path,
                batch,
                persist_item_plans=False,
            )
            return BatchApplyPlanResult(batch_id=batch_id, plan=planning_result.orchestration_plan, status="planned")
        with acquire_batch_lock(self.project_path, batch_id, "plan"):
            batch = self.show(batch_id)
            planning_result = build_batch_orchestration_plan(self.project_path, batch)
            save_orchestration_plan(self.project_path, planning_result.orchestration_plan)
            save_batch_record(
                self.project_path,
                type(batch).from_dict(
                    {
                        **batch.to_dict(),
                        "status": "planned",
                        "latest_plan_id": planning_result.orchestration_plan.plan_id,
                        "progress": planning_result.orchestration_plan.progress.to_dict(),
                        "checksums": {
                            **batch.checksums,
                            "plan": planning_result.orchestration_plan.checksums.get("plan", ""),
                            "dependency_graph": planning_result.orchestration_plan.checksums.get("dependency_graph", ""),
                        },
                    },
                ),
            )
            append_batch_audit_event(
                self.project_path,
                BatchAuditEvent(
                    event_id="",
                    event_type="batch_plan",
                    batch_id=batch_id,
                    prior_state=batch.status,
                    new_state="planned",
                    timestamp=self.now_factory(),
                    details={"plan_id": planning_result.orchestration_plan.plan_id},
                ),
            )
            return BatchApplyPlanResult(batch_id=batch_id, plan=planning_result.orchestration_plan, status="planned")

    def apply(self, batch_id: str, *, dry_run: bool = False) -> BatchApplyResult:
        from agentic_dev.cloud_batch.orchestration_runtime import run_dependency_aware_batch_apply

        return run_dependency_aware_batch_apply(
            self.project_path,
            batch_id,
            now_factory=self.now_factory,
            dry_run=dry_run,
        )

    def resume(self, batch_id: str) -> BatchResumeResult:
        from agentic_dev.cloud_batch.orchestration_runtime import run_dependency_aware_batch_resume

        return run_dependency_aware_batch_resume(
            self.project_path,
            batch_id,
            now_factory=self.now_factory,
        )

    def retry(self, batch_id: str, reason: str = ""):
        with acquire_batch_lock(self.project_path, batch_id, "retry"):
            return retry_batch(self.project_path, batch_id, reason=reason)

    def cancel(self, batch_id: str, reason: str = "") -> CancellationResult:
        with acquire_batch_lock(self.project_path, batch_id, "cancel"):
            return cancel_batch(self.project_path, batch_id, reason=reason)

    def rollback(self, batch_id: str, reason: str = "") -> RollbackResult:
        with acquire_batch_lock(self.project_path, batch_id, "rollback"):
            return rollback_batch(self.project_path, batch_id, reason=reason)

    def recover(self, batch_id: str) -> BatchRecoveryResult:
        with acquire_batch_lock(self.project_path, batch_id, "recover"):
            return recover_batch(self.project_path, batch_id)

    def _application_service_for_item(self, batch: BatchRecord, item: BatchItem) -> ApplicationService:
        return ApplicationService(
            self.project_path,
            application_id_factory=lambda: item.application_id or f"{batch.batch_id}-{item.item_id}-application",
            revision_id_factory=lambda: item.revision_id or f"{batch.batch_id}-{item.item_id}-revision",
            lease_id_factory=lambda: item.lease_id or f"{batch.batch_id}-{item.item_id}-lease",
            attempt_id_factory=lambda: f"{batch.batch_id}-{item.item_id}-attempt",
        )


def _validate_orchestration_plan_snapshot(batch: BatchRecord, plan: OrchestrationPlan) -> None:
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


def _run_batch_apply(
    project_path: Path,
    batch_id: str,
    batch: BatchRecord,
    plan: OrchestrationPlan,
    *,
    now_factory: Callable[[], str],
    dry_run: bool,
) -> BatchApplyResult:
    item_map = {item.item_id: item for item in batch.items}
    application_records: list[ApplicationRecord] = []
    application_plans: list[ApplicationPlan] = []
    item_results: list[ItemResult] = []
    expected_active_revision_id: str | None = None
    commit_waves = tuple(wave for wave in plan.execution_waves if wave.phase == "commit") or (
        plan.execution_waves[-1:] if plan.execution_waves else ()
    )

    for wave in commit_waves:
        current_batch = load_batch_record(project_path, batch_id)
        current_plan = load_orchestration_plan(project_path, batch_id)
        _validate_orchestration_plan_snapshot(current_batch, current_plan)
        item_map = {item.item_id: item for item in current_batch.items}
        runtime_state = load_active_runtime_state(project_path)
        if expected_active_revision_id is not None and runtime_state.revision.revision_id != expected_active_revision_id:
            raise ValueError("Active runtime revision changed between batch items.")
        ready_set = set(batch_dependency_ready_set(list(item_map.values()), completed=_successful_item_ids(item_map)))
        conflict_result = detect_batch_conflicts(list(item_map.values()))
        for item_id in wave.item_ids:
            item = item_map[item_id]
            if _is_terminal_item(item) or item.status == "cancelled":
                continue
            blocker_ids = _dependency_blockers(item, item_map)
            if blocker_ids:
                if _dependency_blocked(item_map, blocker_ids):
                    item_map[item_id] = _mark_blocked_item(item, blocker_ids)
                    current_batch = _persist_batch_snapshot(
                        project_path,
                        current_batch,
                        item_map,
                        plan,
                        item_results,
                        now_factory=now_factory,
                        status_override=None,
                        event_type="batch_apply_blocked",
                        event_details={"item_id": item_id, "blocked_by": blocker_ids},
                    )
                continue
            if item_id not in ready_set:
                continue
            runtime_state = load_active_runtime_state(project_path)
            if expected_active_revision_id is not None and runtime_state.revision.revision_id != expected_active_revision_id:
                raise ValueError("Active runtime revision changed between batch items.")
            try:
                service = _application_service_for_item(project_path, batch_id, current_batch, item)
                if dry_run:
                    result = service.plan_apply(item.request_id, dry_run=True)
                    application_result = result.application
                    application_plan = result.plan
                else:
                    result = service.plan_apply(item.request_id, dry_run=False)
                    application_result = result.application
                    application_plan = result.plan
                application_records.append(application_result)
                application_plans.append(application_plan)
                item_results.append(
                    ItemResult(
                        item_id=item.item_id,
                        outcome="dry_run" if dry_run else "applied",
                        message="no mutation" if dry_run else "applied",
                        request_checksum=application_result.request_checksum,
                        response_checksum=application_result.response_checksum,
                        approval_checksum=application_result.approval_checksum or "",
                        plan_checksum=application_plan.plan_checksum,
                        application_id=application_result.application_id,
                        revision_id=application_result.revision_id or "",
                        attempt_id=f"{batch_id}-{item.item_id}-attempt",
                    ),
                )
                if not dry_run:
                    item_map[item_id] = type(item).from_dict(
                        {
                            **item.to_dict(),
                            "status": "applied",
                            "application_id": application_result.application_id,
                            "revision_id": application_result.revision_id or "",
                            "response_checksum": application_result.response_checksum,
                            "approval_checksum": application_result.approval_checksum or item.approval_checksum,
                            "plan_checksum": application_plan.plan_checksum,
                            "result": {
                                "status": application_result.status,
                                "application_id": application_result.application_id,
                                "revision_id": application_result.revision_id or "",
                            },
                        },
                    )
                    current_batch = _persist_batch_snapshot(
                        project_path,
                        current_batch,
                        item_map,
                        plan,
                        item_results,
                        now_factory=now_factory,
                        status_override=None,
                        event_type="batch_apply_item",
                        event_details={"item_id": item_id, "wave_id": wave.wave_id},
                    )
                    runtime_state = load_active_runtime_state(project_path)
                    expected_active_revision_id = runtime_state.revision.revision_id
            except Exception as error:  # noqa: BLE001
                item_results.append(
                    ItemResult(
                        item_id=item.item_id,
                        outcome="failed",
                        message=_safe_batch_error_message(error),
                        request_checksum=item.request_checksum,
                        response_checksum=item.response_checksum,
                        approval_checksum=item.approval_checksum,
                        plan_checksum=item.plan_checksum,
                        attempt_id=f"{batch_id}-{item.item_id}-attempt",
                        details={"error_type": type(error).__name__},
                    ),
                )
                if not dry_run:
                    item_map[item_id] = _mark_failed_item(item, error)
                    _propagate_dependency_blocks(item_map, item_id)
                    current_batch = _persist_batch_snapshot(
                        project_path,
                        current_batch,
                        item_map,
                        plan,
                        item_results,
                        now_factory=now_factory,
                        status_override=None,
                        event_type="batch_apply_item_failed",
                        event_details={"item_id": item_id, "wave_id": wave.wave_id, "error_type": type(error).__name__},
                    )
                continue
            conflict_result = detect_batch_conflicts(list(item_map.values()))
        _ = conflict_result

    final_batch = load_batch_record(project_path, batch_id) if not dry_run else batch
    final_items = list((load_batch_record(project_path, batch_id).items if not dry_run else batch.items))
    if dry_run:
        final_items = [item_map[item.item_id] for item in batch.items]
    else:
        final_items = [item_map[item.item_id] for item in load_batch_record(project_path, batch_id).items]
    final_result = derive_batch_result(batch_id, final_items, item_results)
    final_progress = derive_batch_progress(final_items)
    final_batch = _persist_batch_snapshot(
        project_path,
        final_batch,
        item_map,
        plan,
        item_results,
        now_factory=now_factory,
        status_override=final_result.status,
        event_type="batch_apply_dry_run" if dry_run else "batch_apply_complete",
        event_details={"dry_run": dry_run, "item_count": len(item_results)},
        persist=not dry_run,
    )
    if dry_run:
        final_batch = type(batch).from_dict(
            {
                **batch.to_dict(),
                "progress": final_progress.to_dict(),
                "results": final_result.to_dict(),
            },
        )
    return BatchApplyResult(
        batch_id=batch_id,
        plan=plan,
        application_records=tuple(application_records),
        application_plans=tuple(application_plans),
        item_results=tuple(item_results),
        status=final_result.status,
        dry_run=dry_run,
    )


def _execute_batch_resume(
    project_path: Path,
    batch_id: str,
    batch: BatchRecord,
    plan: OrchestrationPlan,
    *,
    now_factory: Callable[[], str],
) -> BatchResumeResult:
    item_map = {item.item_id: item for item in batch.items}
    groups = build_resume_groups(batch_id, list(plan.items))
    item_results: list[ItemResult] = []
    expected_active_revision_id = load_active_runtime_state(project_path).revision.revision_id
    for group in groups:
        current_batch = load_batch_record(project_path, batch_id)
        current_plan = load_orchestration_plan(project_path, batch_id)
        _validate_orchestration_plan_snapshot(current_batch, current_plan)
        runtime_state = load_active_runtime_state(project_path)
        if runtime_state.revision.revision_id != expected_active_revision_id:
            raise ValueError("Active runtime revision changed before resume group execution.")
        group_failed = False
        for item_id in group.item_ids:
            item = item_map[item_id]
            if item.status in {"cancelled", "superseded", "failed"} or _is_terminal_item(item):
                continue
            blocker_ids = _dependency_blockers(item, item_map)
            if blocker_ids:
                item_map[item_id] = _mark_blocked_item(item, blocker_ids)
                continue
            if not _item_ready_for_resume(item):
                continue
            try:
                service = _application_service_for_item(project_path, batch_id, current_batch, item)
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
                current_batch = _persist_batch_snapshot(
                    project_path,
                    current_batch,
                    item_map,
                    plan,
                    item_results,
                    now_factory=now_factory,
                    status_override=None,
                    event_type="batch_resume_item",
                    event_details={"item_id": item_id, "group_id": group.wave_id},
                )
                expected_active_revision_id = load_active_runtime_state(project_path).revision.revision_id
            except Exception as error:  # noqa: BLE001
                group_failed = True
                item_results.append(
                    ItemResult(
                        item_id=item.item_id,
                        outcome="failed",
                        message=_safe_batch_error_message(error),
                        request_checksum=item.request_checksum,
                        response_checksum=item.response_checksum,
                        application_id=item.application_id,
                        revision_id=item.revision_id,
                        attempt_id=f"{batch_id}-{item.item_id}-resume",
                        details={"error_type": type(error).__name__},
                    ),
                )
                item_map[item_id] = _mark_failed_item(item, error)
                current_batch = _persist_batch_snapshot(
                    project_path,
                    current_batch,
                    item_map,
                    plan,
                    item_results,
                    now_factory=now_factory,
                    status_override=None,
                    event_type="batch_resume_item_failed",
                    event_details={"item_id": item_id, "group_id": group.wave_id, "error_type": type(error).__name__},
                )
                break
        if group_failed:
            _propagate_dependency_blocks(item_map, group.item_ids[-1] if group.item_ids else "")
            current_batch = _persist_batch_snapshot(
                project_path,
                current_batch,
                item_map,
                plan,
                item_results,
                now_factory=now_factory,
                status_override=None,
                event_type="batch_resume_group_failed",
                event_details={"group_id": group.wave_id},
            )
            continue

    final_items = [item_map[item.item_id] for item in batch.items]
    final_result = derive_batch_result(batch_id, final_items, item_results)
    final_batch = _persist_batch_snapshot(
        project_path,
        load_batch_record(project_path, batch_id),
        item_map,
        plan,
        item_results,
        now_factory=now_factory,
        status_override=final_result.status,
        event_type="batch_resume_complete",
        event_details={"group_count": len(groups)},
    )
    _ = final_batch
    return BatchResumeResult(
        batch_id=batch_id,
        resume_groups=tuple(tuple(group.item_ids) for group in groups),
        item_results=tuple(item_results),
        status=final_result.status,
    )


def _persist_batch_snapshot(
    project_path: Path,
    batch: BatchRecord,
    item_map: dict[str, BatchItem],
    plan: OrchestrationPlan,
    item_results: list[ItemResult],
    *,
    now_factory: Callable[[], str],
    status_override: str | None,
    event_type: str,
    event_details: dict[str, object],
    persist: bool = True,
) -> BatchRecord:
    items = [item_map[item_id] for item_id in batch.item_ids if item_id in item_map]
    progress = derive_batch_progress(items)
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
                details=event_details,
            ),
        )
    return updated


def _application_service_for_item(project_path: Path, batch_id: str, batch: BatchRecord, item: BatchItem) -> ApplicationService:
    return ApplicationService(
        project_path,
        application_id_factory=lambda: item.application_id or f"{batch_id}-{item.item_id}-application",
        revision_id_factory=lambda: item.revision_id or f"{batch_id}-{item.item_id}-revision",
        lease_id_factory=lambda: item.lease_id or f"{batch_id}-{item.item_id}-lease",
        attempt_id_factory=lambda: f"{batch_id}-{item.item_id}-attempt",
    )


def _successful_item_ids(item_map: dict[str, BatchItem]) -> tuple[str, ...]:
    return tuple(sorted(item_id for item_id, item in item_map.items() if item.status in {"applied", "resumed"}))


def _dependency_blockers(item: BatchItem, item_map: dict[str, BatchItem]) -> tuple[str, ...]:
    blockers = [
        dependency
        for dependency in item.dependencies
        if dependency in item_map and item_map[dependency].status not in {"applied", "resumed"}
    ]
    return tuple(sorted(dict.fromkeys(blockers)))


def _dependency_blocked(item_map: dict[str, BatchItem], blocker_ids: tuple[str, ...]) -> bool:
    return any(item_map[blocker_id].status in {"failed", "partially_failed", "cancelled", "superseded", "validation_partial"} for blocker_id in blocker_ids if blocker_id in item_map)


def _propagate_dependency_blocks(item_map: dict[str, BatchItem], failed_item_id: str) -> None:
    if not failed_item_id:
        return
    ordered_ids = batch_dependency_topological_order([item for item in item_map.values()])
    failed_like = {"failed", "partially_failed", "cancelled", "superseded", "validation_partial"}
    changed = True
    while changed:
        changed = False
        for item_id in ordered_ids:
            item = item_map[item_id]
            if item.status in {"applied", "resumed", "failed", "cancelled", "superseded"}:
                continue
            blockers = tuple(sorted(dependency for dependency in item.dependencies if item_map.get(dependency, item).status in failed_like))
            if blockers:
                item_map[item_id] = type(item).from_dict(
                    {
                        **item.to_dict(),
                        "status": "validation_partial",
                        "result": {"status": "blocked", "blocked_by": list(blockers)},
                    },
                )
                changed = True


def _mark_blocked_item(item: BatchItem, blocked_by: tuple[str, ...]) -> BatchItem:
    return type(item).from_dict(
        {
            **item.to_dict(),
            "status": "validation_partial",
            "result": {"status": "blocked", "blocked_by": list(blocked_by)},
        },
    )


def _mark_failed_item(item: BatchItem, error: Exception) -> BatchItem:
    return type(item).from_dict(
        {
            **item.to_dict(),
            "status": "failed",
            "result": {
                "status": "failed",
                "error_type": type(error).__name__,
                "message": _safe_batch_error_message(error),
            },
        },
    )


def _item_ready_for_resume(item: BatchItem) -> bool:
    return item.status in {"applied", "partially_applied", "resumed", "partially_resumed"}


def _is_terminal_item(item: BatchItem) -> bool:
    return item.status in {"applied", "resumed", "failed", "rolled_back", "cancelled", "superseded"}


def _safe_batch_error_message(error: Exception) -> str:
    return str(error).strip()[:240]


def build_default_batch_service(project_path: Path) -> BatchService:
    return BatchService(project_path)
