from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.prepare_story import prepare_story


STORY = "story_007_prepare_story_command"


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text(
        "# Prepare Story\n\nPrepare this story for agent work.\n",
        encoding="utf-8",
    )
    (story_path / "test_plan.yaml").write_text(
        "unit_tests: true\n",
        encoding="utf-8",
    )
    (story_path / "monitoring_plan.yaml").write_text(
        "watch_for:\n  - missing_prompt_pack\n",
        encoding="utf-8",
    )
    (story_path / "status.yaml").write_text(
        "story_id: story_007_prepare_story_command\n"
        "status: planned\n"
        "ready_for_review: true\n"
        "notes: keep this field\n",
        encoding="utf-8",
    )
    return story_path


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_prepare_story_creates_agent_plan_prompt_pack_runbook_report_and_status(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)

    result = prepare_story(tmp_path, STORY)

    assert result.agent_plan_path == story_path / "agent_plan.yaml"
    assert result.prompt_pack_path == story_path / "prompt_pack"
    assert result.runbook_path == story_path / "story_runbook.md"
    assert result.report_path == story_path / "reports" / "prepare_story_report.md"
    assert result.status_path == story_path / "status.yaml"

    assert result.agent_plan_path.exists()
    assert len(list(result.prompt_pack_path.glob("*_prompt.md"))) == 7
    assert result.runbook_path.exists()
    assert result.report_path.exists()

    status = read_yaml(result.status_path)
    assert status["story_id"] == STORY
    assert status["status"] == "prepared"
    assert status["ready_for_review"] is False
    assert status["notes"] == "keep this field"


def test_prepare_story_output_says_agents_models_review_bundle_and_quality_gate_do_not_run(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)

    prepare_story(tmp_path, STORY)

    report = (story_path / "reports" / "prepare_story_report.md").read_text(
        encoding="utf-8",
    )
    runbook = (story_path / "story_runbook.md").read_text(encoding="utf-8")

    assert "Agents were not executed." in report
    assert "Cloud models were not run." in report
    assert "Review bundle was not created." in report
    assert "Quality gate was not run." in report
    assert "docker compose run --rm dev agentic review-bundle" in runbook
    assert "docker compose run --rm dev agentic quality-gate" in runbook
    assert not (story_path / "review_bundle").exists()
    assert not (story_path / "reports" / "quality_gate_result.yaml").exists()
    assert not (story_path / "reports" / "quality_gate_report.md").exists()


def test_missing_story_folder_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        prepare_story(tmp_path, STORY)

    assert STORY in str(error.value)


def test_force_refreshes_agent_plan_and_prompt_files(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    prepare_story(tmp_path, STORY)

    agent_plan_path = story_path / "agent_plan.yaml"
    prompt_path = story_path / "prompt_pack" / "03_developer_agent_prompt.md"
    agent_plan_path.write_text("custom: replace me\n", encoding="utf-8")
    prompt_path.write_text("custom prompt content\n", encoding="utf-8")

    result = prepare_story(tmp_path, STORY, force=True)

    assert "custom: replace me" not in agent_plan_path.read_text(encoding="utf-8")
    assert "custom prompt content" not in prompt_path.read_text(encoding="utf-8")
    assert prompt_path in result.prompt_files_created
    assert result.prompt_files_skipped == []


def test_prepare_story_does_not_require_real_git_repo(tmp_path: Path) -> None:
    create_story(tmp_path)

    assert not (tmp_path / ".git").exists()

    result = prepare_story(tmp_path, STORY)

    assert result.report_path.exists()


def test_cli_prepare_story_requires_story_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "prepare-story"],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_prepare_story_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "prepare-story", "--story", STORY],
    )

    main()

    assert (story_path / "agent_plan.yaml").exists()
    assert (story_path / "prompt_pack" / "03_developer_agent_prompt.md").exists()
    assert (story_path / "reports" / "prepare_story_report.md").exists()
