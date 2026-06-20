from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml

from agentic_dev.cloud_queue import (
    approve_cloud_queue_request,
    cancel_cloud_queue_request,
    cloud_queue_status,
    create_cloud_queue_request,
    dependencies_resolved,
    export_cloud_queue_request,
    fail_cloud_queue_request,
    import_cloud_queue_response,
    list_cloud_queue_requests,
    reject_cloud_queue_request,
    show_cloud_queue_request,
)
from agentic_dev.cloud_queue.classification import APPROVAL_REQUIRED, VALIDATED_FAILED
from agentic_dev.cloud_queue.persistence import read_audit_events


STORY = "story_063_structured_cloud_escalation_and_manual_packet_queue"


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# STORY-063\n", encoding="utf-8")
    return story_path


def event_ids_factory() -> callable:
    counter = {"value": 0}

    def next_id() -> str:
        counter["value"] += 1
        return f"event-{counter['value']}"

    return next_id


def response_payload(
    request_id: str,
    batch_id: str,
    decision: str,
    claims: dict[str, object],
    normalized_response: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "response_id": f"{request_id}-response",
        "request_id": request_id,
        "batch_id": batch_id,
        "response_schema_version": 1,
        "normalized_response": normalized_response or {"summary": "normalized"},
        "raw_response": "raw",
        "checksum": "checksum",
        "decision": decision,
        "claims": claims,
        "adapter": "manual_packet",
    }


def write_response_yaml(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def request_claims(request_id: str, batch_id: str, requirements: list[str], writable_paths: list[str]) -> dict[str, object]:
    return {
        "applicable_requirements": list(requirements),
        "writable_paths": list(writable_paths),
        "scope_changes": [],
        "dependency_status": "resolved",
        "resolved_dependencies": [],
        "safe_to_apply": True,
    }


def test_create_list_show_status_and_audit_events(tmp_path: Path) -> None:
    create_story(tmp_path)
    result = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Investigate cloud escalation",
        details="The local model needs a manual review packet.",
        requirements=["AC-001", "AC-002"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        notes=["blocked"],
        request_id_factory=lambda: "CQ-20260620-0001",
        batch_id_factory=lambda: "batch-20260620-1",
        event_id_factory=event_ids_factory(),
    )

    show = show_cloud_queue_request(tmp_path, result.request.request_id)
    listing = list_cloud_queue_requests(tmp_path)
    status = cloud_queue_status(tmp_path)
    audit_events = read_audit_events(tmp_path)

    assert show.request.request_id == result.request.request_id
    assert listing.counts_by_state["ready"] == 1
    assert status.request_count == 1
    assert status.counts_by_state["ready"] == 1
    assert audit_events[0]["event_id"] == "event-1"
    assert audit_events[0]["event_type"] == "create"
    assert audit_events[0]["request_id"] == result.request.request_id
    assert audit_events[0]["prior_state"] == "new"
    assert audit_events[0]["new_state"] == "ready"
    assert result.request_path.exists()


def test_export_writes_per_request_audit_events_and_manifest(tmp_path: Path) -> None:
    create_story(tmp_path)
    request_a = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="First request",
        details="first",
        requirements=["AC-001"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        request_id_factory=lambda: "CQ-20260620-0001",
        batch_id_factory=lambda: "batch-1",
        event_id_factory=event_ids_factory(),
    )
    request_b = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Second request",
        details="second",
        requirements=["AC-002"],
        writable_paths=["tests/test_cloud_queue_service.py"],
        request_id_factory=lambda: "CQ-20260620-0002",
        batch_id_factory=lambda: "batch-1",
        event_id_factory=event_ids_factory(),
    )

    result = export_cloud_queue_request(tmp_path, all_ready=True, event_id_factory=event_ids_factory())

    assert result.request_count == 2
    assert result.request_ids == [request_a.request.request_id, request_b.request.request_id]
    assert result.export_path.exists()
    assert result.export_markdown_path.exists()
    assert result.manifest_path.exists()

    with ZipFile(result.export_path) as archive:
        members = archive.namelist()
        assert f"{request_a.request.request_id}/request.yaml" in members
        assert f"{request_b.request.request_id}/request.yaml" in members
        manifest = yaml.safe_load(archive.read("manifest.yaml").decode("utf-8"))
        assert manifest["request_ids"] == result.request_ids
        assert manifest["request_count"] == 2
        assert len(manifest["members"]) == 8

    audit_events = read_audit_events(tmp_path)
    assert [event["event_type"] for event in audit_events[-2:]] == ["export", "export"]
    assert audit_events[-2]["request_id"] == request_a.request.request_id
    assert audit_events[-1]["request_id"] == request_b.request.request_id
    assert audit_events[-2]["batch_id"] == "batch-1"
    assert audit_events[-1]["batch_id"] == "batch-1"


def test_dependency_resolution_blocks_export_until_prerequisite_resolves(tmp_path: Path) -> None:
    create_story(tmp_path)
    prerequisite = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Prerequisite",
        details="first",
        requirements=["AC-001"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        request_id_factory=lambda: "CQ-1",
        batch_id_factory=lambda: "batch-1",
        event_id_factory=event_ids_factory(),
    )
    dependent = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Dependent",
        details="second",
        requirements=["AC-002"],
        writable_paths=["tests/test_cloud_queue_service.py"],
        dependencies=[prerequisite.request.request_id],
        request_id_factory=lambda: "CQ-2",
        batch_id_factory=lambda: "batch-1",
        event_id_factory=event_ids_factory(),
    )

    assert dependencies_resolved(tmp_path, dependent.request) is False
    with pytest.raises(ValueError, match="Request is not ready for export"):
        export_cloud_queue_request(tmp_path, request_id=dependent.request.request_id)


def test_import_classifies_safe_approval_required_and_failed_responses_independently(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    safe_request_record = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Import target",
        details="details",
        requirements=["AC-001", "AC-002"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        request_id_factory=lambda: "CQ-20260620-0001",
        batch_id_factory=lambda: "batch-1",
        event_id_factory=event_ids_factory(),
    )
    export_cloud_queue_request(
        tmp_path,
        request_id=safe_request_record.request.request_id,
        event_id_factory=event_ids_factory(),
    )

    safe_file = write_response_yaml(
        tmp_path / "safe.yaml",
        response_payload(
            safe_request_record.request.request_id,
            safe_request_record.request.batch_id,
            "SAFE",
            request_claims(
                safe_request_record.request.request_id,
                safe_request_record.request.batch_id,
                ["AC-001", "AC-002"],
                ["src/agentic_dev/cloud_queue/service.py"],
            ),
        ),
    )

    safe_result = import_cloud_queue_response(tmp_path, safe_file)
    safe_request = show_cloud_queue_request(tmp_path, safe_request_record.request.request_id).request
    assert safe_result.valid_count == 1
    assert safe_request.state == "validated_safe"

    approval_request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Approval target",
        details="details",
        requirements=["AC-003"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        request_id_factory=lambda: "CQ-20260620-0002",
        batch_id_factory=lambda: "batch-2",
        event_id_factory=event_ids_factory(),
    )
    export_cloud_queue_request(
        tmp_path,
        request_id=approval_request.request.request_id,
        event_id_factory=event_ids_factory(),
    )
    approval_file = write_response_yaml(
        tmp_path / "approval.yaml",
        response_payload(
            approval_request.request.request_id,
            approval_request.request.batch_id,
            "APPROVAL_REQUIRED",
            {
                "applicable_requirements": ["AC-001", "AC-002"],
                "writable_paths": ["src/agentic_dev/cloud_queue/service.py", "docs/cloud_queue_operator_guide.md"],
                "scope_changes": ["expanded docs"],
                "dependency_status": "resolved",
                "resolved_dependencies": [],
                "safe_to_apply": False,
            },
        ),
    )
    approval_result = import_cloud_queue_response(tmp_path, approval_file)
    approval_state = show_cloud_queue_request(tmp_path, approval_request.request.request_id).request.state
    assert approval_result.valid_count == 1
    assert approval_state == APPROVAL_REQUIRED

    failed_request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Failed target",
        details="details",
        requirements=["AC-004"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        request_id_factory=lambda: "CQ-20260620-0003",
        batch_id_factory=lambda: "batch-3",
        event_id_factory=event_ids_factory(),
    )
    export_cloud_queue_request(
        tmp_path,
        request_id=failed_request.request.request_id,
        event_id_factory=event_ids_factory(),
    )
    failed_file = write_response_yaml(
        tmp_path / "failed.yaml",
        response_payload(
            failed_request.request.request_id,
            failed_request.request.batch_id,
            "SAFE",
            {
                "applicable_requirements": ["AC-001"],
                "writable_paths": ["src/agentic_dev/cloud_queue/service.py"],
                "scope_changes": [],
                "dependency_status": "blocked",
                "resolved_dependencies": [],
                "safe_to_apply": False,
            },
        ),
    )
    failed_result = import_cloud_queue_response(tmp_path, failed_file)
    failed_state = show_cloud_queue_request(tmp_path, failed_request.request.request_id).request.state
    assert failed_result.invalid_count == 1
    assert failed_state == VALIDATED_FAILED


def test_approval_checksum_lock_blocks_stale_checksum_and_reclassification_changes_binding(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Approve target",
        details="details",
        requirements=["AC-010"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        request_id_factory=lambda: "CQ-APPROVE-1",
        batch_id_factory=lambda: "batch-approve",
        event_id_factory=event_ids_factory(),
    )
    export_cloud_queue_request(tmp_path, request_id=request.request.request_id, event_id_factory=event_ids_factory())
    import_cloud_queue_response(
        tmp_path,
        write_response_yaml(
            tmp_path / "approve.yaml",
            response_payload(
                request.request.request_id,
                request.request.batch_id,
                "APPROVAL_REQUIRED",
                {
                    "applicable_requirements": ["AC-010"],
                    "writable_paths": ["src/agentic_dev/cloud_queue/service.py", "docs/cloud_queue_operator_guide.md"],
                    "scope_changes": ["docs"],
                    "dependency_status": "resolved",
                    "resolved_dependencies": [],
                    "safe_to_apply": False,
                },
            ),
        ),
    )
    approval_request = show_cloud_queue_request(tmp_path, request.request.request_id).request
    locked_checksum = approval_request.approval_checksum

    with pytest.raises(ValueError, match="Approval checksum does not match"):
        approve_cloud_queue_request(tmp_path, request.request.request_id, normalized_response_checksum_value="wrong")

    approved = approve_cloud_queue_request(
        tmp_path,
        request.request.request_id,
        normalized_response_checksum_value=locked_checksum,
        operator_note="Approve exact checksum",
        event_id_factory=event_ids_factory(),
    )
    assert approved.request.state == "approved"

    # Reclassify a fresh request and prove the checksum binding changes.
    second = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Reclassify target",
        details="details",
        requirements=["AC-011"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        request_id_factory=lambda: "CQ-APPROVE-2",
        batch_id_factory=lambda: "batch-approve-2",
        event_id_factory=event_ids_factory(),
    )
    export_cloud_queue_request(tmp_path, request_id=second.request.request_id, event_id_factory=event_ids_factory())
    import_cloud_queue_response(
        tmp_path,
        write_response_yaml(
            tmp_path / "approve2.yaml",
            response_payload(
                second.request.request_id,
                second.request.batch_id,
                "APPROVAL_REQUIRED",
                {
                    "applicable_requirements": ["AC-011"],
                    "writable_paths": ["src/agentic_dev/cloud_queue/service.py", "docs/cloud_queue_operator_guide.md"],
                    "scope_changes": ["docs"],
                    "dependency_status": "resolved",
                    "resolved_dependencies": [],
                    "safe_to_apply": False,
                },
            ),
        ),
    )
    first_binding = show_cloud_queue_request(tmp_path, second.request.request_id).request.approval_checksum
    second_import = import_cloud_queue_response(
        tmp_path,
        write_response_yaml(
            tmp_path / "approve2-reclassify.yaml",
            response_payload(
                second.request.request_id,
                second.request.batch_id,
                "SAFE",
                {
                    "applicable_requirements": ["AC-011"],
                    "writable_paths": ["src/agentic_dev/cloud_queue/service.py"],
                    "scope_changes": [],
                    "dependency_status": "resolved",
                    "resolved_dependencies": [],
                    "safe_to_apply": True,
                },
                normalized_response={"summary": "reclassified"},
            ),
        ),
    )
    second_binding = show_cloud_queue_request(tmp_path, second.request.request_id).request.approval_checksum
    assert second_import.valid_count == 1
    assert first_binding != second_binding


def test_reject_cancel_and_fail_update_state_and_audit(tmp_path: Path) -> None:
    create_story(tmp_path)
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Decision target",
        details="details",
        requirements=["AC-100"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        request_id_factory=lambda: "CQ-DECISION",
        batch_id_factory=lambda: "batch-decision",
        event_id_factory=event_ids_factory(),
    )
    rejected = reject_cloud_queue_request(tmp_path, request.request.request_id, operator_note="not needed", event_id_factory=event_ids_factory())
    assert rejected.request.state == "rejected"

    request2 = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Cancel target",
        details="details",
        requirements=["AC-101"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        request_id_factory=lambda: "CQ-CANCEL",
        batch_id_factory=lambda: "batch-cancel",
        event_id_factory=event_ids_factory(),
    )
    canceled = cancel_cloud_queue_request(tmp_path, request2.request.request_id, reason="cancelled", event_id_factory=event_ids_factory())
    assert canceled.request.state == "canceled"

    request3 = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Failure target",
        details="details",
        requirements=["AC-102"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        request_id_factory=lambda: "CQ-FAIL",
        batch_id_factory=lambda: "batch-fail",
        event_id_factory=event_ids_factory(),
    )
    failed = fail_cloud_queue_request(tmp_path, request3.request.request_id, reason="broken", event_id_factory=event_ids_factory())
    assert failed.request.state == "failed"


def test_export_rejects_unready_request(tmp_path: Path) -> None:
    create_story(tmp_path)
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Dependent export",
        details="details",
        requirements=["AC-200"],
        writable_paths=["src/agentic_dev/cloud_queue/service.py"],
        dependencies=["CQ-MISSING"],
        request_id_factory=lambda: "CQ-UNREADY",
        batch_id_factory=lambda: "batch-unready",
        event_id_factory=event_ids_factory(),
    )
    with pytest.raises(ValueError, match="Request is not ready for export"):
        export_cloud_queue_request(tmp_path, request_id=request.request.request_id)
