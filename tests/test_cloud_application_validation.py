from __future__ import annotations

import pytest

from agentic_dev.cloud_application.models import TaskSnapshot
from agentic_dev.cloud_application.validation import (
    canonical_request_checksum,
    canonical_response_checksum,
    validate_approval_scope,
    validate_context_budget,
    validate_dependency_graph,
    validate_eligibility,
    validate_requirement_coverage,
    validate_writable_paths_exact,
)
from agentic_dev.cloud_queue.models import CloudQueueRequest


def sample_request(*, state: str = "validated_safe", classification: str = "validated_safe") -> CloudQueueRequest:
    return CloudQueueRequest(
        request_id="CQ-20260620-0001",
        story="safe-cloud-response-application-and-local-resume",
        title="Runtime plan update",
        blocker_type="local_blocker",
        details="details",
        state=state,
        prior_state="imported",
        batch_id="batch-1",
        request_count=1,
        requirements=["AC-001", "AC-002"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
        dependencies=[],
        context_files=[],
        created_at="2026-06-20T12:00:00Z",
        updated_at="2026-06-20T12:00:00Z",
        packet_checksum="sha256:request",
        normalized_response_checksum="sha256:response",
        approval_checksum=None,
        raw_response_checksum="sha256:raw",
        classification=classification,
        next_action="Apply safely",
    )


def sample_tasks() -> list[TaskSnapshot]:
    return [
        TaskSnapshot(
            task_id="source",
            title="Source",
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
        ),
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
            source_task_id="source",
        ),
        TaskSnapshot(
            task_id="child-b",
            title="Child B",
            role="test",
            depends_on=("child-a",),
            requirement_ids=("AC-002",),
            required_context=("story.md",),
            writable_paths=("runtime/app/validator/**",),
            expected_outputs=("reports/validator.md",),
            validation_steps=("pytest -q",),
            token_estimate=500,
            usable_input_tokens=2000,
            status="ready",
            source_task_id="source",
        ),
    ]


def test_validated_safe_request_is_eligible() -> None:
    request = sample_request()
    result = validate_eligibility(request)

    assert result.eligible is True
    assert result.source_kind == "validated_safe"
    assert result.request_checksum == canonical_request_checksum(request)
    assert result.response_checksum == canonical_response_checksum(request)


def test_approval_required_request_needs_approval_record() -> None:
    request = sample_request(state="approved", classification="approval_required")
    approval = {
        "request_id": request.request_id,
        "approved": True,
        "normalized_response_checksum": request.normalized_response_checksum,
        "approved_writable_paths": list(request.writable_paths),
        "approved_requirements": list(request.requirements),
    }

    result = validate_eligibility(request, approval_record=approval)

    assert result.eligible is True
    assert result.eligible_for_approval is True


def test_missing_approval_is_rejected() -> None:
    request = sample_request(state="approved", classification="approval_required")

    with pytest.raises(ValueError, match="missing an approval record"):
        validate_eligibility(request, approval_record=None)


def test_stale_approval_is_rejected() -> None:
    request = sample_request(state="approved", classification="approval_required")
    approval = {
        "request_id": request.request_id,
        "approved": True,
        "normalized_response_checksum": "sha256:other",
        "approved_writable_paths": list(request.writable_paths),
        "approved_requirements": list(request.requirements),
    }

    with pytest.raises(ValueError, match="Approval checksum does not match"):
        validate_eligibility(request, approval_record=approval)


def test_dependency_and_requirement_validation_rejects_invalid_graph() -> None:
    tasks = sample_tasks()
    validate_dependency_graph(tasks)
    validate_requirement_coverage(tasks[0], tasks[1:], ["AC-001", "AC-002"])

    with pytest.raises(ValueError, match="Missing dependency"):
        validate_dependency_graph([tasks[1], TaskSnapshot(**{**tasks[1].to_dict(), "task_id": "child-c", "depends_on": ("missing",)})])


def test_writable_path_and_context_validation_are_deterministic() -> None:
    paths = validate_writable_paths_exact(
        ["runtime/app/parser/**", "runtime/app/validator/**"],
        ["runtime/app/parser/**", "runtime/app/validator/**"],
    )
    assert paths == ["runtime/app/parser/**", "runtime/app/validator/**"]

    validate_context_budget(sample_tasks()[0])

    with pytest.raises(ValueError, match="expands writable paths"):
        validate_writable_paths_exact(["runtime/app/parser/**"], ["runtime/app/parser/**", "runtime/app/validator/**"])


def test_approval_scope_matches_exact_paths_and_requirements() -> None:
    approval = {
        "approved_writable_paths": ["runtime/app/parser/**", "runtime/app/validator/**"],
        "approved_requirements": ["AC-001", "AC-002"],
    }
    validate_approval_scope(approval, ["runtime/app/parser/**", "runtime/app/validator/**"], ["AC-001", "AC-002"])

    with pytest.raises(ValueError, match="exactly match the proposed application"):
        validate_approval_scope(approval, ["runtime/app/parser/**"], ["AC-001"])
