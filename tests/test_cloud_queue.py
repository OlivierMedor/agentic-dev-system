from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.cloud_queue import (
    CLOUD_QUEUE_SCHEMA_VERSION,
    CLOUD_RESPONSE_SCHEMA_VERSION,
    ManualPacketAdapter,
    build_cloud_queue_service,
    compare_request_response,
    create_request_from_story_blocker,
    load_import_records,
    validate_request_dict,
    validate_response_dict,
)


class DeterministicIds:
    def __init__(self) -> None:
        self.request = 0
        self.batch = 0
        self.event = 0

    def request_id(self, _service) -> str:
        self.request += 1
        return f"cloud-req-{self.request:04d}"

    def batch_id(self, _service) -> str:
        self.batch += 1
        return f"cloud-batch-{self.batch:04d}"

    def event_id(self, _service) -> str:
        self.event += 1
        return f"cloud-event-{self.event:06d}"


def make_service(tmp_path: Path) -> tuple[object, DeterministicIds]:
    ids = DeterministicIds()
    service = build_cloud_queue_service(
        tmp_path,
        now_fn=lambda: "2026-06-20T12:00:00Z",
        request_id_factory=ids.request_id,
        batch_id_factory=ids.batch_id,
        event_id_factory=ids.event_id,
    )
    return service, ids


def make_request_kwargs() -> dict[str, object]:
    return {
        "request_type": "task_redecomposition",
        "story_id": 63,
        "story_slug": "structured-cloud-escalation-and-manual-packet-queue",
        "task_id": "task-001",
        "reason_code": "context_limit_exceeded",
        "reason_summary": "Required context exceeds the local model limit.",
        "requested_action_summary": "Split the task into context-safe subtasks.",
        "task_title": "Split blocked task",
        "role": "developer",
        "dependencies": [],
        "writable_paths": ["src/**"],
        "expected_outputs": ["reports/task-001.md"],
        "validation": ["pytest"],
        "story_goal": "Implement the manual cloud escalation queue.",
        "acceptance_criteria": ["Queue items are exportable."],
        "architecture_decisions": [],
        "dependency_handoffs": [],
        "local_failure_summary": "The task exceeded the local context budget.",
        "relevant_files": [],
        "file_summaries": [],
        "token_estimate": 18000,
        "usable_token_limit": 8000,
        "requirement_ids": ["REQ-1"],
        "immutable_requirement_ids": ["IMM-1"],
    }


def make_safe_response(request_id: str) -> dict[str, object]:
    return {
        "schema_version": CLOUD_RESPONSE_SCHEMA_VERSION,
        "request_id": request_id,
        "response_type": "task_redecomposition",
        "status": "completed",
        "summary": "Split the task into bounded subtasks.",
        "requirement_preservation": {
            "preserved_requirement_ids": ["REQ-1", "IMM-1"],
            "removed_requirement_ids": [],
            "modified_requirement_ids": [],
        },
        "proposed_changes": {
            "subtasks": [
                {
                    "id": "child-1",
                    "title": "Implement queue models",
                    "requirement_ids": ["REQ-1"],
                    "required_context": {
                        "files": [],
                        "summaries": [],
                        "prior_task_outputs": [],
                        "architecture_decisions": [],
                    },
                    "depends_on": [],
                    "writable_paths": ["src/**"],
                    "expected_outputs": ["src/agentic_dev/cloud_queue.py"],
                    "validation": ["pytest tests/test_cloud_queue.py -q"],
                    "estimated_token_usage": 1200,
                }
            ],
            "architecture_decisions": [],
            "writable_paths": ["src/**"],
            "external_services": [],
        },
        "risk_classification": {"claims_requirement_preserving": True},
        "handoff": {"decisions": [], "risks": [], "follow_up_actions": []},
    }


def make_approval_response(request_id: str) -> dict[str, object]:
    response = make_safe_response(request_id)
    response["proposed_changes"] = {
        "subtasks": [
            {
                "id": "child-1",
                "title": "Add docs and queue output",
                "requirement_ids": ["REQ-1"],
                "required_context": {
                    "files": [],
                    "summaries": [],
                    "prior_task_outputs": [],
                    "architecture_decisions": [],
                },
                "depends_on": [],
                "writable_paths": ["src/**", "docs/**"],
                "expected_outputs": ["docs/cloud_queue.md"],
                "validation": ["pytest tests/test_cloud_queue.py -q"],
                "estimated_token_usage": 1200,
            }
        ],
        "architecture_decisions": [],
        "writable_paths": ["src/**", "docs/**"],
        "external_services": [],
    }
    return response


def write_response_yaml(path: Path, response: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(response, sort_keys=False), encoding="utf-8")


def response_bundle_bytes(entries: dict[str, dict[str, object]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, response in entries.items():
            archive.writestr(name, yaml.safe_dump(response, sort_keys=False))
    return buffer.getvalue()


def test_request_and_response_schema_validation() -> None:
    request = {
        "schema_version": CLOUD_QUEUE_SCHEMA_VERSION,
        "request_id": "cloud-req-0001",
        "request_type": "task_redecomposition",
        "story_id": 63,
        "story_slug": "structured-cloud-escalation-and-manual-packet-queue",
        "task_id": "task-001",
        "created_at": "2026-06-20T12:00:00Z",
        "status": "queued",
        "reason": {"code": "context_limit_exceeded", "summary": "Context is too large."},
        "requested_action": {"summary": "Split the task."},
        "requirements": {"applicable_requirement_ids": [], "immutable_requirement_ids": []},
        "task": {
            "title": "",
            "role": "developer",
            "dependencies": [],
            "writable_paths": [],
            "expected_outputs": [],
            "validation": [],
        },
        "context": {
            "story_goal": "",
            "acceptance_criteria": [],
            "architecture_decisions": [],
            "dependency_handoffs": [],
            "local_failure_summary": "",
            "relevant_files": [],
            "file_summaries": [],
            "token_estimate": 0,
            "usable_token_limit": 0,
        },
        "constraints": {
            "preserve_requirements": True,
            "may_expand_writable_paths": False,
            "may_add_external_services": False,
            "may_change_architecture": False,
            "may_execute_code": False,
        },
        "response_contract": {"format": "yaml", "schema_version": CLOUD_RESPONSE_SCHEMA_VERSION},
        "dependencies": [],
        "export_batch_ids": [],
        "next_action": "Ready to export.",
    }
    validate_request_dict(request)

    invalid_request = dict(request)
    invalid_request["schema_version"] = 99
    with pytest.raises(ValueError, match="schema_version"):
        validate_request_dict(invalid_request)

    response = make_safe_response("cloud-req-0001")
    validate_response_dict(response)

    invalid_response = dict(response)
    invalid_response["schema_version"] = 99
    with pytest.raises(ValueError, match="schema_version"):
        validate_response_dict(invalid_response)


def test_state_transitions_and_audit(tmp_path: Path) -> None:
    service, ids = make_service(tmp_path)
    request = service.create_request(**make_request_kwargs())
    request_path = service.request_path(request.request_id)

    assert request.status == "ready_for_export"
    assert request_path.exists()

    service.transition_request(request.request_id, "exported", "Exported for testing.")
    loaded = service.load_request_dict(request.request_id)
    assert loaded["status"] == "exported"

    with pytest.raises(ValueError, match="Invalid state transition"):
        service.transition_request(request.request_id, "queued", "Cannot go backwards.")

    audit_files = sorted((tmp_path / ".agentic" / "cloud_queue" / "audit").glob("*.yaml"))
    assert audit_files
    assert ids.event >= 2


def test_single_export_and_redaction(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    secret_file = tmp_path / "docs" / "notes.txt"
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_text(
        "Authorization: Bearer SECRET\napi_key=super-secret\n",
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text("PASSWORD=secret\n", encoding="utf-8")

    request = service.create_request(
        **{
            **make_request_kwargs(),
            "relevant_files": ["docs/notes.txt", ".env"],
        },
    )

    export = service.export_request(request.request_id)
    assert export.batch_id == "cloud-batch-0001"
    assert export.packet_path.exists()
    assert export.manifest_path.exists()

    with zipfile.ZipFile(export.packet_path) as archive:
        names = sorted(archive.namelist())
        assert "manifest.yaml" in names
        assert "instructions.md" in names
        assert "response_schema.yaml" in names
        assert "requests/cloud-req-0001.yaml" in names
        assert "context/docs/notes.txt" in names
        assert "context/.env" not in names
        packet_text = archive.read("context/docs/notes.txt").decode("utf-8")
        assert "SECRET" not in packet_text
        assert "REDACTED" in packet_text
        instruction_text = archive.read("instructions.md").decode("utf-8")
        assert "Do not execute code." in instruction_text

    repeated = service.export_request(request.request_id)
    assert repeated.reused_existing_export is True
    assert repeated.batch_id == export.batch_id


def test_batch_export_filters_dependencies(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    first = service.create_request(**make_request_kwargs())
    second = service.create_request(
        **{
            **make_request_kwargs(),
            "reason_code": "requirement_ambiguity",
            "reason_summary": "Clarify dependencies first.",
            "requested_action_summary": "Clarify the ambiguous dependency.",
            "dependencies": [first.request_id],
        },
    )

    batch = service.export_ready_requests()
    assert batch.request_ids == [first.request_id]
    assert second.request_id not in batch.request_ids


def test_import_validation_and_classification(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    request = service.create_request(**make_request_kwargs())
    service.export_request(request.request_id)

    response_path = tmp_path / "response.yaml"
    response = make_safe_response(request.request_id)
    write_response_yaml(response_path, response)

    result = service.import_response_bundle(response_path)
    assert result.valid_count == 1
    assert result.invalid_count == 0
    imported = service.load_request_dict(request.request_id)
    assert imported["status"] == "validated_safe"
    assert imported["classification"]["classification"] == "validated_safe"
    assert imported["validation_result"]["passed"] is True
    assert compare_request_response(request.to_dict(), response).passed is True


def test_import_approval_required_then_approve_and_changed_checksum_blocks_approval(
    tmp_path: Path,
) -> None:
    service, _ = make_service(tmp_path)
    request = service.create_request(**make_request_kwargs())
    service.export_request(request.request_id)

    response_path = tmp_path / "approval-response.yaml"
    write_response_yaml(response_path, make_approval_response(request.request_id))
    imported = service.import_response_bundle(response_path)
    assert imported.valid_count == 1
    assert service.load_request_dict(request.request_id)["status"] == "approval_required"

    raw_path = service.request_dir(request.request_id) / "response.raw"
    raw_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="changed since classification"):
        service.approve_request(request.request_id)


def test_valid_approval_path(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    request = service.create_request(**make_request_kwargs())
    service.export_request(request.request_id)
    response_path = tmp_path / "approval-response.yaml"
    write_response_yaml(response_path, make_approval_response(request.request_id))
    service.import_response_bundle(response_path)

    approval = service.approve_request(request.request_id)
    assert approval.new_status == "approved"


def test_rejection_requires_reason(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    request = service.create_request(**make_request_kwargs())
    service.export_request(request.request_id)
    response_path = tmp_path / "approval-response.yaml"
    write_response_yaml(response_path, make_approval_response(request.request_id))
    service.import_response_bundle(response_path)

    with pytest.raises(ValueError, match="must not be empty"):
        service.reject_request(request.request_id, "")

    rejected = service.reject_request(request.request_id, "Scope change is not acceptable.")
    assert rejected.new_status == "rejected"


def test_batch_import_keeps_valid_siblings(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    request_one = service.create_request(**make_request_kwargs())
    request_two = service.create_request(
        **{
            **make_request_kwargs(),
            "reason_code": "requirement_ambiguity",
            "reason_summary": "Clarify the request before continuing.",
            "requested_action_summary": "Clarify the request.",
        },
    )
    service.export_request(request_one.request_id)
    service.export_request(request_two.request_id)

    bundle = response_bundle_bytes(
        {
            "responses/valid.yaml": make_safe_response(request_one.request_id),
            "responses/invalid.yaml": {"response_type": "task_redecomposition"},
        },
    )
    bundle_path = tmp_path / "bundle.zip"
    bundle_path.write_bytes(bundle)

    result = service.import_response_bundle(bundle_path)
    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert service.load_request_dict(request_one.request_id)["status"] == "validated_safe"


def test_zip_import_security_controls(tmp_path: Path) -> None:
    service, _ = make_service(tmp_path)
    service.create_request(**make_request_kwargs())

    zip_path = tmp_path / "traversal.zip"
    with zipfile.ZipFile(zip_path, mode="w") as archive:
        archive.writestr("../evil.yaml", "request_id: cloud-req-0001\n")

    with pytest.raises(ValueError, match="Unsafe archive entry path"):
        load_import_records(zip_path, service.packet_limits)


def test_blocker_integration_creates_request_from_story_blocker(tmp_path: Path) -> None:
    story_path = tmp_path / "stories" / "story_063"
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# STORY-063\n", encoding="utf-8")
    (story_path / "status.yaml").write_text("story_id: 63\nslug: story-063\n", encoding="utf-8")

    request = create_request_from_story_blocker(
        tmp_path,
        "story_063",
        blocker_type="context_limit",
        blocker_summary="Context exceeds the local limit.",
        task_id="task-007",
        requirement_ids=["REQ-1"],
        immutable_requirement_ids=["IMM-1"],
        dependencies=["cloud-req-0001"],
        writable_paths=["src/**"],
        expected_outputs=["reports/task-007.md"],
        validation=["pytest"],
        local_failure_summary="The local model budget is too small.",
    )

    assert request.request_type == "task_redecomposition"
    assert request.story_id == 63
    assert request.story_slug == "story-063"
    assert request.reason["code"] == "context_limit_exceeded"


def test_manual_adapter_is_offline_and_provider_neutral() -> None:
    adapter = ManualPacketAdapter()
    request = {"request_id": "cloud-req-0001"}
    assert adapter.provider_name == "manual"
    assert adapter.prepare_request(request) == request
    normalized = adapter.normalize_response(
        yaml.safe_dump(make_safe_response("cloud-req-0001")).encode("utf-8"),
        request_id="cloud-req-0001",
    )
    assert normalized["request_id"] == "cloud-req-0001"


def test_cli_cloud_queue_commands_use_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "cloud-queue",
            "create",
            "--story",
            "story_063",
            "--request-type",
            "task_redecomposition",
            "--reason-code",
            "context_limit_exceeded",
            "--reason-summary",
            "Context exceeds the local model limit.",
            "--requested-action",
            "Split the task into context-safe subtasks.",
            "--writable-path",
            "src/**",
            "--expected-output",
            "reports/task-001.md",
            "--validation",
            "pytest",
        ],
    )
    main()
    create_output = capsys.readouterr().out
    assert "Cloud queue request created:" in create_output
    assert "cloud-req-0001" in create_output

    monkeypatch.setattr("sys.argv", ["agentic", "cloud-queue", "list"])
    main()
    list_output = capsys.readouterr().out
    assert "Cloud queue requests:" in list_output

    monkeypatch.setattr("sys.argv", ["agentic", "cloud-queue", "status"])
    main()
    status_output = capsys.readouterr().out
    assert "Cloud Queue Status" in status_output

    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "cloud-queue", "export", "--request", "cloud-req-0001"],
    )
    main()
    export_output = capsys.readouterr().out
    assert "Cloud queue export batch:" in export_output

    response_path = tmp_path / "response.yaml"
    write_response_yaml(response_path, make_safe_response("cloud-req-0001"))
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "cloud-queue", "import", "--file", str(response_path)],
    )
    main()
    import_output = capsys.readouterr().out
    assert "Cloud queue import summary:" in import_output
