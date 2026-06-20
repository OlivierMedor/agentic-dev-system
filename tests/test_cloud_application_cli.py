from __future__ import annotations

import os
import sys
import uuid
import contextlib
import io
from pathlib import Path

import yaml

from agentic_dev.cloud_queue import (
    approve_cloud_queue_request,
    create_cloud_queue_request,
    export_cloud_queue_request,
    import_cloud_queue_response,
    show_cloud_queue_request,
)


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
    request = create_cloud_queue_request(
        project_path,
        story=STORY,
        title="CLI target",
        details="details",
        requirements=["AC-001"],
        writable_paths=["runtime/app/parser/**", "runtime/app/validator/**"],
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


def test_cloud_queue_application_cli_commands(
) -> None:
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
