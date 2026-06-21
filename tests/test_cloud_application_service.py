from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from agentic_dev.cloud_application import build_default_application_service
from agentic_dev.cloud_application.models import ExecutionLease
from agentic_dev.cloud_application.graph import build_runtime_graph_revision
from agentic_dev.cloud_application.models import (
    ActiveRevisionPointer,
    DependencyChange,
    RequirementMapping,
    RollbackMetadata,
    TaskSnapshot,
)
from agentic_dev.cloud_application.publication import validate_publication_gate
from agentic_dev.cloud_application.persistence import active_pointer_path, revision_path, save_active_pointer, save_runtime_revision
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
    state_path.write_text("status: completed\n", encoding="utf-8")
    fake_result = SimpleNamespace(
        result=SimpleNamespace(status="completed", state_path=state_path, story_path=project_path / "stories" / STORY),
    )
    monkeypatch.setattr("agentic_dev.cloud_application.service.run_runtime_revision_execution", lambda *args, **kwargs: fake_result)


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
    before = active_pointer_path(tmp_path).read_text(encoding="utf-8")

    result = service.plan_apply(request_id, dry_run=True)

    assert result.dry_run is True
    assert result.application.status == "application_planned"
    assert result.plan.plan_checksum
    assert result.revision_path is None
    assert active_pointer_path(tmp_path).read_text(encoding="utf-8") == before


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


def test_publication_gate_rejects_stale_worker_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request_id, _ = prepare_validated_safe_request(tmp_path)
    service = build_default_application_service(tmp_path)
    patch_runtime_execution(monkeypatch, tmp_path)
    service.plan_apply(request_id, dry_run=False)
    service.resume(request_id)

    lease_path = tmp_path / ".agentic" / "execution_leases"
    lease_file = next(iter(lease_path.glob("*.yaml")))
    lease = ExecutionLease.from_dict(yaml.safe_load(lease_file.read_text(encoding="utf-8")))
    stale_pointer = ActiveRevisionPointer(
        schema_version=1,
        active_revision_id="runtime-plan-r999",
        active_revision_checksum="sha256:stale",
        previous_revision_id=lease.runtime_revision_id,
        update_timestamp="2026-06-20T12:00:00Z",
        application_id="bootstrap",
    )

    with pytest.raises(ValueError, match="Lease revision does not match the active revision"):
        validate_publication_gate(
            tmp_path,
            lease=lease,
            execution_attempt_id=lease.execution_attempt_id,
            active_pointer=stale_pointer,
            result_checksum="sha256:result",
            result_path=lease_file,
        )
