from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.cloud_batch import build_default_batch_service
from agentic_dev.cloud_queue import create_cloud_queue_request, show_cloud_queue_request


STORY = "story_065_parallel_cloud_batch_orchestration"


def create_story(project_path: Path) -> Path:
    story_path = project_path / "stories" / STORY
    story_path.mkdir(parents=True, exist_ok=True)
    (story_path / "story.md").write_text("# STORY-065\n", encoding="utf-8")
    return story_path


def response_payload(request_id: str, batch_id: str, decision: str = "SAFE") -> dict[str, object]:
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
            "applicable_requirements": ["AC-001"],
            "writable_paths": ["src/agentic_dev/cli.py"],
            "scope_changes": [],
            "dependency_status": "resolved",
            "resolved_dependencies": [],
            "safe_to_apply": True,
            "operation_type": "update_task_metadata",
            "task_metadata": {
                "title": "Updated task",
                "role": "developer",
                "required_context": ["story.md"],
                "writable_paths": ["src/agentic_dev/cli.py"],
                "expected_outputs": ["reports/item.md"],
                "validation_steps": ["pytest -q"],
                "token_estimate": 1000,
                "usable_input_tokens": 2000,
            },
        },
        "adapter": "manual_packet",
    }


def snapshot_tree(project_path: Path) -> dict[str, str]:
    roots = [
        project_path / ".agentic" / "cloud_queue",
        project_path / ".agentic" / "cloud_applications",
        project_path / ".agentic" / "cloud_batches",
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


def test_batch_export_creates_record_and_artifacts(tmp_path: Path) -> None:
    create_story(tmp_path)
    request_a = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Item A",
        details="details",
        requirements=["AC-001"],
        writable_paths=["src/agentic_dev/cli.py"],
        request_id_factory=lambda: "CQ-BATCH-1",
        batch_id_factory=lambda: "batch-source",
    )
    _request_b = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Item B",
        details="details",
        requirements=["AC-001"],
        writable_paths=["docs/cloud_batch_operator_guide.md"],
        request_id_factory=lambda: "CQ-BATCH-2",
        batch_id_factory=lambda: "batch-source",
    )

    service = build_default_batch_service(tmp_path)
    result = service.export(all_ready=True, batch_id="batch-20260621-0001")

    assert result.batch_record.batch_id == "batch-20260621-0001"
    assert result.export_path.exists()
    assert result.batch_record.status == "exported"
    assert set(result.request_ids) == {request_a.request.request_id, _request_b.request.request_id}
    assert service.show("batch-20260621-0001").status == "exported"


def test_batch_import_isolates_malformed_sibling(tmp_path: Path) -> None:
    create_story(tmp_path)
    request_a = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Item A",
        details="details",
        requirements=["AC-001"],
        writable_paths=["src/agentic_dev/cli.py"],
        request_id_factory=lambda: "CQ-BATCH-3",
        batch_id_factory=lambda: "batch-source",
    )
    _request_b = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Item B",
        details="details",
        requirements=["AC-001"],
        writable_paths=["docs/cloud_batch_operator_guide.md"],
        request_id_factory=lambda: "CQ-BATCH-4",
        batch_id_factory=lambda: "batch-source",
    )
    bundle_path = tmp_path / "responses.zip"
    with ZipFile(bundle_path, "w") as archive:
        archive.writestr(
            "valid.yaml",
            yaml.safe_dump(response_payload(request_a.request.request_id, request_a.request.batch_id), sort_keys=False),
        )
        archive.writestr("broken.yaml", ":\n  - not valid yaml\n")

    service = build_default_batch_service(tmp_path)
    service.export(all_ready=True, batch_id="batch-20260621-0002")
    result = service.import_bundle(bundle_path, batch_id="batch-20260621-0002")

    assert result.imported_count == 2
    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.request_ids == (request_a.request.request_id,)
    assert show_cloud_queue_request(tmp_path, request_a.request.request_id).request.state in {"validated_safe", "approval_required", "validated_failed"}


def test_batch_cli_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    create_story(tmp_path)
    create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Item A",
        details="details",
        requirements=["AC-001"],
        writable_paths=["src/agentic_dev/cli.py"],
        request_id_factory=lambda: "CQ-BATCH-CLI-1",
        batch_id_factory=lambda: "batch-source",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "cloud-queue", "batch", "export", "--all-ready", "--batch", "batch-20260621-0003"])
    main()
    export_output = capsys.readouterr().out
    assert "Batch export created:" in export_output

    monkeypatch.setattr("sys.argv", ["agentic", "cloud-queue", "batch", "list"])
    main()
    list_output = capsys.readouterr().out
    assert "Batch status:" in list_output

    monkeypatch.setattr("sys.argv", ["agentic", "cloud-queue", "batch", "show", "--batch", "batch-20260621-0003"])
    main()
    show_output = capsys.readouterr().out
    assert "Batch:" in show_output


def test_batch_plan_apply_dry_run_makes_no_mutation(tmp_path: Path) -> None:
    create_story(tmp_path)
    request = create_cloud_queue_request(
        tmp_path,
        story=STORY,
        title="Item A",
        details="details",
        requirements=["AC-001"],
        writable_paths=["src/agentic_dev/cli.py"],
        request_id_factory=lambda: "CQ-BATCH-DRY-1",
        batch_id_factory=lambda: "batch-source",
    )
    service = build_default_batch_service(tmp_path)
    service.export(all_ready=True, batch_id="batch-20260621-0004")
    response_path = tmp_path / "response.yaml"
    response_path.write_text(
        yaml.safe_dump(response_payload(request.request.request_id, request.request.batch_id), sort_keys=False),
        encoding="utf-8",
    )
    from agentic_dev.cloud_queue import import_cloud_queue_response

    import_cloud_queue_response(tmp_path, response_path)

    before = snapshot_tree(tmp_path)

    result = service.plan_apply("batch-20260621-0004", dry_run=True)

    assert result.status == "planned"
    assert snapshot_tree(tmp_path) == before
