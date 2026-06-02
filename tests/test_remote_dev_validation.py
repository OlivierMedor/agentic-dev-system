from pathlib import Path
from typing import Any

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.remote_dev_validation import (
    create_remote_dev_packet,
    record_remote_dev_validation,
)


STORY = "story_024_remote_dev_validation_bundle"
PRESERVED_STORY_ID = "STORY-024"


def create_story(project_path: Path, story_content: str = "# STORY-024\n") -> Path:
    story_path = project_path / "stories" / STORY
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text(story_content, encoding="utf-8")
    (story_path / "status.yaml").write_text(
        yaml.safe_dump(
            {
                "story_id": PRESERVED_STORY_ID,
                "status": "ready_for_review",
                "ready_for_review": True,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return story_path


def write_result_file(
    path: Path,
    validation_status: str = "DEV_VALIDATED",
    extra_fields: dict[str, Any] | None = None,
) -> Path:
    data: dict[str, Any] = {
        "validation_status": validation_status,
        "environment_name": "remote-dev",
        "deployment_url": "https://remote-dev.example.test",
        "branch_or_commit": "story-024-test-sha",
        "validated_by": "test-agent",
        "validation_notes": "Remote dev evidence was reviewed.",
        "smoke_tests": {
            "status": "passed",
            "evidence": ["Opened the validation route."],
        },
        "integration_tests": {
            "status": "not_run",
            "evidence": ["No remote integration target exists yet."],
        },
        "logs_review": {
            "status": "passed",
            "evidence": ["No critical errors found."],
        },
        "environment_checklist": {
            "status": "passed",
            "notes": "Only variable names were checked; secret values were not exposed.",
        },
        "rollback_notes": "Revert the story branch if validation fails.",
        "known_risks": ["Remote environment is a test double."],
        "next_action": "Human owner reviews the evidence.",
    }
    if extra_fields:
        data.update(extra_fields)

    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def read_packet(story_path: Path) -> str:
    return (story_path / "remote_dev_validation" / "remote_dev_packet.md").read_text(
        encoding="utf-8",
    )


def test_remote_dev_packet_validates_story_folder_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        create_remote_dev_packet(tmp_path, STORY)

    assert STORY in str(error.value)


def test_remote_dev_packet_creates_packet_and_template(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)

    result = create_remote_dev_packet(tmp_path, STORY)

    validation_path = story_path / "remote_dev_validation"
    packet_path = validation_path / "remote_dev_packet.md"
    template_path = validation_path / "remote_dev_result_template.yaml"

    assert result.story == STORY
    assert result.validation_path == validation_path
    assert result.packet_path == packet_path
    assert result.template_path == template_path
    assert {path.name for path in result.generated_files} == {
        "remote_dev_packet.md",
        "remote_dev_result_template.yaml",
    }
    assert packet_path.exists()
    assert template_path.exists()
    assert (validation_path / ".gitkeep").exists()


def test_remote_dev_packet_includes_story_content_and_required_instructions(
    tmp_path: Path,
) -> None:
    story_content = "# STORY-024\n\nRemote dev validation acceptance criteria.\n"
    story_path = create_story(tmp_path, story_content=story_content)

    create_remote_dev_packet(tmp_path, STORY)

    packet = read_packet(story_path)
    assert "Remote dev validation acceptance criteria." in packet
    assert "## Remote dev evidence to collect" in packet
    assert "## Smoke test checklist" in packet
    assert "## Integration test checklist" in packet
    assert "## Log review checklist" in packet
    assert "## Environment variable checklist" in packet
    assert "## Rollback notes" in packet
    assert "## Known risks" in packet
    assert "Do not expose secrets" in packet
    assert "Do not mark DEV_VALIDATED if checks were not actually performed." in packet
    assert "It does not deploy, commit, push, merge, call GitHub APIs, or call cloud models." in packet


def test_remote_dev_packet_includes_present_story_evidence(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    reports_path = story_path / "reports"
    reports_path.mkdir()
    (story_path / "test_plan.yaml").write_text("unit_tests:\n  required: true\n", encoding="utf-8")
    (story_path / "monitoring_plan.yaml").write_text(
        "logs_required: true\nwatch_for:\n  - remote_dev_failed\n",
        encoding="utf-8",
    )
    (reports_path / "quality_gate_result.yaml").write_text(
        "status: READY_FOR_REVIEW\nready_for_review: true\n",
        encoding="utf-8",
    )
    (reports_path / "finalize_story_result.yaml").write_text(
        "status: ready_for_review\n",
        encoding="utf-8",
    )
    (reports_path / "cloud_review_result.yaml").write_text(
        "decision: APPROVE_WITH_NOTES\n",
        encoding="utf-8",
    )
    (reports_path / "merge_readiness_result.yaml").write_text(
        "status: READY_FOR_HUMAN_MERGE_DECISION\n",
        encoding="utf-8",
    )

    create_remote_dev_packet(tmp_path, STORY)

    packet = read_packet(story_path)
    assert "## Test plan" in packet
    assert "unit_tests:" in packet
    assert "## Monitoring plan" in packet
    assert "remote_dev_failed" in packet
    assert "## Quality gate result" in packet
    assert "status: READY_FOR_REVIEW" in packet
    assert "## Finalize story result" in packet
    assert "status: ready_for_review" in packet
    assert "## Cloud review result" in packet
    assert "decision: APPROVE_WITH_NOTES" in packet
    assert "## Merge readiness result" in packet
    assert "READY_FOR_HUMAN_MERGE_DECISION" in packet


def test_remote_dev_packet_does_not_overwrite_existing_files_by_default(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    validation_path = story_path / "remote_dev_validation"
    validation_path.mkdir()
    packet_path = validation_path / "remote_dev_packet.md"
    packet_path.write_text("keep this packet\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Use --force to overwrite"):
        create_remote_dev_packet(tmp_path, STORY)

    assert packet_path.read_text(encoding="utf-8") == "keep this packet\n"


def test_remote_dev_packet_force_regenerates_existing_files(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    validation_path = story_path / "remote_dev_validation"
    validation_path.mkdir()
    packet_path = validation_path / "remote_dev_packet.md"
    packet_path.write_text("old packet\n", encoding="utf-8")
    template_path = validation_path / "remote_dev_result_template.yaml"
    template_path.write_text("old template\n", encoding="utf-8")

    create_remote_dev_packet(tmp_path, STORY, force=True)

    packet = packet_path.read_text(encoding="utf-8")
    template = template_path.read_text(encoding="utf-8")
    assert "old packet" not in packet
    assert "Remote Dev Validation Packet" in packet
    assert "old template" not in template
    assert "validation_status: DEV_VALIDATED" in template


def test_record_remote_dev_validates_result_file_exists(tmp_path: Path) -> None:
    create_story(tmp_path)

    with pytest.raises(FileNotFoundError, match="Remote dev validation result file does not exist"):
        record_remote_dev_validation(tmp_path, STORY, tmp_path / "missing_result.yaml")


def test_record_remote_dev_rejects_invalid_validation_status(tmp_path: Path) -> None:
    create_story(tmp_path)
    result_file = write_result_file(tmp_path / "remote_result.yaml", "MAYBE_VALID")

    with pytest.raises(ValueError, match="Invalid remote dev validation_status"):
        record_remote_dev_validation(tmp_path, STORY, result_file)


@pytest.mark.parametrize(
    ("validation_status", "expected_status", "expected_ready_for_review"),
    [
        ("DEV_VALIDATED", "remote_dev_validated", True),
        ("DEV_VALIDATED_WITH_NOTES", "remote_dev_validated_with_notes", True),
        ("DEV_FAILED", "remote_dev_failed", False),
        ("NOT_RUN", "remote_dev_not_run", False),
    ],
)
def test_record_remote_dev_accepts_statuses_and_updates_story_status(
    tmp_path: Path,
    validation_status: str,
    expected_status: str,
    expected_ready_for_review: bool,
) -> None:
    story_path = create_story(tmp_path)
    result_file = write_result_file(tmp_path / "remote_result.yaml", validation_status)

    result = record_remote_dev_validation(tmp_path, STORY, result_file)

    result_yaml_path = story_path / "reports" / "remote_dev_validation_result.yaml"
    report_path = story_path / "reports" / "remote_dev_validation_report.md"
    status_path = story_path / "status.yaml"

    assert result.validation_status == validation_status
    assert result.ready_for_review is expected_ready_for_review
    assert result.result_path == result_yaml_path
    assert result.report_path == report_path
    assert result.status_path == status_path
    assert result_yaml_path.exists()
    assert report_path.exists()

    result_yaml = yaml.safe_load(result_yaml_path.read_text(encoding="utf-8"))
    assert result_yaml["story"] == STORY
    assert result_yaml["validation_status"] == validation_status
    assert result_yaml["ready_for_review"] is expected_ready_for_review

    report = report_path.read_text(encoding="utf-8")
    assert "# Remote Dev Validation Report" in report
    assert validation_status in report
    assert "This command did not deploy, commit, push, merge, call GitHub APIs, or call cloud models." in report

    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    assert status["story_id"] == PRESERVED_STORY_ID
    assert status["status"] == expected_status
    assert status["ready_for_review"] is expected_ready_for_review
    assert status["remote_dev_validation_status"] == validation_status


def test_cli_remote_dev_packet_requires_story_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "remote-dev-packet"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_record_remote_dev_requires_story_argument(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result_file = write_result_file(tmp_path / "remote_result.yaml")
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "record-remote-dev", "--result-file", str(result_file)],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_record_remote_dev_requires_result_file_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "record-remote-dev", "--story", STORY])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_commands_default_project_to_cwd_and_do_not_need_real_git_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    result_file = write_result_file(tmp_path / "remote_result.yaml", "DEV_VALIDATED")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    monkeypatch.setattr("sys.argv", ["agentic", "remote-dev-packet", "--story", STORY])
    main()
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "record-remote-dev", "--story", STORY, "--result-file", str(result_file)],
    )
    main()

    assert not (tmp_path / ".git").exists()
    assert (story_path / "remote_dev_validation" / "remote_dev_packet.md").exists()
    assert (story_path / "remote_dev_validation" / "remote_dev_result_template.yaml").exists()
    assert (story_path / "reports" / "remote_dev_validation_result.yaml").exists()
    assert (story_path / "reports" / "remote_dev_validation_report.md").exists()


def test_remote_dev_commands_do_not_shell_out_to_git_deploy_or_cloud_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    result_file = write_result_file(tmp_path / "remote_result.yaml", "DEV_VALIDATED")

    def fail_if_subprocess_is_used(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("remote dev validation should not run external commands")

    monkeypatch.setattr("subprocess.run", fail_if_subprocess_is_used)

    create_remote_dev_packet(tmp_path, STORY)
    record_remote_dev_validation(tmp_path, STORY, result_file)

    assert (story_path / "remote_dev_validation" / "remote_dev_packet.md").exists()
    assert (story_path / "reports" / "remote_dev_validation_result.yaml").exists()
