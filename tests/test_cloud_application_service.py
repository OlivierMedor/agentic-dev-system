from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_dev.cloud_application import build_default_application_service
from agentic_dev.cloud_application.persistence import active_pointer_path, revision_path
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
    request = create_cloud_queue_request(
        project_path,
        story=STORY,
        title="Application target",
        details="details",
        requirements=["AC-001", "AC-002"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
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


def test_dry_run_creates_plan_without_pointer_change(tmp_path: Path) -> None:
    request_id, _ = prepare_validated_safe_request(tmp_path)
    service = build_default_application_service(tmp_path)

    result = service.plan_apply(request_id, dry_run=True)

    assert result.dry_run is True
    assert result.application.status == "application_planned"
    assert result.plan.plan_checksum
    assert result.revision_path is None
    assert not active_pointer_path(tmp_path).exists()


def test_apply_resume_and_rollback_flow(tmp_path: Path) -> None:
    request_id, _ = prepare_validated_safe_request(tmp_path)
    service = build_default_application_service(tmp_path)

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
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Approval target",
        details="details",
        requirements=["AC-001", "AC-002"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
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
