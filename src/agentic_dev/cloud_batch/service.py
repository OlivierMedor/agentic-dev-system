from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agentic_dev.cloud_application import ApplicationService
from agentic_dev.cloud_application.models import ApplicationPlan, ApplicationRecord
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
from agentic_dev.cloud_queue import show_cloud_queue_request
from agentic_dev.cloud_queue.imports import load_imported_response
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
        if dry_run:
            batch = self.show(batch_id)
            plan = load_orchestration_plan(self.project_path, batch_id)
            return BatchApplyResult(
                batch_id=batch_id,
                plan=plan,
                application_records=(),
                application_plans=(),
                item_results=plan.items and tuple(ItemResult(item_id=item.item_id, outcome="dry_run", message="no mutation") for item in plan.items) or (),
                status=plan.status,
                dry_run=True,
            )
        with acquire_batch_lock(self.project_path, batch_id, "apply"):
            batch = self.show(batch_id)
            plan = load_orchestration_plan(self.project_path, batch_id)
            application_records: list[ApplicationRecord] = []
            application_plans: list[ApplicationPlan] = []
            item_results: list[ItemResult] = []
            updated_items: list[BatchItem] = []
            for item in sorted(plan.items, key=lambda value: value.item_id):
                request = show_cloud_queue_request(self.project_path, item.request_id).request
                if item.response_checksum:
                    load_imported_response(self.project_path, item.request_id)
                else:
                    raise ValueError(f"Imported response missing for request: {item.request_id}")
                service = self._application_service_for_item(batch, item)
                result = service.plan_apply(request.request_id, dry_run=False)
                application_records.append(result.application)
                application_plans.append(result.plan)
                item_results.append(
                    ItemResult(
                        item_id=item.item_id,
                        outcome=result.application.status,
                        message="applied",
                        request_checksum=result.application.request_checksum,
                        response_checksum=result.application.response_checksum,
                        plan_checksum=result.plan.plan_checksum,
                        application_id=result.application.application_id,
                        revision_id=result.application.revision_id or "",
                        attempt_id=f"{batch_id}-{item.item_id}-attempt",
                    ),
                )
                updated_items.append(
                    type(item).from_dict(
                        {
                            **item.to_dict(),
                            "status": "applied",
                            "application_id": result.application.application_id,
                            "revision_id": result.application.revision_id or "",
                            "plan_checksum": result.plan.plan_checksum,
                            "result": {"status": result.application.status},
                        },
                    ),
                )
            new_progress = derive_batch_progress(updated_items)
            new_result = derive_batch_result(batch_id, updated_items, item_results)
            updated = type(batch).from_dict(
                {
                    **batch.to_dict(),
                    "status": new_result.status,
                    "progress": new_progress.to_dict(),
                    "results": new_result.to_dict(),
                    "latest_plan_id": plan.plan_id,
                    "items": [item.to_dict() for item in updated_items],
                    "checksums": {
                        **batch.checksums,
                        "plan": plan.checksums.get("plan", ""),
                        "result": checksum_text(str([item.to_dict() for item in updated_items])),
                    },
                },
            )
            save_batch_record(self.project_path, updated)
            append_batch_audit_event(
                self.project_path,
                BatchAuditEvent(
                    event_id="",
                    event_type="batch_apply",
                    batch_id=batch_id,
                    prior_state=batch.status,
                    new_state=new_result.status,
                    timestamp=self.now_factory(),
                    details={"item_ids": [item.item_id for item in plan.items]},
                ),
            )
            return BatchApplyResult(
                batch_id=batch_id,
                plan=plan,
                application_records=tuple(application_records),
                application_plans=tuple(application_plans),
                item_results=tuple(item_results),
                status=new_result.status,
                dry_run=False,
            )

    def resume(self, batch_id: str) -> BatchResumeResult:
        with acquire_batch_lock(self.project_path, batch_id, "resume"):
            batch = self.show(batch_id)
            groups = build_resume_groups(batch_id, list(batch.items))
            item_results: list[ItemResult] = []
            updated_items: list[BatchItem] = []
            for group in groups:
                for item_id in group.item_ids:
                    item = next(candidate for candidate in batch.items if candidate.item_id == item_id)
                    service = self._application_service_for_item(batch, item)
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
                            attempt_id=f"{batch_id}-{item.item_id}-resume",
                            lease_ids=result.lease_ids,
                        ),
                    )
                    updated_items.append(
                        type(item).from_dict(
                            {
                                **item.to_dict(),
                                "status": "resumed",
                                "lease_id": result.lease_ids[0] if result.lease_ids else item.lease_id,
                                "result": {"status": result.status},
                            },
                        ),
                    )
            if not updated_items:
                updated_items = list(batch.items)
            updated = type(batch).from_dict(
                {
                    **batch.to_dict(),
                    "status": "resumed",
                    "results": {
                        **batch.results.to_dict(),
                        "status": "resumed",
                        "item_results": [item.to_dict() for item in item_results],
                    },
                    "items": [item.to_dict() for item in updated_items],
                    "checksums": {
                        **batch.checksums,
                        "result": checksum_text(str([item.to_dict() for item in updated_items])),
                    },
                },
            )
            save_batch_record(self.project_path, updated)
            append_batch_audit_event(
                self.project_path,
                BatchAuditEvent(
                    event_id="",
                    event_type="batch_resume",
                    batch_id=batch_id,
                    prior_state=batch.status,
                    new_state="resumed",
                    timestamp=self.now_factory(),
                    details={"groups": [list(group.item_ids) for group in groups]},
                ),
            )
            return BatchResumeResult(batch_id=batch_id, resume_groups=tuple(tuple(group.item_ids) for group in groups), item_results=tuple(item_results), status="resumed")

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


def build_default_batch_service(project_path: Path) -> BatchService:
    return BatchService(project_path)
