from __future__ import annotations

import os
import sys
import uuid
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace

import yaml

from agentic_dev.cloud_queue import (
    approve_cloud_queue_request,
    create_cloud_queue_request,
    export_cloud_queue_request,
    import_cloud_queue_response,
    show_cloud_queue_request,
)
from agentic_dev.cloud_application.graph import build_runtime_graph_revision
from agentic_dev.cloud_application.models import (
    ActiveRevisionPointer,
    DependencyChange,
    RequirementMapping,
    RollbackMetadata,
    TaskSnapshot,
)
from agentic_dev.cloud_application.persistence import save_active_pointer, save_runtime_revision


STORY = "safe-cloud-response-application-and-local-resume"


def create_story(project_path: Path) -> None:
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
                        "acceptance_criteria": ["AC-001: Validated or approved cloud responses can be applied safely."],
                        "subtasks": [
                            {
                                "id": "source",
                                "title": "Source task",
                                "role": "developer",
                                "depends_on": [],
                                "requirement_ids": ["AC-001"],
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
                                "requirement_ids": ["AC-001"],
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


def bootstrap_runtime_state(project_path: Path) -> None:
    source = TaskSnapshot(
        task_id="source",
        title="Source task",
        role="developer",
        depends_on=(),
        requirement_ids=("AC-001",),
        required_context=("story.md",),
        writable_paths=("runtime/source/**",),
        expected_outputs=("reports/source.md",),
        validation_steps=("pytest -q",),
        token_estimate=1000,
        usable_input_tokens=2000,
        status="blocked",
        history=("bootstrap",),
    )
    audit = TaskSnapshot(
        task_id="audit",
        title="Audit task",
        role="test",
        depends_on=("source",),
        requirement_ids=("AC-001",),
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
        requirement_mappings=[RequirementMapping(requirement_id="AC-001", task_ids=("source", "audit"))],
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


def response_payload(request_id: str, batch_id: str) -> dict[str, object]:
    return {
        "response_id": f"{request_id}-response",
        "request_id": request_id,
        "batch_id": batch_id,
        "response_schema_version": 1,
        "normalized_response": {"summary": "normalized"},
        "raw_response": "raw",
        "checksum": "checksum",
        "decision": "SAFE",
        "claims": {
            "operation_type": "replace_task_with_subtasks",
            "source_task_id": "source",
            "source_plan_revision": "runtime-plan-r0",
            "applicable_requirements": ["AC-001"],
            "writable_paths": ["runtime/app/parser/**", "runtime/app/validator/**"],
            "scope_changes": ["manual approval required for redecomposition"],
            "dependency_status": "resolved",
            "resolved_dependencies": [],
            "safe_to_apply": True,
            "proposed_tasks": [
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
                    "requirement_ids": ["AC-001"],
                    "required_context": ["story.md"],
                    "writable_paths": ["runtime/app/validator/**"],
                    "expected_outputs": ["reports/validator.md"],
                    "validation_steps": ["pytest -q"],
                    "token_estimate": 500,
                    "usable_input_tokens": 2000,
                    "status": "ready",
                },
            ],
            "expected_outputs": ["reports/parser.md", "reports/validator.md"],
            "validation_steps": ["pytest -q"],
        },
        "adapter": "manual_packet",
    }


def prepare_project(project_path: Path) -> str:
    create_story(project_path)
    bootstrap_runtime_state(project_path)
    request = create_cloud_queue_request(
        project_path,
        story=STORY,
        title="CLI target",
        details="details",
        requirements=["AC-001"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
        source_task_id="source",
        source_plan_revision="runtime-plan-r0",
        request_id_factory=lambda: "CQ-CLI-1",
        batch_id_factory=lambda: "batch-cli",
    )
    export_cloud_queue_request(project_path, request_id=request.request.request_id)
    response_path = project_path / "response.yaml"
    response_path.write_text(
        yaml.safe_dump(response_payload(request.request.request_id, request.request.batch_id), sort_keys=False),
        encoding="utf-8",
    )
    import_cloud_queue_response(project_path, response_path)
    approved = show_cloud_queue_request(project_path, request.request.request_id).request
    approve_cloud_queue_request(
        project_path,
        request.request.request_id,
        normalized_response_checksum_value=approved.approval_checksum,
        operator_note="approved",
    )
    return request.request.request_id


def test_cloud_queue_application_cli_commands(monkeypatch) -> None:
    temp_root = (
        Path(os.environ["LOCALAPPDATA"]) / "Temp"
        if os.environ.get("LOCALAPPDATA")
        else Path(os.environ.get("TMPDIR", os.environ.get("TMP", "/tmp")))
    )
    project_path = temp_root / f"story064-cli-{uuid.uuid4().hex[:8]}"
    project_path.mkdir(parents=True, exist_ok=True)

    def run_cli(*args: str) -> str:
        stdout = io.StringIO()
        stderr = io.StringIO()
        previous_argv = sys.argv[:]
        sys.argv = ["agentic", *args]
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                from agentic_dev.cli import main

                main()
        finally:
            sys.argv = previous_argv
        assert stderr.getvalue() == ""
        return stdout.getvalue()

    state_path = project_path / ".agentic" / "cloud_applications" / "execution_state.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("status: completed\n", encoding="utf-8")
    fake_result = SimpleNamespace(
        result=SimpleNamespace(status="completed", state_path=state_path, story_path=project_path / "stories" / STORY),
    )
    monkeypatch.setattr("agentic_dev.cloud_application.service.run_runtime_revision_execution", lambda *args, **kwargs: fake_result)

    request_id = prepare_project(project_path)

    out = run_cli("cloud-queue", "plan-apply", "--project", str(project_path), "--request", request_id)
    assert "Application" in out

    out = run_cli("cloud-queue", "apply", "--project", str(project_path), "--request", request_id)
    assert "Application" in out
    assert "Plan:" in out

    out = run_cli("cloud-queue", "resume", "--project", str(project_path), "--request", request_id)
    assert "Lease IDs:" in out

    application_records = sorted((project_path / ".agentic" / "cloud_applications" / "applications").glob("*.yaml"))
    application_id = next(
        path.stem
        for path in application_records
        if yaml.safe_load(path.read_text(encoding="utf-8")).get("revision_id")
    )
    out = run_cli("cloud-queue", "application-show", "--project", str(project_path), "--application", application_id)
    assert application_id in out

    out = run_cli("cloud-queue", "application-status", "--project", str(project_path))
    assert "Application status:" in out

    out = run_cli("cloud-queue", "rollback", "--project", str(project_path), "--application", application_id)
    assert "rolled_back" in out

    out = run_cli("cloud-queue", "recover", "--project", str(project_path))
    assert "Recovery inspection:" in out
