from pathlib import Path
import socket

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.improvement_scan import (
    create_improvement_scan_packet,
    record_improvement_suggestions,
)


STORY = "story_021_post_story_improvement_scan"


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text(
        "# STORY-021\n\nAdd post-story improvement scan.\n",
        encoding="utf-8",
    )
    return story_path


def write_suggestions_file(project_path: Path) -> Path:
    suggestions_path = project_path / "suggestions.yaml"
    suggestions_path.write_text(
        """suggestions:
  - title: Clarify validation messages
    category: maintainability
    priority: medium
    details: Make invalid suggestion files easier to fix.
    expected_benefit: Reviewers can correct YAML mistakes faster.
    suggested_acceptance_criteria:
      - Missing fields identify the exact suggestion number.
      - The README includes one invalid YAML troubleshooting example.
""",
        encoding="utf-8",
    )
    return suggestions_path


def read_yaml(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded or {}


def test_improvement_scan_create_validates_story_folder_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        create_improvement_scan_packet(tmp_path, STORY)

    assert STORY in str(error.value)


def test_improvement_scan_create_writes_packet_and_template(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)

    result = create_improvement_scan_packet(tmp_path, STORY)

    assert result.story == STORY
    assert result.story_path == story_path
    assert result.packet_path == story_path / "improvements" / "improvement_scan_packet.md"
    assert result.template_path == (
        story_path / "improvements" / "improvement_suggestions_template.yaml"
    )
    assert result.packet_path.exists()
    assert result.template_path.exists()


def test_improvement_scan_packet_includes_story_and_present_evidence(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    reports_path = story_path / "reports"
    reports_path.mkdir()
    (reports_path / "test_layer_result.yaml").write_text(
        "status: passed\nunit_tests: covered\n",
        encoding="utf-8",
    )
    (reports_path / "finalize_story_result.yaml").write_text(
        "status: ready_for_review\n",
        encoding="utf-8",
    )
    (reports_path / "local_review_report.md").write_text(
        "# Local Review\n\nNo blocking issues.\n",
        encoding="utf-8",
    )
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir()
    (review_bundle_path / "handoff.md").write_text(
        "# Handoff\n\nReady for review.\n",
        encoding="utf-8",
    )

    create_improvement_scan_packet(tmp_path, STORY)

    packet = (story_path / "improvements" / "improvement_scan_packet.md").read_text(
        encoding="utf-8",
    )
    assert "Add post-story improvement scan." in packet
    assert "## Test layer result" in packet
    assert "unit_tests: covered" in packet
    assert "## Finalize story result" in packet
    assert "status: ready_for_review" in packet
    assert "## Local review report" in packet
    assert "No blocking issues." in packet
    assert "## Review bundle handoff" in packet
    assert "Ready for review." in packet


def test_improvement_scan_packet_instructs_reviewer_to_stay_in_scope(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)

    create_improvement_scan_packet(tmp_path, STORY)

    packet = (story_path / "improvements" / "improvement_scan_packet.md").read_text(
        encoding="utf-8",
    )
    assert "suggest improvements only within this story's scope" in packet
    assert "do not propose unrelated features" in packet
    assert "Do not call cloud models automatically" in packet
    assert "Do not call internet search" in packet


def test_improvement_scan_create_does_not_overwrite_existing_files_by_default(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    improvements_path = story_path / "improvements"
    improvements_path.mkdir()
    packet_path = improvements_path / "improvement_scan_packet.md"
    packet_path.write_text("keep this packet\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Use --force to overwrite"):
        create_improvement_scan_packet(tmp_path, STORY)

    assert packet_path.read_text(encoding="utf-8") == "keep this packet\n"


def test_improvement_scan_create_with_force_regenerates_files(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    improvements_path = story_path / "improvements"
    improvements_path.mkdir()
    packet_path = improvements_path / "improvement_scan_packet.md"
    template_path = improvements_path / "improvement_suggestions_template.yaml"
    packet_path.write_text("old packet\n", encoding="utf-8")
    template_path.write_text("old template\n", encoding="utf-8")

    create_improvement_scan_packet(tmp_path, STORY, force=True)

    assert "old packet" not in packet_path.read_text(encoding="utf-8")
    assert "Improvement Scan Packet" in packet_path.read_text(encoding="utf-8")
    assert "old template" not in template_path.read_text(encoding="utf-8")
    assert "suggestions:" in template_path.read_text(encoding="utf-8")


def test_improvement_scan_create_cli_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "improvement-scan", "create", "--story", STORY])

    main()

    assert (story_path / "improvements" / "improvement_scan_packet.md").exists()


def test_improvement_scan_create_cli_requires_story_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "improvement-scan", "create"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_improvement_scan_record_validates_suggestions_file_exists(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)

    with pytest.raises(FileNotFoundError, match="suggestions file does not exist"):
        record_improvement_suggestions(tmp_path, STORY, tmp_path / "missing.yaml")


def test_improvement_scan_record_fails_when_suggestions_list_is_missing(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    suggestions_path = tmp_path / "suggestions.yaml"
    suggestions_path.write_text("items: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="top-level suggestions list"):
        record_improvement_suggestions(tmp_path, STORY, suggestions_path)


def test_improvement_scan_record_fails_when_required_fields_are_missing(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    suggestions_path = tmp_path / "suggestions.yaml"
    suggestions_path.write_text(
        """suggestions:
  - title: Incomplete suggestion
    category: testing
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required fields") as error:
        record_improvement_suggestions(tmp_path, STORY, suggestions_path)

    assert "priority" in str(error.value)
    assert "suggested_acceptance_criteria" in str(error.value)


def test_improvement_scan_record_creates_pending_queue_item_with_required_fields(
    tmp_path: Path,
) -> None:
    create_story(tmp_path)
    suggestions_path = write_suggestions_file(tmp_path)

    result = record_improvement_suggestions(tmp_path, STORY, suggestions_path)

    assert len(result.queue_items) == 1
    queue_item = result.queue_items[0]
    assert queue_item.item_path.parent == (
        tmp_path.resolve() / ".agentic" / "improvement_queue" / "pending"
    )
    assert queue_item.item_path.exists()

    item = read_yaml(queue_item.item_path)
    assert item["source_story"] == STORY
    assert item["title"] == "Clarify validation messages"
    assert item["category"] == "maintainability"
    assert item["priority"] == "medium"
    assert item["details"] == "Make invalid suggestion files easier to fix."
    assert item["expected_benefit"] == "Reviewers can correct YAML mistakes faster."
    assert item["suggested_acceptance_criteria"] == [
        "Missing fields identify the exact suggestion number.",
        "The README includes one invalid YAML troubleshooting example.",
    ]
    assert item["next_action"]


def test_improvement_scan_record_writes_report(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    suggestions_path = write_suggestions_file(tmp_path)

    result = record_improvement_suggestions(tmp_path, STORY, suggestions_path)

    assert result.report_path == story_path / "improvements" / "improvement_record_report.md"
    assert result.report_path.exists()
    report = result.report_path.read_text(encoding="utf-8")
    assert "Improvement Record Report" in report
    assert "Recorded 1 improvement suggestion" in report
    assert result.queue_items[0].item_id in report
    assert "did not call cloud models or internet search" in report


def test_improvement_scan_record_cli_requires_story_and_suggestions_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "improvement-scan", "record"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_improvement_scan_commands_do_not_require_git_repo_or_external_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    create_story(tmp_path)
    suggestions_path = write_suggestions_file(tmp_path)

    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access is not allowed in this command.")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket, "socket", fail_network)

    monkeypatch.setattr("sys.argv", ["agentic", "improvement-scan", "create", "--story", STORY])
    main()
    create_output = capsys.readouterr().out

    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "improvement-scan",
            "record",
            "--story",
            STORY,
            "--suggestions-file",
            str(suggestions_path),
        ],
    )
    main()
    record_output = capsys.readouterr().out

    assert "Improvement scan packet created" in create_output
    assert "Improvement suggestions recorded" in record_output
    assert not (tmp_path / ".git").exists()
    assert (tmp_path / ".agentic" / "improvement_queue" / "pending").exists()
