from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agentic_dev.cloud_application.audit import record_application_audit_event
from agentic_dev.cloud_application.graph import build_runtime_graph_revision
from agentic_dev.cloud_application.models import (
    ActiveRevisionPointer,
    ApplicationAuditEvent,
    ApplicationOperation,
    ApplicationPlan,
    ApplicationRecord,
    ApplicationSafety,
    ApplicationSource,
    ApplicationStatusResult,
    ExecutionLease,
    RecoveryResult,
    RequirementMapping,
    ResumeEligibility,
    ResumeResult,
    RollbackMetadata,
    RuntimePlanRevision,
    TaskSnapshot,
)
from agentic_dev.cloud_application.persistence import (
    active_pointer_path,
    application_path,
    application_plan_path,
    application_recovery_path,
    application_root_path,
    ensure_cloud_application_dirs,
    load_active_pointer,
    load_application_record,
    load_execution_leases,
    load_runtime_revision,
    revision_path,
    runtime_active_pointer_path,
    save_active_pointer,
    save_application_plan,
    save_application_record,
    save_execution_lease,
    save_runtime_revision,
    save_transaction_record,
    write_yaml_atomic,
    normalized_yaml_checksum,
    transaction_root_path,
)
from agentic_dev.cloud_application.validation import (
    EligibilityResult,
    validate_approval_scope,
    validate_application_state_boundaries,
    validate_dependency_graph,
    validate_eligibility,
    validate_no_canonical_mutation,
    validate_active_pointer,
)
from agentic_dev.cloud_queue import show_cloud_queue_request
from agentic_dev.cloud_queue.approvals import load_approval_record
from agentic_dev.cloud_queue.classification import APPROVAL_REQUIRED
from agentic_dev.cloud_queue.models import CloudQueueRequest, CloudQueueResponse
from agentic_dev.cloud_queue.persistence import checksum_text, now_iso
from agentic_dev.story_blueprint import load_blueprint_story
from agentic_dev.cloud_queue.imports import load_imported_response
from agentic_dev.cloud_application.planning import (
    RuntimeState,
    build_planned_application,
    load_active_runtime_state,
    resolve_source_task,
)
from agentic_dev.cloud_application.resume import run_runtime_revision_execution
from agentic_dev.cloud_application.transactions import (
    create_transaction_record,
    save_transaction_phase,
    load_transaction,
)
from agentic_dev.cloud_application.publication import validate_publication_gate, quarantine_path


@dataclass(frozen=True)
class ApplicationTransactionHooks:
    fail_on_plan_write: bool = False
    fail_on_revision_write: bool = False
    fail_on_revision_validation: bool = False
    fail_on_publish: bool = False
    fail_on_pointer_update: bool = False
    fail_on_audit_write: bool = False
    fail_on_status_update: bool = False
    fail_after_pointer_update: bool = False


@dataclass(frozen=True)
class PlanApplyResult:
    application: ApplicationRecord
    plan: ApplicationPlan
    dry_run: bool
    active_revision_id: str | None
    active_revision_checksum: str | None
    application_path: Path
    plan_path: Path
    revision_path: Path | None
    pointer_path: Path | None
    audit_event_ids: tuple[str, ...]
    resume_result: ResumeResult | None = None

    @property
    def terminal_summary(self) -> str:
        lines = [
            f"Application {self.application.application_id}: {self.application.status}",
            f"Request: {self.application.request_id}",
            f"Plan: {self.plan.plan_checksum}",
            f"Dry run: {self.dry_run}",
        ]
        if self.revision_path is not None:
            lines.append(f"Revision: {self.revision_path}")
        if self.pointer_path is not None:
            lines.append(f"Active pointer: {self.pointer_path}")
        if self.resume_result is not None:
            lines.append(f"Resume: {self.resume_result.status}")
        return "\n".join(lines)


def build_default_application_service(project_path: Path) -> "ApplicationService":
    return ApplicationService(project_path)


class ApplicationService:
    def __init__(
        self,
        project_path: Path,
        *,
        now_factory: Callable[[], str] | None = None,
        application_id_factory: Callable[[], str] | None = None,
        revision_id_factory: Callable[[], str] | None = None,
        lease_id_factory: Callable[[], str] | None = None,
        attempt_id_factory: Callable[[], str] | None = None,
        event_id_factory: Callable[[], str] | None = None,
        transaction_hooks: ApplicationTransactionHooks | None = None,
    ) -> None:
        self.project_path = project_path.resolve()
        self.now_factory = now_factory or now_iso
        self.application_id_factory = application_id_factory or (lambda: f"cloud-application-{uuid.uuid4().hex[:8]}")
        self.revision_id_factory = revision_id_factory or (lambda: f"runtime-plan-r-{uuid.uuid4().hex[:8]}")
        self.lease_id_factory = lease_id_factory or (lambda: f"lease-{uuid.uuid4().hex[:8]}")
        self.attempt_id_factory = attempt_id_factory or (lambda: f"attempt-{uuid.uuid4().hex[:8]}")
        self.event_id_factory = event_id_factory or (lambda: f"ae-{uuid.uuid4().hex[:12]}")
        self.transaction_hooks = transaction_hooks or ApplicationTransactionHooks()

    def plan_apply(self, request_id: str, *, dry_run: bool = False) -> PlanApplyResult:
        ensure_cloud_application_dirs(self.project_path)
        request, response = self._load_request_and_response(request_id)
        approval_record = self._load_approval_record_if_present(request)
        eligibility = validate_eligibility(request, approval_record=approval_record)
        if not eligibility.eligible:
            raise ValueError(eligibility.reason)

        runtime_state = load_active_runtime_state(self.project_path)
        source_task = resolve_source_task(runtime_state, request)
        planned = build_planned_application(request, response, source_task, runtime_state)
        if request.classification == APPROVAL_REQUIRED and approval_record is not None:
            validate_approval_scope(approval_record, list(request.writable_paths), list(request.requirements))
        validate_no_canonical_mutation(
            ApplicationPlan(
                schema_version=1,
                application_id="",
                request_id=request.request_id,
                request_checksum=eligibility.request_checksum,
                response_checksum=eligibility.response_checksum,
                approval_checksum=eligibility.approval_checksum,
                source_revision_id=runtime_state.revision.revision_id,
                source_revision_checksum=runtime_state.revision.revision_checksum,
                proposed_revision_id="",
                operation_type=planned.operation.operation_type,
                source_task_snapshot=source_task,
                proposed_tasks=planned.proposed_tasks,
                requirement_mapping=planned.diff.requirement_mappings,
                dependency_changes=planned.diff.dependency_changes,
                writable_path_diff=planned.diff.writable_path_diff,
                context_budget_validation={},
                expected_outputs=planned.operation.expected_outputs,
                validation_steps=planned.operation.validation_steps,
                affected_completed_tasks=planned.diff.affected_completed_tasks,
                affected_pending_tasks=planned.diff.affected_pending_tasks,
                resume_candidates=planned.diff.resume_candidates,
                rollback_target=runtime_state.revision.revision_id,
                preconditions=(planned.operation.operation_type,),
                predicted_side_effects=("preserve canonical blueprint",),
                plan_checksum="",
                created_at=self.now_factory(),
            )
        )

        application_id = self.application_id_factory()
        proposed_revision_id = self.revision_id_factory()
        diff = planned.diff
        application = self._build_application_record(
            application_id,
            request,
            response,
            eligibility,
            proposed_revision_id,
            dry_run=dry_run,
            source_task=source_task,
            proposed_tasks=list(planned.proposed_tasks),
            diff=diff,
            active_revision_id=runtime_state.revision.revision_id,
        )
        plan = self._build_application_plan(
            application,
            request,
            response,
            eligibility,
            proposed_revision_id,
            source_task,
            list(planned.proposed_tasks),
            diff,
            active_revision_id=runtime_state.revision.revision_id,
            active_revision_checksum=runtime_state.revision.revision_checksum,
            dry_run=dry_run,
        )
        validate_application_state_boundaries(plan)
        application = ApplicationRecord.from_dict({**application.to_dict(), "plan_checksum": plan.plan_checksum})
        application_path = save_application_record(self.project_path, application)
        plan_path = save_application_plan(self.project_path, plan)
        audit_ids = [self._record_audit("application_planned", application, request, "new", application.status, {"dry_run": dry_run})]

        if dry_run:
            return PlanApplyResult(
                application=application,
                plan=plan,
                dry_run=True,
                active_revision_id=runtime_state.revision.revision_id,
                active_revision_checksum=runtime_state.revision.revision_checksum,
                application_path=application_path,
                plan_path=plan_path,
                revision_path=None,
                pointer_path=None,
                audit_event_ids=tuple(audit_ids),
            )

        application = self._transition_application(
            application,
            "ready_to_apply",
            request,
            details={"plan_checksum": plan.plan_checksum},
        )
        save_application_record(self.project_path, application)
        result = self._apply_plan(application, plan, request, response, source_task, list(planned.proposed_tasks), diff, audit_ids, runtime_state)
        return result

    def application_status(self) -> ApplicationStatusResult:
        ensure_cloud_application_dirs(self.project_path)
        applications_dir = application_root_path(self.project_path) / "applications"
        applications: list[ApplicationRecord] = []
        if applications_dir.exists():
            for path in sorted(applications_dir.glob("*.yaml")):
                applications.append(load_application_record(path))
        active_pointer = None
        if runtime_active_pointer_path(self.project_path).exists():
            active_pointer = load_active_pointer(runtime_active_pointer_path(self.project_path))
        counts: dict[str, int] = {}
        for application in applications:
            counts[application.status] = counts.get(application.status, 0) + 1
        return ApplicationStatusResult(
            project_path=self.project_path,
            applications=tuple(applications),
            active_pointer=active_pointer,
            counts_by_state=counts,
        )

    def application_show(self, application_id: str) -> ApplicationRecord:
        return load_application_record(application_path(self.project_path, application_id))

    def resume(self, request_id: str) -> ResumeResult:
        request = self._load_request(request_id)
        application = self._load_application_for_request(request_id)
        revision = self._load_revision(application.revision_id or "")
        pointer = load_active_pointer(runtime_active_pointer_path(self.project_path))
        validate_active_pointer(pointer, revision.revision_id, revision.revision_checksum)
        resume_eligibility = self._build_resume_eligibility(revision, application)
        if not resume_eligibility.eligible:
            raise ValueError("; ".join(resume_eligibility.reasons) or "Resume is not eligible.")
        application = self._transition_application(application, "resuming", request, details={"revision_id": revision.revision_id})
        save_application_record(self.project_path, application)
        lease_ids: list[str] = []
        for task_id in resume_eligibility.resume_from_task_ids:
            lease = self._create_lease(task_id, revision)
            lease_ids.append(lease.lease_id)
        resume_state_path = application_root_path(self.project_path) / "recovery" / f"{application.application_id}_resume.yaml"
        write_yaml_atomic(
            resume_state_path,
            {
                "application_id": application.application_id,
                "request_id": request_id,
                "revision_id": revision.revision_id,
                "status": "resuming",
                "task_ids": list(resume_eligibility.resume_from_task_ids),
                "lease_ids": lease_ids,
            },
        )
        execution = run_runtime_revision_execution(
            self.project_path,
            request.story,
            revision,
            resume=True,
            dry_run=False,
        )
        if execution.result.status != "completed":
            application = self._transition_application(
                application,
                "resume_failed",
                request,
                details={"lease_ids": lease_ids, "execution_status": execution.result.status},
            )
            save_application_record(self.project_path, application)
            self._record_audit(
                "resume_failed",
                application,
                request,
                "resuming",
                "resume_failed",
                {"lease_ids": lease_ids, "execution_status": execution.result.status},
            )
            return ResumeResult(
                project_path=self.project_path,
                application_id=application.application_id,
                revision_id=revision.revision_id,
                revision_checksum=revision.revision_checksum,
                task_ids=resume_eligibility.resume_from_task_ids,
                lease_ids=tuple(lease_ids),
                status="resume_failed",
                reasons=(execution.result.status,),
                resume_state_path=resume_state_path,
                execution_status_path=execution.result.state_path,
            )
        result_checksum = checksum_text(execution.result.state_path.read_text(encoding="utf-8"))
        for lease in load_execution_leases(self.project_path):
            if lease.runtime_revision_id != revision.revision_id or lease.lease_state != "active":
                continue
            current_pointer = load_active_pointer(runtime_active_pointer_path(self.project_path))
            validate_active_pointer(current_pointer, revision.revision_id, revision.revision_checksum)
            validate_publication_gate(
                self.project_path,
                lease=lease,
                execution_attempt_id=lease.execution_attempt_id,
                active_pointer=current_pointer,
                result_checksum=result_checksum,
                result_path=execution.result.state_path,
            )
            save_execution_lease(
                self.project_path,
                ExecutionLease.from_dict({**lease.to_dict(), "completion_checksum": result_checksum}),
            )
        application = self._transition_application(
            application,
            "resumed",
            request,
            details={"lease_ids": lease_ids},
        )
        application = ApplicationRecord.from_dict(
            {
                **application.to_dict(),
                "revision_id": revision.revision_id,
                "revision_checksum": revision.revision_checksum,
                "active_revision_id": revision.revision_id,
                "resume": {
                    **resume_eligibility.__dict__,
                },
            },
        )
        save_application_record(self.project_path, application)
        self._record_audit("resume", application, request, "resuming", "resumed", {"lease_ids": lease_ids})
        return ResumeResult(
            project_path=self.project_path,
            application_id=application.application_id,
            revision_id=revision.revision_id,
            revision_checksum=revision.revision_checksum,
            task_ids=resume_eligibility.resume_from_task_ids,
            lease_ids=tuple(lease_ids),
            status="resumed",
            reasons=resume_eligibility.reasons,
            resume_state_path=resume_state_path,
            execution_status_path=execution.result.state_path,
            execution_report_path=execution.result.state_path,
        )

    def rollback(self, application_id: str) -> ApplicationRecord:
        application = load_application_record(application_path(self.project_path, application_id))
        if application.status not in {"applied", "resumed", "rollback_available", "rollback_failed"}:
            raise ValueError("Application is not eligible for rollback.")
        if not application.revision_id:
            raise ValueError("Application has no revision to roll back from.")
        revision = self._load_revision(application.revision_id)
        prior_revision_id = revision.parent_revision_id
        if not prior_revision_id:
            raise ValueError("No prior revision exists for rollback.")
        prior_revision = self._load_revision(prior_revision_id)
        pointer = load_active_pointer(runtime_active_pointer_path(self.project_path))
        if pointer.active_revision_id != revision.revision_id:
            raise ValueError("Current active revision does not match the application revision.")
        if pointer.active_revision_checksum != revision.revision_checksum:
            raise ValueError("Current active revision checksum does not match the application revision.")
        leases = load_execution_leases(self.project_path)
        active_lease_ids = [
            lease.lease_id
            for lease in leases
            if lease.runtime_revision_id == revision.revision_id and lease.lease_state == "active"
        ]
        rollback_transaction = create_transaction_record(
            transaction_id=f"rollback-{application.application_id}",
            application_id=application.application_id,
            source_revision_id=revision.parent_revision_id or "",
            source_revision_checksum=prior_revision.revision_checksum,
            proposed_revision_id=prior_revision.revision_id,
            proposed_revision_checksum=prior_revision.revision_checksum,
            expected_active_pointer=revision.revision_id,
            created_at=self.now_factory(),
            updated_at=self.now_factory(),
            artifact_paths=(str(revision_path(self.project_path, revision.revision_id)),),
            recovery_action="restore prior pointer atomically",
            details={"active_lease_ids": active_lease_ids},
        )
        save_transaction_record(self.project_path, rollback_transaction)
        for lease in leases:
            if lease.runtime_revision_id == revision.revision_id and lease.lease_state == "active":
                save_execution_lease(
                    self.project_path,
                    ExecutionLease.from_dict({**lease.to_dict(), "lease_state": "stale"}),
                )
        pointer = ActiveRevisionPointer(
            schema_version=1,
            active_revision_id=prior_revision.revision_id,
            active_revision_checksum=prior_revision.revision_checksum,
            previous_revision_id=revision.revision_id,
            update_timestamp=self.now_factory(),
            application_id=application.application_id,
        )
        save_active_pointer(self.project_path, pointer)
        save_transaction_phase(
            self.project_path,
            rollback_transaction,
            phase="committed",
            updated_at=self.now_factory(),
            details={"rolled_back_to": prior_revision.revision_id},
        )
        rolled_back = ApplicationRecord.from_dict(
            {
                **application.to_dict(),
                "status": "rolled_back",
                "active_revision_id": prior_revision.revision_id,
                "revision_id": prior_revision.revision_id,
                "revision_checksum": prior_revision.revision_checksum,
            },
        )
        save_application_record(self.project_path, rolled_back)
        self._record_audit(
            "rollback",
            rolled_back,
            self._load_request(application.request_id),
            "rollback_available",
            "rolled_back",
            {"prior_revision_id": prior_revision_id, "active_lease_ids": active_lease_ids},
        )
        return rolled_back

    def recover(self) -> RecoveryResult:
        ensure_cloud_application_dirs(self.project_path)
        findings: list[str] = []
        actions: list[str] = []
        reconciled = False
        pointer = None
        pointer_path = runtime_active_pointer_path(self.project_path)
        transactions: list[Any] = []
        if transaction_root_path(self.project_path).exists():
            for path in sorted(transaction_root_path(self.project_path).glob("*.yaml")):
                try:
                    transactions.append(load_transaction(path))
                except Exception:
                    findings.append(f"corrupt transaction record: {path.name}")
                    actions.append("inspect transaction journal manually")
        if pointer_path.exists():
            try:
                pointer = load_active_pointer(pointer_path)
            except Exception:
                findings.append("corrupt active pointer")
                actions.append("replace pointer only after operator review")
        else:
            findings.append("missing active pointer")
            actions.append("select an active revision only after recovery review")

        applications = self.application_status().applications
        for application in applications:
            if application.status == "applying":
                transaction = next((item for item in transactions if item.application_id == application.application_id), None)
                if transaction and transaction.phase in {"revision_written", "revision_validated"}:
                    findings.append(f"application recoverable after interrupted apply: {application.application_id}")
                    actions.append(f"re-run apply for {application.application_id}")
                    reconciled = True
                    save_application_record(
                        self.project_path,
                        ApplicationRecord.from_dict({**application.to_dict(), "status": "application_validation_failed"}),
                    )
                else:
                    findings.append(f"application stuck in applying: {application.application_id}")
                    actions.append(f"reconcile application {application.application_id}")
            if application.status == "rolling_back":
                findings.append(f"application stuck in rolling_back: {application.application_id}")
                actions.append(f"reconcile rollback for {application.application_id}")

        for lease in load_execution_leases(self.project_path):
            if lease.runtime_revision_id and not revision_path(self.project_path, lease.runtime_revision_id).exists():
                findings.append(f"stale lease: {lease.lease_id}")
                actions.append(f"quarantine lease {lease.lease_id}")
                quarantine_target = quarantine_path(self.project_path, lease.lease_id)
                quarantine_target.parent.mkdir(parents=True, exist_ok=True)
                write_yaml_atomic(quarantine_target, lease.to_dict())
                reconciled = True

        if pointer is not None:
            for transaction in transactions:
                if transaction.phase in {"revision_published", "pointer_updated"}:
                    revision_file = revision_path(self.project_path, transaction.proposed_revision_id)
                    if revision_file.exists():
                        revision = load_runtime_revision(revision_file)
                        if revision.revision_checksum == transaction.proposed_revision_checksum or not transaction.proposed_revision_checksum:
                            if pointer.active_revision_id != revision.revision_id and transaction.phase == "revision_published":
                                save_active_pointer(
                                    self.project_path,
                                    ActiveRevisionPointer(
                                        schema_version=1,
                                        active_revision_id=revision.revision_id,
                                        active_revision_checksum=revision.revision_checksum,
                                        previous_revision_id=transaction.source_revision_id or None,
                                        update_timestamp=self.now_factory(),
                                        application_id=transaction.application_id,
                                    ),
                                )
                                reconciled = True
                                findings.append(f"reconciled published revision: {revision.revision_id}")
                                actions.append(f"complete pointer update for {transaction.application_id}")
                            app = next((item for item in applications if item.application_id == transaction.application_id), None)
                            if app and app.status == "applying" and transaction.phase == "pointer_updated":
                                save_application_record(
                                    self.project_path,
                                    ApplicationRecord.from_dict({**app.to_dict(), "status": "applied", "revision_id": revision.revision_id, "revision_checksum": revision.revision_checksum, "active_revision_id": revision.revision_id}),
                                )
                                reconciled = True
                                findings.append(f"reconciled stale application status: {app.application_id}")
                                actions.append(f"finalize application {app.application_id}")

        result = RecoveryResult(
            project_path=self.project_path,
            findings=tuple(findings or ["no recovery actions needed"]),
            recommended_actions=tuple(actions or ["no action required"]),
            reconciled=reconciled,
            active_pointer=pointer,
        )
        write_yaml_atomic(application_recovery_path(self.project_path), {
            "project_path": str(self.project_path),
            "findings": list(result.findings),
            "recommended_actions": list(result.recommended_actions),
            "reconciled": result.reconciled,
        })
        self._record_audit("recovery", None, None, "inspect", "inspect", {"findings": list(result.findings)})
        return result

    def _apply_plan(
        self,
        application: ApplicationRecord,
        plan: ApplicationPlan,
        request: CloudQueueRequest,
        response: CloudQueueResponse,
        source_task: TaskSnapshot,
        proposed_tasks: list[TaskSnapshot],
        diff: Any,
        audit_ids: list[str],
        runtime_state: RuntimeState,
    ) -> PlanApplyResult:
        transaction_id = f"txn-{application.application_id}"
        transaction = create_transaction_record(
            transaction_id=transaction_id,
            application_id=application.application_id,
            source_revision_id=runtime_state.revision.revision_id,
            source_revision_checksum=runtime_state.revision.revision_checksum,
            proposed_revision_id=plan.proposed_revision_id,
            proposed_revision_checksum="",
            expected_active_pointer=runtime_state.pointer.active_revision_id,
            created_at=self.now_factory(),
            updated_at=self.now_factory(),
            artifact_paths=(),
            recovery_action="reconcile transaction by re-running apply or recover",
            details={"plan_checksum": plan.plan_checksum},
        )
        save_transaction_record(self.project_path, transaction)
        if self.transaction_hooks.fail_on_plan_write:
            save_transaction_phase(self.project_path, transaction, phase="failed", updated_at=self.now_factory(), details={"reason": "plan_write"})
            raise RuntimeError("Injected failure during plan persistence.")
        application = self._transition_application(
            application,
            "applying",
            request,
            details={"transaction_id": transaction_id, "plan_checksum": plan.plan_checksum},
        )
        transaction = save_transaction_phase(
            self.project_path,
            transaction,
            phase="prepared",
            updated_at=self.now_factory(),
            details={"application_status": application.status},
        )
        if self.transaction_hooks.fail_on_revision_write:
            save_transaction_phase(self.project_path, transaction, phase="failed", updated_at=self.now_factory(), details={"reason": "revision_write"})
            raise RuntimeError("Injected failure during proposed revision write.")
        superseded_source_task = TaskSnapshot.from_dict(
            {
                **source_task.to_dict(),
                "status": "superseded",
                "writable_paths": [],
            },
        )
        proposed_revision = build_runtime_graph_revision(
            revision_id=plan.proposed_revision_id,
            parent_revision_id=plan.source_revision_id,
            application_id=application.application_id,
            created_at=self.now_factory(),
            tasks=[superseded_source_task, *proposed_tasks],
            requirement_mappings=list(diff.requirement_mappings),
            dependency_changes=list(diff.dependency_changes),
            change_summary=[f"{source_task.task_id} superseded"],
            rollback_metadata=RollbackMetadata(
                prior_revision_id=plan.source_revision_id,
                prior_revision_checksum=plan.source_revision_checksum,
                rollback_reason="explicit rollback availability",
                created_at=self.now_factory(),
                application_id=application.application_id,
            ),
            audit_event_ids=audit_ids,
        )
        transaction = type(transaction).from_dict(
            {**transaction.to_dict(), "proposed_revision_checksum": proposed_revision.revision_checksum},
        )
        save_transaction_record(self.project_path, transaction)
        transaction = save_transaction_phase(
            self.project_path,
            transaction,
            phase="revision_written",
            updated_at=self.now_factory(),
            details={"revision_id": proposed_revision.revision_id},
        )
        if self.transaction_hooks.fail_on_revision_validation:
            save_transaction_phase(self.project_path, transaction, phase="failed", updated_at=self.now_factory(), details={"reason": "revision_validation"})
            raise RuntimeError("Injected failure during revision validation.")
        validate_dependency_graph(list(proposed_revision.task_graph))
        transaction = save_transaction_phase(
            self.project_path,
            transaction,
            phase="revision_validated",
            updated_at=self.now_factory(),
            details={"revision_id": proposed_revision.revision_id},
        )
        if self.transaction_hooks.fail_on_publish:
            save_transaction_phase(self.project_path, transaction, phase="failed", updated_at=self.now_factory(), details={"reason": "publish"})
            raise RuntimeError("Injected failure during revision publish.")
        revision_path_obj = save_runtime_revision(self.project_path, proposed_revision)
        transaction = save_transaction_phase(
            self.project_path,
            transaction,
            phase="revision_published",
            updated_at=self.now_factory(),
            artifact_paths=(str(revision_path_obj),),
            details={"revision_path": str(revision_path_obj)},
        )
        current_pointer = load_active_pointer(runtime_active_pointer_path(self.project_path))
        validate_active_pointer(current_pointer, plan.source_revision_id, plan.source_revision_checksum)
        if self.transaction_hooks.fail_on_pointer_update:
            save_transaction_phase(self.project_path, transaction, phase="failed", updated_at=self.now_factory(), details={"reason": "pointer_update"})
            raise RuntimeError("Injected failure during active pointer update.")
        pointer = ActiveRevisionPointer(
            schema_version=1,
            active_revision_id=proposed_revision.revision_id,
            active_revision_checksum=proposed_revision.revision_checksum,
            previous_revision_id=plan.source_revision_id,
            update_timestamp=self.now_factory(),
            application_id=application.application_id,
        )
        save_active_pointer(self.project_path, pointer)
        transaction = save_transaction_phase(
            self.project_path,
            transaction,
            phase="pointer_updated",
            updated_at=self.now_factory(),
            details={"active_revision_id": pointer.active_revision_id},
        )
        if self.transaction_hooks.fail_after_pointer_update:
            save_transaction_phase(self.project_path, transaction, phase="failed", updated_at=self.now_factory(), details={"reason": "after_pointer_update"})
            raise RuntimeError("Injected failure after pointer update.")
        if self.transaction_hooks.fail_on_status_update:
            save_transaction_phase(self.project_path, transaction, phase="failed", updated_at=self.now_factory(), details={"reason": "status_update"})
            raise RuntimeError("Injected failure updating application status.")
        application = self._transition_application(
            application,
            "applied",
            request,
            details={"revision_id": proposed_revision.revision_id},
        )
        application = ApplicationRecord.from_dict(
            {
                **application.to_dict(),
                "revision_id": proposed_revision.revision_id,
                "revision_checksum": proposed_revision.revision_checksum,
                "active_revision_id": proposed_revision.revision_id,
                "resume": self._build_resume_eligibility(proposed_revision, application).__dict__,
                "rollback_available": True,
                "plan_checksum": plan.plan_checksum,
            },
        )
        save_application_record(self.project_path, application)
        transaction = save_transaction_phase(
            self.project_path,
            transaction,
            phase="application_updated",
            updated_at=self.now_factory(),
            details={"application_status": application.status},
        )
        self._record_audit("apply", application, request, "applying", "applied", {"revision_id": proposed_revision.revision_id})
        transaction = save_transaction_phase(
            self.project_path,
            transaction,
            phase="audit_completed",
            updated_at=self.now_factory(),
            details={"audit_event_ids": list(audit_ids)},
        )
        resume_result = None
        if application.resume.eligible:
            application = self._transition_application(
                application,
                "resume_pending",
                request,
                details={"revision_id": proposed_revision.revision_id},
            )
            save_application_record(self.project_path, application)
            self._record_audit("resume_eligible", application, request, "applied", "resume_pending", {"resume_from_task_ids": list(application.resume.resume_from_task_ids)})
        transaction = save_transaction_phase(
            self.project_path,
            transaction,
            phase="committed",
            updated_at=self.now_factory(),
            details={"application_status": application.status},
        )
        return PlanApplyResult(
            application=application,
            plan=plan,
            dry_run=False,
            active_revision_id=proposed_revision.revision_id,
            active_revision_checksum=proposed_revision.revision_checksum,
            application_path=application_path(self.project_path, application.application_id),
            plan_path=application_plan_path(self.project_path, application.application_id),
            revision_path=revision_path_obj,
            pointer_path=active_pointer_path(self.project_path),
            audit_event_ids=tuple(audit_ids),
            resume_result=resume_result,
        )

    def _build_application_record(
        self,
        application_id: str,
        request: CloudQueueRequest,
        response: CloudQueueResponse,
        eligibility: EligibilityResult,
        proposed_revision_id: str,
        *,
        dry_run: bool,
        source_task: TaskSnapshot,
        proposed_tasks: list[TaskSnapshot],
        diff: Any,
        active_revision_id: str,
    ) -> ApplicationRecord:
        resume = self._build_resume_eligibility_placeholder(source_task, proposed_tasks)
        operation_type = str(response.claims.get("operation_type", "replace_task_with_subtasks"))
        operation = ApplicationOperation(
            operation_type=operation_type,
            affected_task_ids=(source_task.task_id,),
            proposed_task_ids=tuple(task.task_id for task in proposed_tasks),
            preserved_requirement_ids=tuple(request.requirements),
            dependency_changes=diff.dependency_changes,
            writable_paths=tuple(task for task in diff.writable_path_diff),
            expected_outputs=tuple(str(item) for item in (response.claims.get("expected_outputs", []) or source_task.expected_outputs)),
            validation_steps=tuple(response.claims.get("validation_steps", []) or []),
        )
        return ApplicationRecord(
            schema_version=1,
            application_id=application_id,
            request_id=request.request_id,
            request_checksum=eligibility.request_checksum,
            response_checksum=eligibility.response_checksum,
            approval_checksum=eligibility.approval_checksum,
            status="application_planned",
            created_at=self.now_factory(),
            source=ApplicationSource(
                request_type=str(request.classification or request.state),
                response_classification=str(request.classification or request.state),
                source_task_id=source_task.task_id,
                source_plan_revision=active_revision_id,
            ),
            application=operation,
            safety=ApplicationSafety(
                canonical_blueprint_modified=False,
                writable_paths_expanded=False,
                requirements_removed=False,
                external_services_added=False,
                network_access_added=False,
                deployment_added=False,
            ),
            resume=resume,
            plan_checksum="",
        )

    def _build_application_plan(
        self,
        application: ApplicationRecord,
        request: CloudQueueRequest,
        response: CloudQueueResponse,
        eligibility: EligibilityResult,
        proposed_revision_id: str,
        source_task: TaskSnapshot,
        proposed_tasks: list[TaskSnapshot],
        diff: Any,
        *,
        active_revision_id: str,
        active_revision_checksum: str,
        dry_run: bool,
    ) -> ApplicationPlan:
        source_revision_id = active_revision_id
        source_revision_checksum = active_revision_checksum
        plan = ApplicationPlan(
            schema_version=1,
            application_id=application.application_id,
            request_id=request.request_id,
            request_checksum=eligibility.request_checksum,
            response_checksum=eligibility.response_checksum,
            approval_checksum=eligibility.approval_checksum,
            source_revision_id=source_revision_id,
            source_revision_checksum=source_revision_checksum,
            proposed_revision_id=proposed_revision_id,
            operation_type=application.application.operation_type,
            source_task_snapshot=source_task,
            proposed_tasks=tuple(proposed_tasks),
            requirement_mapping=diff.requirement_mappings,
            dependency_changes=diff.dependency_changes,
            writable_path_diff=diff.writable_path_diff,
            context_budget_validation={
                "usable_input_tokens": source_task.usable_input_tokens,
                "token_estimate": source_task.token_estimate,
            },
            expected_outputs=tuple(response.claims.get("expected_outputs", []) or []),
            validation_steps=tuple(response.claims.get("validation_steps", []) or []),
            affected_completed_tasks=diff.affected_completed_tasks,
            affected_pending_tasks=diff.affected_pending_tasks,
            resume_candidates=diff.resume_candidates,
            rollback_target=source_revision_id,
            preconditions=(str(application.application.operation_type),),
            predicted_side_effects=("supersede source task", "preserve canonical blueprint"),
            plan_checksum="",
            created_at=self.now_factory(),
            dry_run=dry_run,
        )
        return ApplicationPlan.from_dict({**plan.to_dict(), "plan_checksum": normalized_yaml_checksum(plan.to_dict())})

    def _build_resume_eligibility_placeholder(self, source_task: TaskSnapshot, proposed_tasks: list[TaskSnapshot]) -> ResumeEligibility:
        return ResumeEligibility(
            eligible=False,
            resume_from_task_ids=tuple(task.task_id for task in proposed_tasks if task.status == "ready"),
            blocked_dependents=tuple(),
            previously_completed_tasks=(source_task.task_id,),
            reasons=("resume eligibility is computed after apply",),
        )

    def _build_resume_eligibility(self, revision: RuntimePlanRevision, application: ApplicationRecord) -> ResumeEligibility:
        ready = tuple(task.task_id for task in revision.task_graph if task.status == "ready")
        blocked = tuple(task.task_id for task in revision.task_graph if task.status == "blocked")
        completed = tuple(task.task_id for task in revision.task_graph if task.status == "completed")
        eligible = bool(ready) and application.status in {"applied", "resume_pending", "resumed"}
        return ResumeEligibility(
            eligible=eligible,
            resume_from_task_ids=ready,
            blocked_dependents=blocked,
            previously_completed_tasks=completed,
            reasons=() if eligible else ("active revision must be applied before resume.",),
        )

    def _create_lease(self, task_id: str, revision: RuntimePlanRevision) -> ExecutionLease:
        lease_paths = next(
            (tuple(task.writable_paths) for task in revision.task_graph if task.task_id == task_id),
            tuple(),
        )
        lease = ExecutionLease(
            schema_version=1,
            lease_id=self.lease_id_factory(),
            task_id=task_id,
            execution_attempt_id=self.attempt_id_factory(),
            runtime_revision_id=revision.revision_id,
            runtime_revision_checksum=revision.revision_checksum,
            local_model="local-model",
            writable_paths=lease_paths,
            start_timestamp=self.now_factory(),
            lease_state="active",
        )
        save_execution_lease(self.project_path, lease)
        self._record_audit("lease_created", None, None, "resume_pending", "resume_pending", {"lease_id": lease.lease_id, "task_id": task_id})
        return lease

    def _load_request(self, request_id: str) -> CloudQueueRequest:
        return show_cloud_queue_request(self.project_path, request_id).request

    def _load_request_and_response(self, request_id: str) -> tuple[CloudQueueRequest, CloudQueueResponse]:
        request = self._load_request(request_id)
        response = load_imported_response(self.project_path, request_id)
        if response.request_id != request_id:
            raise ValueError("Imported response does not match the requested application.")
        return request, response

    def _load_approval_record_if_present(self, request: CloudQueueRequest) -> dict[str, Any] | None:
        approval_path = self.project_path / ".agentic" / "cloud_queue" / "approvals" / f"{request.request_id}.yaml"
        if not approval_path.exists():
            return None
        return load_approval_record(approval_path)

    def _load_story(self, story_name: str) -> dict[str, Any]:
        story_path = self.project_path / "stories" / story_name
        blueprint_story = load_blueprint_story(self.project_path, story_path)
        if blueprint_story is None:
            raise FileNotFoundError(f"Blueprint story was not found for application: {story_name}")
        return blueprint_story

    def _load_source_tasks(self, blueprint_story: dict[str, Any], request: CloudQueueRequest) -> list[TaskSnapshot]:
        raise RuntimeError("Blueprint reconstruction is disabled for runtime application.")

    def _build_proposed_tasks(
        self,
        request: CloudQueueRequest,
        response: CloudQueueResponse,
        source_task: TaskSnapshot,
        existing_tasks: list[TaskSnapshot],
    ) -> list[TaskSnapshot]:
        raise RuntimeError("Task reconstruction is handled by explicit operation planners.")

    def _response_writable_paths(self, response: CloudQueueResponse, request: CloudQueueRequest) -> list[str]:
        paths = response.claims.get("writable_paths", [])
        if isinstance(paths, list) and paths:
            return [str(item) for item in paths]
        return list(request.writable_paths)

    def _current_revision_id(self) -> str:
        pointer = self._load_pointer_if_present()
        if pointer is not None:
            return pointer.active_revision_id
        raise FileNotFoundError("Active runtime pointer is missing.")

    def _current_revision_checksum(self) -> str:
        pointer = self._load_pointer_if_present()
        if pointer is not None:
            return pointer.active_revision_checksum
        raise FileNotFoundError("Active runtime pointer is missing.")

    def _load_pointer_if_present(self) -> ActiveRevisionPointer | None:
        path = runtime_active_pointer_path(self.project_path)
        if not path.exists():
            return None
        return load_active_pointer(path)

    def _ensure_bootstrap_revision(self, source_tasks: list[TaskSnapshot]) -> None:
        pointer_path = runtime_active_pointer_path(self.project_path)
        revision_path = self.project_path / ".agentic" / "runtime_plans" / "revisions" / "runtime-plan-r0.yaml"
        if pointer_path.exists() and revision_path.exists():
            return
        bootstrap_revision = build_runtime_graph_revision(
            revision_id="runtime-plan-r0",
            parent_revision_id=None,
            application_id="bootstrap",
            created_at=self.now_factory(),
            tasks=source_tasks,
            requirement_mappings=[
                RequirementMapping(requirement_id=requirement, task_ids=(source_tasks[0].task_id,))
                for requirement in sorted({req for task in source_tasks for req in task.requirement_ids})
            ],
            dependency_changes=[],
            change_summary=("bootstrap runtime plan",),
            rollback_metadata=RollbackMetadata(
                prior_revision_id="",
                prior_revision_checksum="",
                rollback_reason="bootstrap",
                created_at=self.now_factory(),
                application_id="bootstrap",
            ),
            audit_event_ids=[],
        )
        save_runtime_revision(self.project_path, bootstrap_revision)
        save_active_pointer(
            self.project_path,
            ActiveRevisionPointer(
                schema_version=1,
                active_revision_id=bootstrap_revision.revision_id,
                active_revision_checksum=bootstrap_revision.revision_checksum,
                previous_revision_id=None,
                update_timestamp=self.now_factory(),
                application_id="bootstrap",
            ),
        )

    def _load_application_for_request(self, request_id: str) -> ApplicationRecord:
        applications_dir = application_root_path(self.project_path) / "applications"
        candidates: list[ApplicationRecord] = []
        for path in sorted(applications_dir.glob("*.yaml")):
            record = load_application_record(path)
            if record.request_id == request_id:
                candidates.append(record)
        if not candidates:
            raise FileNotFoundError(f"No application record exists for request: {request_id}")

        def preference(record: ApplicationRecord) -> tuple[int, str, str]:
            has_revision = 1 if record.revision_id else 0
            return (has_revision, record.created_at, record.application_id)

        return max(candidates, key=preference)

    def _load_revision(self, revision_id: str) -> RuntimePlanRevision:
        if not revision_id:
            raise FileNotFoundError("Revision ID is missing.")
        return load_runtime_revision(revision_path(self.project_path, revision_id))

    def _record_audit(
        self,
        event_type: str,
        application: ApplicationRecord | None,
        request: CloudQueueRequest | None,
        prior_state: str,
        new_state: str,
        details: dict[str, Any],
    ) -> str:
        if self.transaction_hooks.fail_on_audit_write:
            raise RuntimeError("Injected failure during audit write.")
        event = ApplicationAuditEvent(
            event_id=self.event_id_factory(),
            event_type=event_type,
            application_id=application.application_id if application else "",
            request_id=request.request_id if request else "",
            prior_state=prior_state,
            new_state=new_state,
            timestamp=self.now_factory(),
            details=details,
        )
        record_application_audit_event(self.project_path, event, event_id_factory=None)
        return event.event_id

    def _transition_application(
        self,
        application: ApplicationRecord,
        next_state: str,
        request: CloudQueueRequest | None,
        *,
        details: dict[str, Any],
    ) -> ApplicationRecord:
        from agentic_dev.cloud_application.state_machine import validate_application_transition

        validate_application_transition(application.status, next_state)
        updated = ApplicationRecord.from_dict(
            {
                **application.to_dict(),
                "status": next_state,
                "audit_event_ids": list(application.audit_event_ids),
                "notes": list(application.notes),
            },
        )
        save_application_record(self.project_path, updated)
        self._record_audit("transition", updated, request, application.status, next_state, details)
        return updated
