from pathlib import Path
import socket

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.feature_scan import (
    create_feature_scan_packet,
    record_feature_suggestions,
)


def write_project_context(project_path: Path) -> None:
    (project_path / ".agentic").mkdir()
    (project_path / ".agentic" / "project.yaml").write_text(
        """project:
  name: Sample Agentic Project
""",
        encoding="utf-8",
    )
    (project_path / "blueprints").mkdir()
    (project_path / "blueprints" / "blueprint.yaml").write_text(
        """project:
  name: Sample Agentic Project
  type: cli-tool
  description: Helps agents plan and review local development work.
stories:
  - id: STORY-001
    slug: story_001_project_setup
    title: Set up the project workflow
""",
        encoding="utf-8",
    )
    (project_path / "README.md").write_text(
        """# Sample Agentic Project

This README explains the command workflow and review process.
""",
        encoding="utf-8",
    )
    docs_path = project_path / "docs"
    docs_path.mkdir()
    (docs_path / "roadmap.md").write_text(
        "# Roadmap\n\nAdd better project-level planning loops.\n",
        encoding="utf-8",
    )
    story_path = project_path / "stories" / "story_001_project_setup"
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# STORY-001\n\nSet up workflow.\n", encoding="utf-8")


def write_existing_queue_items(project_path: Path) -> None:
    improvement_pending = project_path / ".agentic" / "improvement_queue" / "pending"
    improvement_pending.mkdir(parents=True)
    (improvement_pending / "IMP-001.yaml").write_text(
        "id: IMP-001\ntitle: Improve docs\n",
        encoding="utf-8",
    )
    feature_pending = project_path / ".agentic" / "feature_queue" / "pending"
    feature_pending.mkdir(parents=True)
    (feature_pending / "FEATURE-001.yaml").write_text(
        """id: FEATURE-001
queue_type: feature
title: Add portfolio view
source_story: project_feature_scan
category: planning
priority: medium
status: pending
""",
        encoding="utf-8",
    )


def write_suggestions_file(project_path: Path) -> Path:
    suggestions_path = project_path / "feature_suggestions.yaml"
    suggestions_path.write_text(
        """suggestions:
  - title: Add project feature dashboard
    category: usability
    priority: medium
    details: Show feature suggestions and queue status in one command.
    expected_benefit: Reviewers can prioritize project-level ideas faster.
    strategic_fit: Supports recurring project planning without automatic implementation.
    evidence:
      - "Project-derived observation: queue data is already structured."
    source_urls:
      - https://example.com/research-note
    suggested_acceptance_criteria:
      - Show feature queue counts in the dashboard.
      - Link each pending feature suggestion to its queue item.
""",
        encoding="utf-8",
    )
    return suggestions_path


def read_yaml(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded or {}


def test_feature_scan_create_writes_packet_and_template(tmp_path: Path) -> None:
    result = create_feature_scan_packet(tmp_path)

    assert result.project_path == tmp_path.resolve()
    assert result.feature_scan_path == tmp_path.resolve() / ".agentic" / "feature_scan"
    assert result.packet_path == (
        tmp_path.resolve() / ".agentic" / "feature_scan" / "feature_scan_packet.md"
    )
    assert result.template_path == (
        tmp_path.resolve() / ".agentic" / "feature_scan" / "feature_suggestions_template.yaml"
    )
    assert result.packet_path.exists()
    assert result.template_path.exists()


def test_feature_scan_packet_includes_project_context_when_present(tmp_path: Path) -> None:
    write_project_context(tmp_path)
    write_existing_queue_items(tmp_path)

    result = create_feature_scan_packet(tmp_path, focus="agent workflow automation")

    packet = result.packet_path.read_text(encoding="utf-8")
    assert "Sample Agentic Project" in packet
    assert "Helps agents plan and review local development work." in packet
    assert "Set up the project workflow" in packet
    assert "This README explains the command workflow" in packet
    assert "docs/roadmap.md" in packet
    assert "Add better project-level planning loops." in packet
    assert "- improvement: total=1" in packet
    assert "- feature: total=1" in packet
    assert "FEATURE-001 | priority=medium | category=planning | title=Add portfolio view" in packet
    assert "agent workflow automation" in packet


def test_feature_scan_packet_instructs_reviewer_to_stay_in_scope(
    tmp_path: Path,
) -> None:
    result = create_feature_scan_packet(tmp_path)

    packet = result.packet_path.read_text(encoding="utf-8")
    assert "suggest project-level new features" in packet
    assert "do not implement features" in packet
    assert "do not create stories" in packet
    assert "Do not call cloud models automatically" in packet
    assert "Do not call internet search automatically" in packet
    assert "if internet research is available" in packet
    assert "clearly separate Project-derived observations" in packet
    assert "External/internet-derived observations" in packet
    assert "do not invent sources" in packet
    assert "do not claim internet research was performed if it was not performed" in packet


def test_feature_scan_create_does_not_overwrite_existing_files_by_default(
    tmp_path: Path,
) -> None:
    feature_scan_path = tmp_path / ".agentic" / "feature_scan"
    feature_scan_path.mkdir(parents=True)
    packet_path = feature_scan_path / "feature_scan_packet.md"
    packet_path.write_text("keep this packet\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Use --force to overwrite"):
        create_feature_scan_packet(tmp_path)

    assert packet_path.read_text(encoding="utf-8") == "keep this packet\n"


def test_feature_scan_create_with_force_regenerates_files(tmp_path: Path) -> None:
    feature_scan_path = tmp_path / ".agentic" / "feature_scan"
    feature_scan_path.mkdir(parents=True)
    packet_path = feature_scan_path / "feature_scan_packet.md"
    template_path = feature_scan_path / "feature_suggestions_template.yaml"
    packet_path.write_text("old packet\n", encoding="utf-8")
    template_path.write_text("old template\n", encoding="utf-8")

    create_feature_scan_packet(tmp_path, force=True)

    assert "old packet" not in packet_path.read_text(encoding="utf-8")
    assert "Project Feature Discovery Scan Packet" in packet_path.read_text(encoding="utf-8")
    assert "old template" not in template_path.read_text(encoding="utf-8")
    assert "strategic_fit:" in template_path.read_text(encoding="utf-8")


def test_feature_scan_create_cli_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "feature-scan", "create"])

    main()

    assert (tmp_path / ".agentic" / "feature_scan" / "feature_scan_packet.md").exists()
    assert (tmp_path / ".agentic" / "feature_scan" / "feature_suggestions_template.yaml").exists()


def test_feature_scan_record_cli_requires_suggestions_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "feature-scan", "record"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_feature_scan_record_validates_suggestions_file_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="suggestions file does not exist"):
        record_feature_suggestions(tmp_path, tmp_path / "missing.yaml")


def test_feature_scan_record_fails_when_suggestions_list_is_missing(
    tmp_path: Path,
) -> None:
    suggestions_path = tmp_path / "feature_suggestions.yaml"
    suggestions_path.write_text("items: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="top-level suggestions list"):
        record_feature_suggestions(tmp_path, suggestions_path)


def test_feature_scan_record_fails_when_required_fields_are_missing(
    tmp_path: Path,
) -> None:
    suggestions_path = tmp_path / "feature_suggestions.yaml"
    suggestions_path.write_text(
        """suggestions:
  - title: Incomplete suggestion
    category: usability
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required fields") as error:
        record_feature_suggestions(tmp_path, suggestions_path)

    assert "priority" in str(error.value)
    assert "strategic_fit" in str(error.value)
    assert "suggested_acceptance_criteria" in str(error.value)


def test_feature_scan_record_creates_pending_queue_item_with_required_fields(
    tmp_path: Path,
) -> None:
    suggestions_path = write_suggestions_file(tmp_path)

    result = record_feature_suggestions(tmp_path, suggestions_path)

    assert len(result.queue_items) == 1
    queue_item = result.queue_items[0]
    assert queue_item.item_path.parent == (
        tmp_path.resolve() / ".agentic" / "feature_queue" / "pending"
    )
    assert queue_item.item_path.exists()

    item = read_yaml(queue_item.item_path)
    assert item["queue_type"] == "feature"
    assert item["source_story"] == "project_feature_scan"
    assert item["title"] == "Add project feature dashboard"
    assert item["category"] == "usability"
    assert item["priority"] == "medium"
    assert item["details"] == "Show feature suggestions and queue status in one command."
    assert item["expected_benefit"] == "Reviewers can prioritize project-level ideas faster."
    assert item["strategic_fit"] == (
        "Supports recurring project planning without automatic implementation."
    )
    assert item["evidence"] == [
        "Project-derived observation: queue data is already structured.",
    ]
    assert item["source_urls"] == ["https://example.com/research-note"]
    assert item["suggested_acceptance_criteria"] == [
        "Show feature queue counts in the dashboard.",
        "Link each pending feature suggestion to its queue item.",
    ]
    assert item["next_action"]


def test_feature_scan_record_writes_report(tmp_path: Path) -> None:
    suggestions_path = write_suggestions_file(tmp_path)

    result = record_feature_suggestions(tmp_path, suggestions_path)

    assert result.report_path == (
        tmp_path.resolve() / ".agentic" / "feature_scan" / "feature_record_report.md"
    )
    assert result.report_path.exists()
    report = result.report_path.read_text(encoding="utf-8")
    assert "Feature Record Report" in report
    assert "Recorded 1 feature suggestion" in report
    assert result.queue_items[0].item_id in report
    assert "did not implement suggestions" in report
    assert "did not call cloud models or internet search" in report


def test_feature_scan_commands_do_not_require_git_repo_or_external_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    suggestions_path = write_suggestions_file(tmp_path)

    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access is not allowed in this command.")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket, "socket", fail_network)

    monkeypatch.setattr("sys.argv", ["agentic", "feature-scan", "create"])
    main()
    create_output = capsys.readouterr().out

    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "feature-scan",
            "record",
            "--suggestions-file",
            str(suggestions_path),
        ],
    )
    main()
    record_output = capsys.readouterr().out

    assert "Feature scan packet created" in create_output
    assert "Feature suggestions recorded" in record_output
    assert not (tmp_path / ".git").exists()
    assert (tmp_path / ".agentic" / "feature_queue" / "pending").exists()
