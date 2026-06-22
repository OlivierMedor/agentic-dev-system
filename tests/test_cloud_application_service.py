from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from agentic_dev.cloud_application import build_default_application_service
from agentic_dev.cloud_application.models import ExecutionLease, TaskPublicationRecord, TransactionRecord
from agentic_dev.cloud_application.graph import build_runtime_graph_revision
from agentic_dev.cloud_application.models import (
    ActiveRevisionPointer,
    ApplicationOperation,
    ApplicationRecord,
    ApplicationSafety,
    ApplicationSource,
    ApplicationPlan,
    DependencyChange,
    RequirementMapping,
    ResumeEligibility,
    RollbackMetadata,
    RuntimePlanRevision,
    TaskSnapshot,
)
from agentic_dev.cloud_application.publication import checksum_bytes, validate_publication_gate
from agentic_dev.cloud_application.persistence import (
    active_pointer_path,
    load_active_pointer,
    load_execution_leases,
    load_runtime_revision,
    load_task_publication_records,
    revision_path,
    save_active_pointer,
    save_execution_lease,
    save_runtime_revision,
    save_task_publication_record,
    transaction_path,
    load_transaction_record,
)
from agentic_dev.cloud_queue import (
    approve_cloud_queue_request,
    cloud_queue_status,
    create_cloud_queue_request,
    export_cloud_queue_request,
    import_cloud_queue_response,
    show_cloud_queue_request,
)


STORY = "safe-cloud-response-application-and-local-resume"


def create_story(project_path: Path) -> Path:
    story_path = project_path / "stories" / STORY
    (story_path / "instructions").mkdir(parents=True, exist_ok=True)
    (story_path / "reports").mkdir(parents=True, exist_ok=True)
    (story_path / "story.md").write_text("# Story 064\n", encoding="utf-8")
    (story_path / "status.yaml").write_text(
        yaml.safe_dump({"story_id": "story_064", "slug": STORY, "status": "prepared"}, sort_keys=False),
        encoding="utf-8",
    )
    (project_path / "blueprints").mkdir(parents=True, exist_ok=True)
    (project_path / "blueprints" / "blueprint.yaml").write_text(
        yaml.safe_dump(
            {
                "stories": [
                    {
                        "id": "STORY-064",
                        "story_id": "story_064",
                        "slug": STORY,
                        "title": "Story 064 - Safe Cloud Response Application and Local Execution Resume",
                        "goal": "Apply safe cloud responses to runtime execution.",
                        "acceptance_criteria": [
                            "AC-001: Validated or approved cloud responses can be applied safely.",
                            "AC-002: Runtime revisions remain immutable and revision-bound.",
                        ],
                        "subtasks": [
                            {
                                "id": "source",
                                "title": "Source task",
                                "role": "developer",
                                "depends_on": [],
                                "requirement_ids": ["AC-001", "AC-002"],
                                "required_context": {
                                    "files": ["stories/safe-cloud-response-application-and-local-resume/story.md"],
                                    "summaries": ["Bootstrap runtime revision."],
                                    "prior_task_outputs": [],
                                    "architecture_decisions": [],
                                },
                                "writable_paths": ["runtime/source/**"],
                                "expected_outputs": ["reports/source.md"],
                                "validation": ["pytest -q"],
                                "context_budget": {
                                    "max_input_tokens": 6000,
                                    "reserved_output_tokens": 1000,
                                    "required_context_must_fit": True,
                                    "allow_required_context_trimming": False,
                                    "oversized_task_policy": "reject_for_cloud_redecomposition",
                                },
                            },
                            {
                                "id": "audit",
                                "title": "Audit task",
                                "role": "test",
                                "depends_on": ["source"],
                                "requirement_ids": ["AC-001", "AC-002"],
                                "required_context": {
                                    "files": ["stories/safe-cloud-response-application-and-local-resume/story.md"],
                                    "summaries": ["Validate the source task output."],
                                    "prior_task_outputs": ["source"],
                                    "architecture_decisions": [],
                                },
                                "writable_paths": ["runtime/review/**"],
                                "expected_outputs": ["reports/audit.md"],
                                "validation": ["pytest -q"],
                                "context_budget": {
                                    "max_input_tokens": 6000,
                                    "reserved_output_tokens": 1000,
                                    "required_context_must_fit": True,
                                    "allow_required_context_trimming": False,
                                    "oversized_task_policy": "reject_for_cloud_redecomposition",
                                },
                            },
                        ],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return story_path


def bootstrap_runtime_state(project_path: Path) -> None:
    source = TaskSnapshot(
        task_id="source",
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
        status="blocked",
        source_task_id=None,
        history=("bootstrap",),
    )
    audit = TaskSnapshot(
        task_id="audit",
        title="Audit task",
        role="test",
        depends_on=("source",),
        requirement_ids=("AC-001", "AC-002"),
        required_context=("story.md",),
        writable_paths=("runtime/review/**",),
        expected_outputs=("reports/audit.md",),
        validation_steps=("pytest -q",),
        token_estimate=1000,
        usable_input_tokens=2000,
        status="ready",
        source_task_id="source",
        history=("source",),
    )
    revision = build_runtime_graph_revision(
        revision_id="runtime-plan-r0",
        parent_revision_id=None,
        application_id="bootstrap",
        created_at="2026-06-20T12:00:00Z",
        tasks=[source, audit],
        requirement_mappings=[
            RequirementMapping(requirement_id="AC-001", task_ids=("source", "audit")),
            RequirementMapping(requirement_id="AC-002", task_ids=("source", "audit")),
        ],
        dependency_changes=[DependencyChange(task_id="audit", prior_dependencies=(), new_dependencies=("source",), summary="bootstrap")],
        change_summary=["bootstrap runtime plan"],
        rollback_metadata=RollbackMetadata(
            prior_revision_id="",
            prior_revision_checksum="",
            rollback_reason="bootstrap",
            created_at="2026-06-20T12:00:00Z",
            application_id="bootstrap",
        ),
        audit_event_ids=("audit-1",),
    )
    save_runtime_revision(project_path, revision)
    save_active_pointer(
        project_path,
        ActiveRevisionPointer(
            schema_version=1,
            active_revision_id=revision.revision_id,
            active_revision_checksum=revision.revision_checksum,
            previous_revision_id=None,
            update_timestamp="2026-06-20T12:00:00Z",
            application_id="bootstrap",
        ),
    )


def bootstrap_runtime_state_with_mixed_tasks(project_path: Path) -> RuntimePlanRevision:
    source = TaskSnapshot(
        task_id="source",
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
        status="blocked",
        source_task_id=None,
        history=("bootstrap",),
    )
    completed = TaskSnapshot(
        task_id="done",
        title="Completed task",
        role="developer",
        depends_on=(),
        requirement_ids=("AC-001",),
        required_context=("story.md",),
        writable_paths=("runtime/done/**",),
        expected_outputs=("reports/done.md",),
        validation_steps=("pytest -q",),
        token_estimate=1000,
        usable_input_tokens=2000,
        status="completed",
        source_task_id=None,
        history=("bootstrap",),
    )
    ready = TaskSnapshot(
        task_id="ready",
        title="Ready task",
        role="developer",
        depends_on=(),
        requirement_ids=("AC-002",),
        required_context=("story.md",),
        writable_paths=("runtime/ready/**",),
        expected_outputs=("reports/ready.md",),
        validation_steps=("pytest -q",),
        token_estimate=1000,
        usable_input_tokens=2000,
        status="ready",
        source_task_id=None,
        history=("bootstrap",),
    )
    blocked = TaskSnapshot(
        task_id="blocked",
        title="Blocked task",
        role="test",
        depends_on=("ready",),
        requirement_ids=("AC-002",),
        required_context=("story.md",),
        writable_paths=("runtime/blocked/**",),
        expected_outputs=("reports/blocked.md",),
        validation_steps=("pytest -q",),
        token_estimate=1000,
        usable_input_tokens=2000,
        status="blocked",
        source_task_id=None,
        history=("ready",),
    )
    revision = build_runtime_graph_revision(
        revision_id="runtime-plan-r0",
        parent_revision_id=None,
        application_id="bootstrap",
        created_at="2026-06-20T12:00:00Z",
        tasks=[source, completed, ready, blocked],
        requirement_mappings=[
            RequirementMapping(requirement_id="AC-001", task_ids=("source", "done")),
            RequirementMapping(requirement_id="AC-002", task_ids=("source", "ready", "blocked")),
        ],
        dependency_changes=[DependencyChange(task_id="blocked", prior_dependencies=(), new_dependencies=("ready",), summary="bootstrap")],
        change_summary=["bootstrap runtime plan"],
        rollback_metadata=RollbackMetadata(
            prior_revision_id="",
            prior_revision_checksum="",
            rollback_reason="bootstrap",
            created_at="2026-06-20T12:00:00Z",
            application_id="bootstrap",
        ),
        audit_event_ids=("audit-1",),
    )
    save_runtime_revision(project_path, revision)
    save_active_pointer(
        project_path,
        ActiveRevisionPointer(
            schema_version=1,
            active_revision_id=revision.revision_id,
            active_revision_checksum=revision.revision_checksum,
            previous_revision_id=None,
            update_timestamp="2026-06-20T12:00:00Z",
            application_id="bootstrap",
        ),
    )
    return revision


def snapshot_application_roots(project_path: Path) -> dict[str, str]:
    roots = [
        project_path / ".agentic" / "cloud_queue",
        project_path / ".agentic" / "cloud_applications",
        project_path / ".agentic" / "runtime_plans",
    ]
    snapshot: dict[str, str] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            rel_path = str(path.relative_to(project_path))
            if path.is_dir():
                snapshot[f"{rel_path}/"] = "DIR"
            else:
                snapshot[rel_path] = sha256(path.read_bytes()).hexdigest()
    return snapshot


def response_payload(request_id: str, batch_id: str, decision: str) -> dict[str, object]:
    proposed_tasks = [
        {
            "task_id": "child-a",
            "title": "Parser task",
            "role": "developer",
            "depends_on": [],
            "requirement_ids": ["AC-001"],
            "required_context": ["story.md"],
            "writable_paths": ["runtime/app/parser/**"],
            "expected_outputs": ["reports/parser.md"],
            "validation_steps": ["pytest -q"],
            "token_estimate": 500,
            "usable_input_tokens": 2000,
            "status": "ready",
        },
        {
            "task_id": "child-b",
            "title": "Validator task",
            "role": "test",
            "depends_on": ["child-a"],
            "requirement_ids": ["AC-002"],
            "required_context": ["story.md"],
            "writable_paths": ["runtime/app/validator/**"],
            "expected_outputs": ["reports/validator.md"],
            "validation_steps": ["pytest -q"],
            "token_estimate": 500,
            "usable_input_tokens": 2000,
            "status": "ready",
        },
    ]
    return {
        "response_id": f"{request_id}-response",
        "request_id": request_id,
        "batch_id": batch_id,
        "response_schema_version": 1,
        "normalized_response": {"summary": "normalized"},
        "raw_response": "raw",
        "checksum": "checksum",
        "decision": decision,
        "claims": {
            "operation_type": "replace_task_with_subtasks",
            "source_task_id": "source",
            "source_plan_revision": "runtime-plan-r0",
            "applicable_requirements": ["AC-001", "AC-002"],
            "writable_paths": ["runtime/app/parser/**", "runtime/app/validator/**"],
            "scope_changes": [],
            "dependency_status": "resolved",
            "resolved_dependencies": [],
            "safe_to_apply": True,
            "proposed_tasks": proposed_tasks,
            "expected_outputs": ["reports/parser.md", "reports/validator.md"],
            "validation_steps": ["pytest -q"],
        },
        "adapter": "manual_packet",
    }


def prepare_validated_safe_request(project_path: Path) -> tuple[str, Path]:
    create_story(project_path)
    bootstrap_runtime_state(project_path)
    request = create_cloud_queue_request(
        project_path,
        story=STORY,
        title="Application target",
        details="details",
        requirements=["AC-001", "AC-002"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
        source_task_id="source",
        source_plan_revision="runtime-plan-r0",
        request_id_factory=lambda: "CQ-20260620-0001",
        batch_id_factory=lambda: "batch-1",
    )
    export_cloud_queue_request(project_path, request_id=request.request.request_id)
    response_path = project_path / "response.yaml"
    response_path.write_text(
        yaml.safe_dump(response_payload(request.request.request_id, request.request.batch_id, "SAFE"), sort_keys=False),
        encoding="utf-8",
    )
    import_cloud_queue_response(project_path, response_path)
    return request.request.request_id, response_path


def patch_runtime_execution(monkeypatch: pytest.MonkeyPatch, project_path: Path) -> None:
    state_path = project_path / ".agentic" / "cloud_applications" / "execution_state.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    story_path = project_path / "stories" / STORY

    def fake_runtime_execution(*args: object, **kwargs: object) -> SimpleNamespace:
        revision = args[2]
        task_ids = tuple(kwargs.get("resume_task_ids") or [task.task_id for task in revision.task_graph if task.status == "ready"])
        tasks: dict[str, dict[str, object]] = {}
        for task in revision.task_graph:
            status = "completed" if task.task_id in task_ids else task.status
            tasks[task.task_id] = {
                "task_id": task.task_id,
                "title": task.title,
                "role": task.role,
                "dependencies": list(task.depends_on),
                "status": status,
                "attempt": 1,
                "outputs": [],
                "handoff_summary": {
                    "available_to_dependents": [],
                    "decisions": [f"{task.task_id} done"] if status == "completed" else [],
                    "outputs": [],
                },
                "validation_result": {
                    "status": "passed" if status == "completed" else "pending",
                    "checks": list(task.validation_steps),
                },
            }
        state = {
            "story": STORY,
            "status": "completed",
            "current_task": None,
            "completed_tasks": list(task_ids),
            "blocked_tasks": [task.task_id for task in revision.task_graph if task.status == "blocked"],
            "cloud_redecomposition_required_tasks": [],
            "execution_order": [task.task_id for task in revision.task_graph],
            "tasks": tasks,
            "final_validation": {
                "status": "passed",
                "requirements_checked": [],
                "missing_requirements": [],
            },
        }
        state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")
        for task_id in task_ids:
            task_dir = story_path / "reports" / "local_execution" / "tasks" / task_id
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "execution.yaml").write_text(
                yaml.safe_dump(tasks[task_id], sort_keys=False),
                encoding="utf-8",
            )
        return SimpleNamespace(
            result=SimpleNamespace(status="completed", state_path=state_path, story_path=story_path),
        )

    monkeypatch.setattr("agentic_dev.cloud_application.service.run_runtime_revision_execution", fake_runtime_execution)


def test_plan_apply_binds_to_requested_runtime_task_id(tmp_path: Path) -> None:
    create_story(tmp_path)
    bootstrap_runtime_state(tmp_path)
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Application target",
        details="details",
        requirements=["AC-001", "AC-002"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
        source_task_id="audit",
        source_plan_revision="runtime-plan-r0",
        request_id_factory=lambda: "CQ-20260620-0100",
        batch_id_factory=lambda: "batch-1",
    )
    export_cloud_queue_request(tmp_path, request_id=request.request.request_id)
    response_path = tmp_path / "response.yaml"
    response_path.write_text(
        yaml.safe_dump(
            {
                **response_payload(request.request.request_id, request.request.batch_id, "SAFE"),
                "claims": {
                    **response_payload(request.request.request_id, request.request.batch_id, "SAFE")["claims"],
                    "source_task_id": "audit",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    import_cloud_queue_response(tmp_path, response_path)
    service = build_default_application_service(tmp_path)

    result = service.plan_apply(request.request.request_id, dry_run=True)

    assert result.plan.source_task_snapshot.task_id == "audit"


def test_replace_task_requires_explicit_children(tmp_path: Path) -> None:
    create_story(tmp_path)
    bootstrap_runtime_state(tmp_path)
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Application target",
        details="details",
        requirements=["AC-001", "AC-002"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
        source_task_id="source",
        source_plan_revision="runtime-plan-r0",
        request_id_factory=lambda: "CQ-20260620-0101",
        batch_id_factory=lambda: "batch-1",
    )
    export_cloud_queue_request(tmp_path, request_id=request.request.request_id)
    response_path = tmp_path / "response.yaml"
    response_path.write_text(
        yaml.safe_dump(
            {
                **response_payload(request.request.request_id, request.request.batch_id, "SAFE"),
                "claims": {
                    **response_payload(request.request.request_id, request.request.batch_id, "SAFE")["claims"],
                    "proposed_tasks": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    import_cloud_queue_response(tmp_path, response_path)
    service = build_default_application_service(tmp_path)

    with pytest.raises(ValueError, match="explicit proposed_tasks"):
        service.plan_apply(request.request.request_id, dry_run=True)


@pytest.mark.parametrize(
    "operation_type",
    [
        "add_architecture_overlay",
        "add_remediation_tasks",
        "record_final_cloud_review",
    ],
)
def test_plan_apply_rejects_unsupported_operation_types(tmp_path: Path, operation_type: str) -> None:
    request_id, _ = prepare_validated_safe_request(tmp_path)
    response_path = tmp_path / "response.yaml"
    payload = response_payload(request_id, "batch-1", "SAFE")
    payload["claims"] = {**payload["claims"], "operation_type": operation_type}
    response_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    import_cloud_queue_response(tmp_path, response_path)
    service = build_default_application_service(tmp_path)

    with pytest.raises(ValueError, match="Unsupported application operation"):
        service.plan_apply(request_id, dry_run=True)


def test_update_task_metadata_operation_builds_revision(tmp_path: Path) -> None:
    create_story(tmp_path)
    bootstrap_runtime_state(tmp_path)
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Metadata update target",
        details="details",
        requirements=["AC-001", "AC-002"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
        source_task_id="source",
        source_plan_revision="runtime-plan-r0",
        request_id_factory=lambda: "CQ-20260620-0102",
        batch_id_factory=lambda: "batch-1",
    )
    export_cloud_queue_request(tmp_path, request_id=request.request.request_id)
    response_path = tmp_path / "response.yaml"
    payload = response_payload(request.request.request_id, request.request.batch_id, "SAFE")
    payload["claims"] = {
        **payload["claims"],
        "operation_type": "update_task_metadata",
        "task_metadata": {
            "title": "Updated source task",
            "role": "developer",
            "required_context": ["story.md", "reports/source.md"],
            "writable_paths": ["runtime/app/parser/**"],
            "expected_outputs": ["reports/source.md"],
            "validation_steps": ["pytest -q", "ruff check ."],
            "token_estimate": 1200,
            "usable_input_tokens": 2400,
        },
    }
    response_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    import_cloud_queue_response(tmp_path, response_path)
    service = build_default_application_service(tmp_path)

    result = service.plan_apply(request.request.request_id, dry_run=True)

    assert result.plan.operation_type == "update_task_metadata"
    assert tuple(task.task_id for task in result.plan.proposed_tasks) == ("source",)
    assert result.plan.source_task_snapshot.title == "Source task"


def test_dry_run_creates_plan_without_pointer_change(tmp_path: Path) -> None:
    request_id, _ = prepare_validated_safe_request(tmp_path)
    service = build_default_application_service(tmp_path)
    before = snapshot_application_roots(tmp_path)
    pointer_before = active_pointer_path(tmp_path).read_text(encoding="utf-8")

    result = service.plan_apply(request_id, dry_run=True)

    assert result.dry_run is True
    assert result.application.status == "application_planned"
    assert result.plan.plan_checksum
    assert result.revision_path is None
    assert active_pointer_path(tmp_path).read_text(encoding="utf-8") == pointer_before
    assert snapshot_application_roots(tmp_path) == before


def test_apply_resume_and_rollback_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request_id, _ = prepare_validated_safe_request(tmp_path)
    service = build_default_application_service(tmp_path)
    patch_runtime_execution(monkeypatch, tmp_path)

    applied = service.plan_apply(request_id, dry_run=False)
    request_path = show_cloud_queue_request(tmp_path, request_id).request
    assert applied.application.status in {"applied", "resume_pending"}
    assert active_pointer_path(tmp_path).exists()
    assert revision_path(tmp_path, applied.application.revision_id or "").exists()
    assert cloud_queue_status(tmp_path).counts_by_state["validated_safe"] == 1
    assert request_path.state == "validated_safe"

    resume = service.resume(request_id)
    assert resume.status == "resumed"
    assert len(resume.lease_ids) == 2

    rolled_back = service.rollback(applied.application.application_id)
    assert rolled_back.status == "rolled_back"
    pointer = yaml.safe_load(active_pointer_path(tmp_path).read_text(encoding="utf-8"))
    assert pointer["active_revision_id"] == "runtime-plan-r0"


def test_approval_required_application_uses_checksum_locked_approval(tmp_path: Path) -> None:
    create_story(tmp_path)
    bootstrap_runtime_state(tmp_path)
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Approval target",
        details="details",
        requirements=["AC-001", "AC-002"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
        source_task_id="source",
        source_plan_revision="runtime-plan-r0",
        request_id_factory=lambda: "CQ-APPROVAL-1",
        batch_id_factory=lambda: "batch-2",
    )
    export_cloud_queue_request(tmp_path, request_id=request.request.request_id)
    response_path = tmp_path / "approval.yaml"
    response_path.write_text(
        yaml.safe_dump(
            {
                **response_payload(request.request.request_id, request.request.batch_id, "APPROVAL_REQUIRED"),
                "claims": {
                    **response_payload(request.request.request_id, request.request.batch_id, "APPROVAL_REQUIRED")["claims"],
                    "scope_changes": ["docs"],
                    "safe_to_apply": False,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    import_cloud_queue_response(tmp_path, response_path)
    approved_request = show_cloud_queue_request(tmp_path, request.request.request_id).request
    approve_cloud_queue_request(
        tmp_path,
        request.request.request_id,
        normalized_response_checksum_value=approved_request.approval_checksum,
        operator_note="approved",
    )

    service = build_default_application_service(tmp_path)
    result = service.plan_apply(request.request.request_id, dry_run=True)

    assert result.application.status == "application_planned"
    assert result.application.approval_checksum == approved_request.approval_checksum


def test_failure_injection_leaves_bootstrap_revision_active(tmp_path: Path) -> None:
    request_id, _ = prepare_validated_safe_request(tmp_path)
    service = build_default_application_service(tmp_path)
    service.transaction_hooks = service.transaction_hooks.__class__(fail_on_publish=True)  # type: ignore[attr-defined]

    with pytest.raises(RuntimeError, match="Injected failure during revision publish"):
        service.plan_apply(request_id, dry_run=False)

    assert active_pointer_path(tmp_path).exists()


def test_resume_invokes_runtime_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request_id, _ = prepare_validated_safe_request(tmp_path)
    service = build_default_application_service(tmp_path)
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_runtime_execution(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append((args, kwargs))
        state_path = tmp_path / ".agentic" / "cloud_applications" / "execution_state.yaml"
        state_path.write_text("status: completed\n", encoding="utf-8")
        return SimpleNamespace(
            result=SimpleNamespace(status="completed", state_path=state_path, story_path=tmp_path / "stories" / STORY),
        )

    monkeypatch.setattr("agentic_dev.cloud_application.service.run_runtime_revision_execution", fake_runtime_execution)

    service.plan_apply(request_id, dry_run=False)
    service.resume(request_id)

    assert calls


def test_publication_gate_rejects_stale_worker_result(tmp_path: Path) -> None:
    create_story(tmp_path)
    revision = build_runtime_graph_revision(
        revision_id="runtime-plan-r1",
        parent_revision_id="runtime-plan-r0",
        application_id="cloud-application-1",
        created_at="2026-06-20T12:00:00Z",
        tasks=[
            TaskSnapshot(
                task_id="task-a",
                title="Task A",
                role="developer",
                depends_on=(),
                requirement_ids=("AC-001",),
                required_context=(),
                writable_paths=("results/**",),
                expected_outputs=("reports/a.md",),
                validation_steps=("pytest -q",),
                token_estimate=1,
                usable_input_tokens=2,
                status="ready",
                history=("bootstrap",),
            ),
        ],
        requirement_mappings=[RequirementMapping(requirement_id="AC-001", task_ids=("task-a",))],
        dependency_changes=[],
        change_summary=["test"],
        rollback_metadata=RollbackMetadata(
            prior_revision_id="runtime-plan-r0",
            prior_revision_checksum="sha256:r0",
            rollback_reason="test",
            created_at="2026-06-20T12:00:00Z",
            application_id="cloud-application-1",
        ),
        audit_event_ids=("audit-1",),
    )
    save_runtime_revision(tmp_path, revision)
    save_active_pointer(
        tmp_path,
        ActiveRevisionPointer(
            schema_version=1,
            active_revision_id=revision.revision_id,
            active_revision_checksum=revision.revision_checksum,
            previous_revision_id="runtime-plan-r0",
            update_timestamp="2026-06-20T12:00:00Z",
            application_id="cloud-application-1",
        ),
    )
    lease = ExecutionLease(
        schema_version=1,
        lease_id="lease-1",
        task_id="task-a",
        execution_attempt_id="attempt-1",
        runtime_revision_id=revision.revision_id,
        runtime_revision_checksum=revision.revision_checksum,
        local_model="local",
        writable_paths=("results/**", "stories/safe-cloud-response-application-and-local-resume/reports/local_execution/tasks/task-a/**"),
        start_timestamp="2026-06-20T12:00:00Z",
    )
    save_execution_lease(tmp_path, lease)
    lease_file = tmp_path / ".agentic" / "execution_leases" / "lease-1.yaml"
    stale_pointer = ActiveRevisionPointer(
        schema_version=1,
        active_revision_id="runtime-plan-r999",
        active_revision_checksum="sha256:stale",
        previous_revision_id=lease.runtime_revision_id,
        update_timestamp="2026-06-20T12:00:00Z",
        application_id="bootstrap",
    )
    result_bytes = b"result: stale\n"
    task = revision.task_graph[0]
    publication = TaskPublicationRecord(
        schema_version=1,
        task_id=lease.task_id,
        lease_id=lease.lease_id,
        execution_attempt_id=lease.execution_attempt_id,
        revision_id=lease.runtime_revision_id,
        revision_checksum=lease.runtime_revision_checksum,
        result_artifact_path=str(lease_file.relative_to(tmp_path)),
        result_checksum=checksum_bytes(result_bytes),
        validation_status="passed",
        publication_timestamp="2026-06-20T12:00:00Z",
    )

    with pytest.raises(ValueError, match="Publication revision does not match the active revision"):
        validate_publication_gate(
            tmp_path,
            publication=publication,
            lease=lease,
            active_pointer=stale_pointer,
            revision=revision,
            task=task,
            result_path=lease_file,
            result_bytes=result_bytes,
        )


def test_graph_preservation_and_rollback_restore_full_revision(tmp_path: Path) -> None:
    create_story(tmp_path)
    bootstrap_runtime_state_with_mixed_tasks(tmp_path)
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Application target",
        details="details",
        requirements=["AC-001", "AC-002"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
        source_task_id="source",
        source_plan_revision="runtime-plan-r0",
        request_id_factory=lambda: "CQ-20260620-0200",
        batch_id_factory=lambda: "batch-1",
    )
    export_cloud_queue_request(tmp_path, request_id=request.request.request_id)
    response_path = tmp_path / "response.yaml"
    response_path.write_text(
        yaml.safe_dump(response_payload(request.request.request_id, request.request.batch_id, "SAFE"), sort_keys=False),
        encoding="utf-8",
    )
    import_cloud_queue_response(tmp_path, response_path)
    service = build_default_application_service(tmp_path)

    original_revision = load_runtime_revision(revision_path(tmp_path, "runtime-plan-r0"))
    applied = service.plan_apply(request.request.request_id, dry_run=False)
    revised_revision = load_runtime_revision(revision_path(tmp_path, applied.application.revision_id or ""))

    revised_by_id = {task.task_id: task for task in revised_revision.task_graph}
    assert tuple(revised_by_id) == ("source", "child-a", "child-b", "done", "ready", "blocked")
    assert revised_by_id["source"].status == "superseded"
    assert revised_by_id["done"].status == "completed"
    assert revised_by_id["ready"].status == "ready"
    assert revised_by_id["blocked"].status == "blocked"
    assert revised_by_id["done"].to_dict() == original_revision.task_graph[1].to_dict()
    assert revised_by_id["ready"].to_dict() == original_revision.task_graph[2].to_dict()
    assert revised_by_id["blocked"].to_dict() == original_revision.task_graph[3].to_dict()
    assert revised_by_id["child-a"].depends_on == ()
    assert revised_by_id["child-b"].depends_on == ("child-a",)
    assert revised_by_id["source"].superseded_by == ("child-b",)

    transaction = load_transaction_record(transaction_path(tmp_path, f"txn-{applied.application.application_id}"))
    assert transaction.proposed_revision_checksum == revised_revision.revision_checksum

    rolled_back = service.rollback(applied.application.application_id)
    rolled_back_revision = load_runtime_revision(revision_path(tmp_path, rolled_back.revision_id or ""))
    assert [task.to_dict() for task in rolled_back_revision.task_graph] == [task.to_dict() for task in original_revision.task_graph]


def test_resume_schedules_only_ready_tasks_and_publishes_per_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story(tmp_path)
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Resume target",
        details="details",
        requirements=["AC-001", "AC-002"],
        writable_paths=["runtime/ready-a/**", "runtime/ready-b/**"],
        source_task_id="source",
        source_plan_revision="runtime-plan-r0",
        request_id_factory=lambda: "CQ-20260620-0300",
        batch_id_factory=lambda: "batch-1",
    )
    export_cloud_queue_request(tmp_path, request_id=request.request.request_id)
    revision = build_runtime_graph_revision(
        revision_id="runtime-plan-r1",
        parent_revision_id="runtime-plan-r0",
        application_id="cloud-application-resume-1",
        created_at="2026-06-20T12:00:00Z",
        tasks=[
            TaskSnapshot(
                task_id="completed",
                title="Completed",
                role="developer",
                depends_on=(),
                requirement_ids=("AC-001",),
                required_context=("story.md",),
                writable_paths=("runtime/completed/**",),
                expected_outputs=("reports/completed.md",),
                validation_steps=("pytest -q",),
                token_estimate=1000,
                usable_input_tokens=2000,
                status="completed",
                history=("bootstrap",),
            ),
            TaskSnapshot(
                task_id="superseded",
                title="Superseded",
                role="developer",
                depends_on=(),
                requirement_ids=("AC-001",),
                required_context=("story.md",),
                writable_paths=("runtime/superseded/**",),
                expected_outputs=("reports/superseded.md",),
                validation_steps=("pytest -q",),
                token_estimate=1000,
                usable_input_tokens=2000,
                status="superseded",
                history=("bootstrap",),
                superseded_by=("ready-a",),
            ),
            TaskSnapshot(
                task_id="blocked",
                title="Blocked",
                role="developer",
                depends_on=("ready-a",),
                requirement_ids=("AC-002",),
                required_context=("story.md",),
                writable_paths=("runtime/blocked/**",),
                expected_outputs=("reports/blocked.md",),
                validation_steps=("pytest -q",),
                token_estimate=1000,
                usable_input_tokens=2000,
                status="blocked",
                history=("bootstrap",),
            ),
            TaskSnapshot(
                task_id="ready-a",
                title="Ready A",
                role="developer",
                depends_on=(),
                requirement_ids=("AC-002",),
                required_context=("story.md",),
                writable_paths=("runtime/ready-a/**",),
                expected_outputs=("reports/ready-a.md",),
                validation_steps=("pytest -q",),
                token_estimate=1000,
                usable_input_tokens=2000,
                status="ready",
                history=("bootstrap",),
            ),
            TaskSnapshot(
                task_id="ready-b",
                title="Ready B",
                role="test",
                depends_on=("ready-a",),
                requirement_ids=("AC-002",),
                required_context=("story.md",),
                writable_paths=("runtime/ready-b/**",),
                expected_outputs=("reports/ready-b.md",),
                validation_steps=("pytest -q",),
                token_estimate=1000,
                usable_input_tokens=2000,
                status="ready",
                history=("ready-a",),
            ),
        ],
        requirement_mappings=[
            RequirementMapping(requirement_id="AC-001", task_ids=("completed", "superseded")),
            RequirementMapping(requirement_id="AC-002", task_ids=("blocked", "ready-a", "ready-b")),
        ],
        dependency_changes=[DependencyChange(task_id="blocked", prior_dependencies=(), new_dependencies=("ready-a",), summary="bootstrap")],
        change_summary=["manual resume revision"],
        rollback_metadata=RollbackMetadata(
            prior_revision_id="runtime-plan-r0",
            prior_revision_checksum="sha256:r0",
            rollback_reason="bootstrap",
            created_at="2026-06-20T12:00:00Z",
            application_id="cloud-application-resume-1",
        ),
        audit_event_ids=("audit-1",),
    )
    save_runtime_revision(tmp_path, revision)
    save_active_pointer(
        tmp_path,
        ActiveRevisionPointer(
            schema_version=1,
            active_revision_id=revision.revision_id,
            active_revision_checksum=revision.revision_checksum,
            previous_revision_id="runtime-plan-r0",
            update_timestamp="2026-06-20T12:00:00Z",
            application_id="cloud-application-resume-1",
        ),
    )
    application = ApplicationRecord(
        schema_version=1,
        application_id="cloud-application-resume-1",
        request_id=request.request.request_id,
        request_checksum=request.request.packet_checksum,
        response_checksum="sha256:response",
        approval_checksum=None,
        status="resume_pending",
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
            proposed_task_ids=("ready-a", "ready-b"),
            preserved_requirement_ids=("AC-001", "AC-002"),
            dependency_changes=(DependencyChange(task_id="ready-a"), DependencyChange(task_id="ready-b")),
            writable_paths=("runtime/ready-a/**", "runtime/ready-b/**"),
            expected_outputs=("reports/ready-a.md", "reports/ready-b.md"),
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
            eligible=True,
            resume_from_task_ids=("ready-a", "ready-b"),
            blocked_dependents=("blocked",),
            previously_completed_tasks=("completed",),
            reasons=(),
        ),
        plan_checksum="sha256:plan",
        revision_id=revision.revision_id,
        revision_checksum=revision.revision_checksum,
        active_revision_id=revision.revision_id,
        rollback_available=True,
    )
    tmp_application_path = tmp_path / ".agentic" / "cloud_applications" / "applications" / f"{application.application_id}.yaml"
    tmp_application_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_application_path.write_text(yaml.safe_dump(application.to_dict(), sort_keys=False), encoding="utf-8")

    calls: list[dict[str, object]] = []

    def fake_runtime_execution(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append(dict(kwargs))
        state_path = tmp_path / ".agentic" / "cloud_applications" / "execution_state.yaml"
        selected_task_ids = tuple(kwargs.get("resume_task_ids") or ())
        tasks: dict[str, dict[str, object]] = {}
        for task in revision.task_graph:
            status = "completed" if task.task_id in selected_task_ids else task.status
            tasks[task.task_id] = {
                "task_id": task.task_id,
                "title": task.title,
                "role": task.role,
                "dependencies": list(task.depends_on),
                "status": status,
                "attempt": 1,
                "outputs": [],
                "handoff_summary": {"available_to_dependents": [], "decisions": [], "outputs": []},
                "validation_result": {"status": "passed" if status == "completed" else "pending"},
            }
            if status == "completed":
                task_dir = tmp_path / "stories" / STORY / "reports" / "local_execution" / "tasks" / task.task_id
                task_dir.mkdir(parents=True, exist_ok=True)
                (task_dir / "execution.yaml").write_text(yaml.safe_dump(tasks[task.task_id], sort_keys=False), encoding="utf-8")
        state_path.write_text(
            yaml.safe_dump(
                {
                    "story": STORY,
                    "status": "completed",
                    "current_task": None,
                    "completed_tasks": list(selected_task_ids),
                    "blocked_tasks": ["blocked"],
                    "cloud_redecomposition_required_tasks": [],
                    "execution_order": [task.task_id for task in revision.task_graph],
                    "tasks": tasks,
                    "final_validation": {"status": "passed", "requirements_checked": [], "missing_requirements": []},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(result=SimpleNamespace(status="completed", state_path=state_path, story_path=tmp_path / "stories" / STORY))

    monkeypatch.setattr("agentic_dev.cloud_application.service.run_runtime_revision_execution", fake_runtime_execution)
    service = build_default_application_service(tmp_path)

    result = service.resume(request.request.request_id)

    assert result.status == "resumed"
    assert calls and calls[0]["resume_task_ids"] == ("ready-a", "ready-b")
    assert {record.task_id for record in load_task_publication_records(tmp_path)} == {"ready-a", "ready-b"}
    assert {lease.task_id for lease in load_execution_leases(tmp_path)} == {"ready-a", "ready-b"}


def test_publication_gate_rejects_duplicate_and_outside_scope_results(tmp_path: Path) -> None:
    revision = build_runtime_graph_revision(
        revision_id="runtime-plan-r1",
        parent_revision_id="runtime-plan-r0",
        application_id="cloud-application-1",
        created_at="2026-06-20T12:00:00Z",
        tasks=[
            TaskSnapshot(
                task_id="task-a",
                title="Task A",
                role="developer",
                depends_on=(),
                requirement_ids=("AC-001",),
                required_context=(),
                writable_paths=("results/**",),
                expected_outputs=("reports/a.md",),
                validation_steps=("pytest -q",),
                token_estimate=1,
                usable_input_tokens=2,
                status="ready",
                history=("bootstrap",),
            ),
        ],
        requirement_mappings=[RequirementMapping(requirement_id="AC-001", task_ids=("task-a",))],
        dependency_changes=[],
        change_summary=["test"],
        rollback_metadata=RollbackMetadata(
            prior_revision_id="runtime-plan-r0",
            prior_revision_checksum="sha256:r0",
            rollback_reason="test",
            created_at="2026-06-20T12:00:00Z",
            application_id="cloud-application-1",
        ),
        audit_event_ids=("audit-1",),
    )
    save_runtime_revision(tmp_path, revision)
    save_active_pointer(
        tmp_path,
        ActiveRevisionPointer(
            schema_version=1,
            active_revision_id=revision.revision_id,
            active_revision_checksum=revision.revision_checksum,
            previous_revision_id="runtime-plan-r0",
            update_timestamp="2026-06-20T12:00:00Z",
            application_id="cloud-application-1",
        ),
    )
    lease = ExecutionLease(
        schema_version=1,
        lease_id="lease-1",
        task_id="task-a",
        execution_attempt_id="attempt-1",
        runtime_revision_id=revision.revision_id,
        runtime_revision_checksum=revision.revision_checksum,
        local_model="local",
        writable_paths=("results/**",),
        start_timestamp="2026-06-20T12:00:00Z",
    )
    save_execution_lease(tmp_path, lease)
    lease2 = ExecutionLease.from_dict({**lease.to_dict(), "lease_id": "lease-2", "execution_attempt_id": "attempt-2"})
    save_execution_lease(tmp_path, lease2)
    result_path = tmp_path / "results" / "task-a" / "execution.yaml"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_bytes = b"status: passed\n"
    result_path.write_bytes(result_bytes)
    publication = TaskPublicationRecord(
        schema_version=1,
        task_id="task-a",
        lease_id="lease-1",
        execution_attempt_id="attempt-1",
        revision_id=revision.revision_id,
        revision_checksum=revision.revision_checksum,
        result_artifact_path=str(result_path.relative_to(tmp_path)),
        result_checksum=checksum_bytes(result_bytes),
        validation_status="passed",
        publication_timestamp="2026-06-20T12:00:00Z",
    )
    active_pointer = load_active_pointer(active_pointer_path(tmp_path))
    validate_publication_gate(
        tmp_path,
        publication=publication,
        lease=lease,
        active_pointer=active_pointer,
        revision=revision,
        task=revision.task_graph[0],
        result_path=result_path,
        result_bytes=result_bytes,
    )
    save_task_publication_record(tmp_path, publication)

    with pytest.raises(ValueError, match="already been published"):
        validate_publication_gate(
            tmp_path,
            publication=publication,
            lease=lease,
            active_pointer=active_pointer,
            revision=revision,
            task=revision.task_graph[0],
            result_path=result_path,
            result_bytes=result_bytes,
        )

    outside_result_path = tmp_path.parent / "outside" / "execution.yaml"
    outside_result_path.parent.mkdir(parents=True, exist_ok=True)
    outside_result_path.write_bytes(result_bytes)
    outside_publication = TaskPublicationRecord(
        schema_version=1,
        task_id="task-a",
        lease_id="lease-2",
        execution_attempt_id="attempt-2",
        revision_id=revision.revision_id,
        revision_checksum=revision.revision_checksum,
        result_artifact_path=str(outside_result_path),
        result_checksum=checksum_bytes(result_bytes),
        validation_status="passed",
        publication_timestamp="2026-06-20T12:00:00Z",
    )
    with pytest.raises(ValueError, match="outside the leased writable paths"):
        validate_publication_gate(
            tmp_path,
            publication=outside_publication,
            lease=lease2,
            active_pointer=active_pointer,
            revision=revision,
            task=revision.task_graph[0],
            result_path=outside_result_path,
            result_bytes=result_bytes,
        )


def test_recovery_preserves_newer_active_pointer_when_transaction_is_stale(tmp_path: Path) -> None:
    revision_r1 = build_runtime_graph_revision(
        revision_id="runtime-plan-r1",
        parent_revision_id="runtime-plan-r0",
        application_id="cloud-application-r1",
        created_at="2026-06-20T12:00:00Z",
        tasks=[
            TaskSnapshot(
                task_id="task-a",
                title="Task A",
                role="developer",
                depends_on=(),
                requirement_ids=("AC-001",),
                required_context=(),
                writable_paths=("results/a/**",),
                expected_outputs=("reports/a.md",),
                validation_steps=("pytest -q",),
                token_estimate=1,
                usable_input_tokens=2,
                status="ready",
                history=("bootstrap",),
            ),
        ],
        requirement_mappings=[RequirementMapping(requirement_id="AC-001", task_ids=("task-a",))],
        dependency_changes=[],
        change_summary=["r1"],
        rollback_metadata=RollbackMetadata(
            prior_revision_id="runtime-plan-r0",
            prior_revision_checksum="sha256:r0",
            rollback_reason="r1",
            created_at="2026-06-20T12:00:00Z",
            application_id="cloud-application-r1",
        ),
        audit_event_ids=("audit-1",),
    )
    revision_r2 = build_runtime_graph_revision(
        revision_id="runtime-plan-r2",
        parent_revision_id="runtime-plan-r1",
        application_id="cloud-application-r1",
        created_at="2026-06-20T12:01:00Z",
        tasks=list(revision_r1.task_graph),
        requirement_mappings=list(revision_r1.requirement_mappings),
        dependency_changes=list(revision_r1.dependency_mappings),
        change_summary=["r2"],
        rollback_metadata=RollbackMetadata(
            prior_revision_id="runtime-plan-r1",
            prior_revision_checksum=revision_r1.revision_checksum,
            rollback_reason="r2",
            created_at="2026-06-20T12:01:00Z",
            application_id="cloud-application-r1",
        ),
        audit_event_ids=("audit-2",),
    )
    revision_r3 = build_runtime_graph_revision(
        revision_id="runtime-plan-r3",
        parent_revision_id="runtime-plan-r2",
        application_id="cloud-application-r3",
        created_at="2026-06-20T12:02:00Z",
        tasks=list(revision_r1.task_graph),
        requirement_mappings=list(revision_r1.requirement_mappings),
        dependency_changes=list(revision_r1.dependency_mappings),
        change_summary=["r3"],
        rollback_metadata=RollbackMetadata(
            prior_revision_id="runtime-plan-r2",
            prior_revision_checksum=revision_r2.revision_checksum,
            rollback_reason="r3",
            created_at="2026-06-20T12:02:00Z",
            application_id="cloud-application-r3",
        ),
        audit_event_ids=("audit-3",),
    )
    save_runtime_revision(tmp_path, revision_r1)
    save_runtime_revision(tmp_path, revision_r2)
    save_runtime_revision(tmp_path, revision_r3)
    save_active_pointer(
        tmp_path,
        ActiveRevisionPointer(
            schema_version=1,
            active_revision_id=revision_r3.revision_id,
            active_revision_checksum=revision_r3.revision_checksum,
            previous_revision_id=revision_r2.revision_id,
            update_timestamp="2026-06-20T12:02:00Z",
            application_id="cloud-application-r3",
        ),
    )
    plan = ApplicationPlan(
        schema_version=1,
        application_id="cloud-application-r1",
        request_id="cloud-request-r1",
        request_checksum="sha256:request",
        response_checksum="sha256:response",
        approval_checksum=None,
        source_revision_id=revision_r1.revision_id,
        source_revision_checksum=revision_r1.revision_checksum,
        proposed_revision_id=revision_r2.revision_id,
        operation_type="replace_task_with_subtasks",
        source_task_snapshot=revision_r1.task_graph[0],
        proposed_tasks=tuple(revision_r2.task_graph),
        requirement_mapping=tuple(revision_r2.requirement_mappings),
        dependency_changes=tuple(revision_r2.dependency_mappings),
        writable_path_diff=("results/a/**",),
        context_budget_validation={},
        expected_outputs=("reports/a.md",),
        validation_steps=("pytest -q",),
        affected_completed_tasks=(),
        affected_pending_tasks=(),
        resume_candidates=("task-a",),
        rollback_target=revision_r1.revision_id,
        preconditions=("validated_safe",),
        predicted_side_effects=("supersede source task",),
        plan_checksum="sha256:plan",
        created_at="2026-06-20T12:01:00Z",
    )
    from agentic_dev.cloud_application.persistence import save_application_plan

    save_application_plan(tmp_path, plan)
    transaction = TransactionRecord(
        schema_version=1,
        transaction_id="txn-1",
        application_id="cloud-application-r1",
        source_revision_id=revision_r1.revision_id,
        source_revision_checksum=revision_r1.revision_checksum,
        proposed_revision_id=revision_r2.revision_id,
        proposed_revision_checksum=revision_r2.revision_checksum,
        expected_active_pointer=revision_r1.revision_id,
        phase="revision_published",
        artifact_paths=(str(revision_path(tmp_path, revision_r2.revision_id)),),
        created_at="2026-06-20T12:01:00Z",
        updated_at="2026-06-20T12:01:00Z",
        recovery_action="restore prior pointer atomically",
        details={"plan_checksum": "sha256:plan"},
    )
    from agentic_dev.cloud_application.persistence import save_transaction_record

    save_transaction_record(tmp_path, transaction)
    service = build_default_application_service(tmp_path)

    result = service.recover()

    assert result.reconciled is False
    assert any("stale published transaction" in finding for finding in result.findings)
    assert load_active_pointer(active_pointer_path(tmp_path)).active_revision_id == revision_r3.revision_id


def test_rollback_transaction_checksum_is_preserved_and_state_machine_applies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request_id, _ = prepare_validated_safe_request(tmp_path)
    service = build_default_application_service(tmp_path)
    patch_runtime_execution(monkeypatch, tmp_path)

    applied = service.plan_apply(request_id, dry_run=False)
    applied_transaction = load_transaction_record(transaction_path(tmp_path, f"txn-{applied.application.application_id}"))
    assert applied_transaction.proposed_revision_checksum == applied.active_revision_checksum
    rolled_back = service.rollback(applied.application.application_id)
    rollback_transaction = load_transaction_record(transaction_path(tmp_path, f"rollback-{applied.application.application_id}"))
    assert rollback_transaction.proposed_revision_checksum == applied_transaction.source_revision_checksum
    assert rolled_back.status == "rolled_back"
