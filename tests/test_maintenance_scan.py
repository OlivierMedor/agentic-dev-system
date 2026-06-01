from pathlib import Path
import socket

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.maintenance_scan import (
    create_maintenance_scan_packet,
    record_maintenance_findings,
)


STORY = "story_022_reactive_maintenance_scan"


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text(
        "# STORY-022\n\nAdd reactive maintenance scan.\n",
        encoding="utf-8",
    )
    return story_path


def write_findings_file(project_path: Path) -> Path:
    findings_path = project_path / "findings.yaml"
    findings_path.write_text(
        """findings:
  - title: Pytest fails after dependency update
    severity: high
    source_type: pytest
    problem: The maintenance scan command exits with a validation error.
    evidence:
      - pytest output shows test_maintenance_scan.py failed.
    suspected_cause: A required findings field was not handled correctly.
    recommended_action: Fix findings validation and rerun the maintenance workflow.
    suggested_acceptance_criteria:
      - maintenance-scan record accepts a valid findings file.
      - maintenance-scan record writes a pending queue item.
""",
        encoding="utf-8",
    )
    return findings_path


def read_yaml(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded or {}


def test_maintenance_scan_create_validates_story_folder_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        create_maintenance_scan_packet(tmp_path, STORY)

    assert STORY in str(error.value)


def test_maintenance_scan_create_writes_packet_and_template(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)

    result = create_maintenance_scan_packet(tmp_path, STORY)

    assert result.story == STORY
    assert result.story_path == story_path
    assert result.packet_path == story_path / "maintenance" / "maintenance_scan_packet.md"
    assert result.template_path == (
        story_path / "maintenance" / "maintenance_findings_template.yaml"
    )
    assert result.packet_path.exists()
    assert result.template_path.exists()


def test_maintenance_scan_packet_includes_story_evidence_and_logs(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    (story_path / "monitoring_plan.yaml").write_text(
        "logs_required: true\nwatch_for:\n  - external_dependency_failure\n",
        encoding="utf-8",
    )
    reports_path = story_path / "reports"
    reports_path.mkdir()
    (reports_path / "quality_gate_result.yaml").write_text(
        "status: READY_FOR_REVIEW\n",
        encoding="utf-8",
    )
    (reports_path / "finalize_story_result.yaml").write_text(
        "status: ready_for_review\n",
        encoding="utf-8",
    )
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir()
    (review_bundle_path / "handoff.md").write_text(
        "# Handoff\n\nReview the failure evidence.\n",
        encoding="utf-8",
    )
    (review_bundle_path / "pytest_output.txt").write_text(
        "1 failed in test_maintenance_scan.py\n",
        encoding="utf-8",
    )
    (review_bundle_path / "ruff_output.txt").write_text(
        "All checks passed!\n",
        encoding="utf-8",
    )
    logs_path = tmp_path / "logs"
    logs_path.mkdir()
    (logs_path / "service.log").write_text(
        "ERROR external API returned 503\n",
        encoding="utf-8",
    )

    create_maintenance_scan_packet(tmp_path, STORY, logs_path=logs_path)

    packet = (story_path / "maintenance" / "maintenance_scan_packet.md").read_text(
        encoding="utf-8",
    )
    assert "Add reactive maintenance scan." in packet
    assert "## Monitoring plan" in packet
    assert "external_dependency_failure" in packet
    assert "## Review bundle handoff" in packet
    assert "Review the failure evidence." in packet
    assert "## pytest output" in packet
    assert "1 failed in test_maintenance_scan.py" in packet
    assert "## ruff output" in packet
    assert "All checks passed!" in packet
    assert "## Quality gate result" in packet
    assert "## Finalize story result" in packet
    assert "### service.log" in packet
    assert "ERROR external API returned 503" in packet


def test_maintenance_scan_packet_instructs_reviewer_to_stay_reactive(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)

    create_maintenance_scan_packet(tmp_path, STORY)

    packet = (story_path / "maintenance" / "maintenance_scan_packet.md").read_text(
        encoding="utf-8",
    )
    assert "identify broken behavior, regressions" in packet
    assert "external dependency failures" in packet
    assert "do not implement fixes" in packet
    assert "Do not call cloud models automatically" in packet
    assert "Do not call internet search" in packet


def test_maintenance_scan_create_does_not_overwrite_existing_files_by_default(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    maintenance_path = story_path / "maintenance"
    maintenance_path.mkdir()
    packet_path = maintenance_path / "maintenance_scan_packet.md"
    packet_path.write_text("keep this packet\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Use --force to overwrite"):
        create_maintenance_scan_packet(tmp_path, STORY)

    assert packet_path.read_text(encoding="utf-8") == "keep this packet\n"


def test_maintenance_scan_create_with_force_regenerates_files(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    maintenance_path = story_path / "maintenance"
    maintenance_path.mkdir()
    packet_path = maintenance_path / "maintenance_scan_packet.md"
    template_path = maintenance_path / "maintenance_findings_template.yaml"
    packet_path.write_text("old packet\n", encoding="utf-8")
    template_path.write_text("old template\n", encoding="utf-8")

    create_maintenance_scan_packet(tmp_path, STORY, force=True)

    assert "old packet" not in packet_path.read_text(encoding="utf-8")
    assert "Maintenance Scan Packet" in packet_path.read_text(encoding="utf-8")
    assert "old template" not in template_path.read_text(encoding="utf-8")
    assert "findings:" in template_path.read_text(encoding="utf-8")


def test_maintenance_scan_create_cli_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "maintenance-scan", "create", "--story", STORY])

    main()

    assert (story_path / "maintenance" / "maintenance_scan_packet.md").exists()


def test_maintenance_scan_create_cli_requires_story_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "maintenance-scan", "create"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_maintenance_scan_record_validates_findings_file_exists(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)

    with pytest.raises(FileNotFoundError, match="findings file does not exist"):
        record_maintenance_findings(tmp_path, STORY, tmp_path / "missing.yaml")


def test_maintenance_scan_record_fails_when_findings_list_is_missing(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    findings_path = tmp_path / "findings.yaml"
    findings_path.write_text("items: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="top-level findings list"):
        record_maintenance_findings(tmp_path, STORY, findings_path)


def test_maintenance_scan_record_fails_when_required_fields_are_missing(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    findings_path = tmp_path / "findings.yaml"
    findings_path.write_text(
        """findings:
  - title: Incomplete finding
    severity: high
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required fields") as error:
        record_maintenance_findings(tmp_path, STORY, findings_path)

    assert "source_type" in str(error.value)
    assert "suggested_acceptance_criteria" in str(error.value)


def test_maintenance_scan_record_creates_pending_queue_item_with_required_fields(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    findings_path = write_findings_file(tmp_path)

    result = record_maintenance_findings(tmp_path, STORY, findings_path)

    assert len(result.queue_items) == 1
    queue_item = result.queue_items[0]
    assert queue_item.item_path.parent == (
        tmp_path.resolve() / ".agentic" / "maintenance_queue" / "pending"
    )
    assert queue_item.item_path.exists()

    item = read_yaml(queue_item.item_path)
    assert item["source_story"] == STORY
    assert item["severity"] == "high"
    assert item["source_type"] == "pytest"
    assert item["problem"] == "The maintenance scan command exits with a validation error."
    assert item["evidence"] == ["pytest output shows test_maintenance_scan.py failed."]
    assert item["suspected_cause"] == "A required findings field was not handled correctly."
    assert item["recommended_action"] == (
        "Fix findings validation and rerun the maintenance workflow."
    )
    assert item["suggested_acceptance_criteria"] == [
        "maintenance-scan record accepts a valid findings file.",
        "maintenance-scan record writes a pending queue item.",
    ]
    assert item["next_action"]


def test_maintenance_scan_record_writes_report(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    findings_path = write_findings_file(tmp_path)

    result = record_maintenance_findings(tmp_path, STORY, findings_path)

    assert result.report_path == story_path / "maintenance" / "maintenance_record_report.md"
    assert result.report_path.exists()
    report = result.report_path.read_text(encoding="utf-8")
    assert "Maintenance Record Report" in report
    assert "Recorded 1 maintenance finding" in report
    assert result.queue_items[0].item_id in report
    assert "did not call cloud models or internet search" in report


def test_maintenance_scan_record_cli_requires_story_and_findings_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "maintenance-scan", "record"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_maintenance_scan_commands_do_not_require_git_repo_or_external_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    create_story(tmp_path)
    findings_path = write_findings_file(tmp_path)

    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access is not allowed in this command.")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket, "socket", fail_network)

    monkeypatch.setattr("sys.argv", ["agentic", "maintenance-scan", "create", "--story", STORY])
    main()
    create_output = capsys.readouterr().out

    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "maintenance-scan",
            "record",
            "--story",
            STORY,
            "--findings-file",
            str(findings_path),
        ],
    )
    main()
    record_output = capsys.readouterr().out

    assert "Maintenance scan packet created" in create_output
    assert "Maintenance findings recorded" in record_output
    assert not (tmp_path / ".git").exists()
    assert (tmp_path / ".agentic" / "maintenance_queue" / "pending").exists()
