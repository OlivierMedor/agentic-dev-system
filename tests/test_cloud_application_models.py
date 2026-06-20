from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from agentic_dev.cloud_application.models import (
    ACTIVE_POINTER_SCHEMA_VERSION,
    APPLICATION_SCHEMA_VERSION,
    LEASE_SCHEMA_VERSION,
    REVISION_SCHEMA_VERSION,
    ActiveRevisionPointer,
    ApplicationOperation,
    ApplicationPlan,
    ApplicationRecord,
    ApplicationSafety,
    ApplicationSource,
    DependencyChange,
    ExecutionLease,
    RequirementMapping,
    RecoveryResult,
    ResumeEligibility,
    ResumeResult,
    RollbackMetadata,
    RuntimePlanRevision,
    TaskSnapshot,
)


def sample_task(task_id: str = "source") -> TaskSnapshot:
    return TaskSnapshot(
        task_id=task_id,
        title="Source task",
        role="developer",
        depends_on=(),
        requirement_ids=("AC-001", "AC-002"),
        required_context=("story.md",),
        writable_paths=("runtime/source/**",),
        expected_outputs=("reports/source.md",),
        validation_steps=("pytest -q",),
        token_estimate=1000,
        usable_input_tokens=2000,
        status="completed",
        source_task_id=None,
        superseded_by=(),
        history=("seed",),
    )


def sample_application_record() -> ApplicationRecord:
    return ApplicationRecord(
        schema_version=APPLICATION_SCHEMA_VERSION,
        application_id="cloud-application-0001",
        request_id="cloud-req-0001",
        request_checksum="sha256:request",
        response_checksum="sha256:response",
        approval_checksum=None,
        status="application_planned",
        created_at="2026-06-20T12:00:00Z",
        source=ApplicationSource(
            request_type="task_redecomposition",
            response_classification="validated_safe",
            source_task_id="source",
            source_plan_revision="runtime-plan-r0",
        ),
        application=ApplicationOperation(
            operation_type="replace_task_with_subtasks",
            affected_task_ids=("source",),
            proposed_task_ids=("child-a", "child-b"),
            preserved_requirement_ids=("AC-001", "AC-002"),
            dependency_changes=(DependencyChange(task_id="child-a"),),
            writable_paths=("runtime/app/parser/**", "runtime/app/validator/**"),
            expected_outputs=("reports/parser.md",),
            validation_steps=("pytest -q",),
        ),
        safety=ApplicationSafety(
            canonical_blueprint_modified=False,
            writable_paths_expanded=False,
            requirements_removed=False,
            external_services_added=False,
            network_access_added=False,
            deployment_added=False,
        ),
        resume=ResumeEligibility(
            eligible=False,
            resume_from_task_ids=(),
            blocked_dependents=(),
            previously_completed_tasks=("source",),
        ),
        plan_checksum="sha256:plan",
        revision_id=None,
        revision_checksum=None,
        active_revision_id=None,
        rollback_available=False,
        notes=("note",),
        audit_event_ids=("audit-1",),
    )


def sample_plan() -> ApplicationPlan:
    source = sample_task()
    proposed = (
        TaskSnapshot(
            task_id="child-a",
            title="Child A",
            role="developer",
            depends_on=(),
            requirement_ids=("AC-001",),
            required_context=("story.md",),
            writable_paths=("runtime/app/parser/**",),
            expected_outputs=("reports/parser.md",),
            validation_steps=("pytest -q",),
            token_estimate=500,
            usable_input_tokens=2000,
            status="ready",
            source_task_id=source.task_id,
            superseded_by=(),
            history=(source.task_id,),
        ),
    )
    return ApplicationPlan(
        schema_version=APPLICATION_SCHEMA_VERSION,
        application_id="cloud-application-0001",
        request_id="cloud-req-0001",
        request_checksum="sha256:request",
        response_checksum="sha256:response",
        approval_checksum=None,
        source_revision_id="runtime-plan-r0",
        source_revision_checksum="sha256:r0",
        proposed_revision_id="runtime-plan-r1",
        operation_type="replace_task_with_subtasks",
        source_task_snapshot=source,
        proposed_tasks=proposed,
        requirement_mapping=(RequirementMapping(requirement_id="AC-001", task_ids=("child-a",)),),
        dependency_changes=(DependencyChange(task_id="child-a"),),
        writable_path_diff=("runtime/app/parser/**",),
        context_budget_validation={"usable_input_tokens": 2000},
        expected_outputs=("reports/parser.md",),
        validation_steps=("pytest -q",),
        affected_completed_tasks=("source",),
        affected_pending_tasks=(),
        resume_candidates=("child-a",),
        rollback_target="runtime-plan-r0",
        preconditions=("validated_safe",),
        predicted_side_effects=("supersede source task",),
        plan_checksum="sha256:plan",
        created_at="2026-06-20T12:00:00Z",
        dry_run=True,
    )


def test_application_record_round_trip_and_immutability() -> None:
    record = sample_application_record()
    loaded = ApplicationRecord.from_dict(record.to_dict())

    assert loaded == record
    with pytest.raises(FrozenInstanceError):
        record.status = "applied"  # type: ignore[misc]


def test_application_plan_round_trip_and_immutability() -> None:
    plan = sample_plan()
    loaded = ApplicationPlan.from_dict(plan.to_dict())

    assert loaded.application_id == plan.application_id
    assert loaded.proposed_revision_id == "runtime-plan-r1"
    with pytest.raises(FrozenInstanceError):
        plan.plan_checksum = "changed"  # type: ignore[misc]


def test_runtime_revision_round_trip() -> None:
    revision = RuntimePlanRevision(
        schema_version=REVISION_SCHEMA_VERSION,
        revision_id="runtime-plan-r1",
        parent_revision_id="runtime-plan-r0",
        application_id="cloud-application-0001",
        created_at="2026-06-20T12:00:00Z",
        task_graph=(sample_task(),),
        task_statuses={"source": "completed"},
        requirement_mappings=(RequirementMapping(requirement_id="AC-001", task_ids=("source",)),),
        dependency_mappings=(DependencyChange(task_id="source"),),
        graph_checksum="sha256:graph",
        revision_checksum="sha256:revision",
        change_summary=("bootstrap",),
        rollback_metadata=RollbackMetadata(
            prior_revision_id="runtime-plan-r0",
            prior_revision_checksum="sha256:r0",
            rollback_reason="test",
            created_at="2026-06-20T12:00:00Z",
            application_id="cloud-application-0001",
        ),
        audit_event_ids=("audit-1",),
    )

    assert RuntimePlanRevision.from_dict(revision.to_dict()) == revision


def test_active_pointer_lease_and_resume_models_round_trip() -> None:
    pointer = ActiveRevisionPointer(
        schema_version=ACTIVE_POINTER_SCHEMA_VERSION,
        active_revision_id="runtime-plan-r1",
        active_revision_checksum="sha256:revision",
        previous_revision_id="runtime-plan-r0",
        update_timestamp="2026-06-20T12:00:00Z",
        application_id="cloud-application-0001",
    )
    lease = ExecutionLease(
        schema_version=LEASE_SCHEMA_VERSION,
        lease_id="lease-0001",
        task_id="child-a",
        execution_attempt_id="attempt-0001",
        runtime_revision_id="runtime-plan-r1",
        runtime_revision_checksum="sha256:revision",
        local_model="gemma",
        writable_paths=("runtime/app/parser/**",),
        start_timestamp="2026-06-20T12:00:00Z",
    )
    resume = ResumeResult(
        project_path=Path("/tmp/project"),
        application_id="cloud-application-0001",
        revision_id="runtime-plan-r1",
        revision_checksum="sha256:revision",
        task_ids=("child-a",),
        lease_ids=("lease-0001",),
        status="resumed",
    )
    recovery = RecoveryResult(
        project_path=Path("/tmp/project"),
        findings=("missing active pointer",),
        recommended_actions=("inspect pointer",),
        reconciled=False,
        active_pointer=pointer,
    )

    assert ActiveRevisionPointer.from_dict(pointer.to_dict()) == pointer
    assert ExecutionLease.from_dict(lease.to_dict()) == lease
    assert resume.status == "resumed"
    assert recovery.reconciled is False

