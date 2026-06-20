from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main


STORY = "story_063_structured_cloud_escalation_and_manual_packet_queue"


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# STORY-063\n", encoding="utf-8")
    return story_path


def write_response_yaml(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_cloud_queue_cli_create_list_show_export_import_approve_reject_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    create_story(tmp_path)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "cloud-queue",
            "create",
            "--story",
            STORY,
            "--title",
            "CLI request",
            "--details",
            "CLI details",
            "--requirement",
            "AC-001",
            "--writable-path",
            "src/agentic_dev/cloud_queue/service.py",
        ],
    )
    main()
    create_output = capsys.readouterr().out
    assert "Cloud queue request created:" in create_output

    request_path = next((tmp_path / ".agentic" / "cloud_queue" / "requests" / "ready").glob("*.yaml"))
    request_id = request_path.stem

    monkeypatch.setattr("sys.argv", ["agentic", "cloud-queue", "list", "--json"])
    main()
    list_output = capsys.readouterr().out
    assert '"state": "ready"' in list_output

    monkeypatch.setattr("sys.argv", ["agentic", "cloud-queue", "show", "--request", request_id])
    main()
    show_output = capsys.readouterr().out
    assert "Cloud queue request:" in show_output
    assert request_id in show_output

    monkeypatch.setattr("sys.argv", ["agentic", "cloud-queue", "export", "--request", request_id])
    main()
    export_output = capsys.readouterr().out
    assert "Cloud queue export created:" in export_output

    response_path = write_response_yaml(
        tmp_path / "response.yaml",
        {
            "response_id": f"{request_id}-response",
            "request_id": request_id,
            "batch_id": "batch-1",
            "response_schema_version": 1,
            "normalized_response": {"summary": "normalized"},
            "raw_response": "raw",
            "checksum": "checksum",
            "decision": "APPROVAL_REQUIRED",
            "claims": {
                "applicable_requirements": ["AC-001"],
                "writable_paths": [
                    "src/agentic_dev/cloud_queue/service.py",
                    "docs/cloud_queue_operator_guide.md",
                ],
                "scope_changes": ["docs"],
                "dependency_status": "resolved",
                "resolved_dependencies": [],
                "safe_to_apply": False,
            },
            "adapter": "manual_packet",
        },
    )

    monkeypatch.setattr("sys.argv", ["agentic", "cloud-queue", "import", "--file", str(response_path)])
    main()
    import_output = capsys.readouterr().out
    assert "Cloud queue import complete:" in import_output

    approval_request_path = next(
        (tmp_path / ".agentic" / "cloud_queue" / "requests" / "approval_required").glob("*.yaml")
    )
    approval_request = yaml.safe_load(approval_request_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "cloud-queue",
            "approve",
            "--request",
            approval_request["request_id"],
            "--checksum",
            approval_request["approval_checksum"],
            "--note",
            "matches",
        ],
    )
    main()
    approve_output = capsys.readouterr().out
    assert "Cloud queue request approved:" in approve_output

    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "cloud-queue", "reject", "--request", approval_request["request_id"], "--note", "not now"],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1

    monkeypatch.setattr("sys.argv", ["agentic", "cloud-queue", "status", "--json"])
    main()
    status_output = capsys.readouterr().out
    assert '"request_count":' in status_output
