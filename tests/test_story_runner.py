from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.runtime_config import default_runtime_config_text
from agentic_dev.story_runner import (
    RUNNER_REPORT_FILENAME,
    RUNNER_RESULT_FILENAME,
    resolve_story,
    run_next_story,
    run_story,
)


STORY = "story_055_one_command_story_runner"


def create_project(project_path: Path, *, runtime_config: str | None = None) -> None:
    (project_path / "stories").mkdir(parents=True)
    if runtime_config is not None:
        agentic_path = project_path / ".agentic"
        agentic_path.mkdir()
        (agentic_path / "agent_runtime.yaml").write_text(runtime_config, encoding="utf-8")


def create_story(
    project_path: Path,
    story: str = STORY,
    *,
    slug: str = "one-command-story-runner",
    status: str = "planned",
) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text(
        "# Story 055\n\n## Goal\n\nRun one story with one command.\n",
        encoding="utf-8",
    )
    (story_path / "test_plan.yaml").write_text("unit_tests: true\n", encoding="utf-8")
    (story_path / "monitoring_plan.yaml").write_text(
        "watch_for:\n  - missing_runtime\n",
        encoding="utf-8",
    )
    (story_path / "status.yaml").write_text(
        yaml.safe_dump(
            {
                "story_id": story,
                "slug": slug,
                "status": status,
                "ready_for_review": False,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return story_path


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_resolves_story_by_exact_folder_name(tmp_path: Path) -> None:
    create_project(tmp_path)
    story_path = create_story(tmp_path)

    resolved = resolve_story(tmp_path, STORY)

    assert resolved.story == STORY
    assert resolved.story_path == story_path
    assert resolved.matched_by == "folder"


def test_resolves_story_by_status_slug(tmp_path: Path) -> None:
    create_project(tmp_path)
    create_story(tmp_path, slug="one-command-story-runner")

    resolved = resolve_story(tmp_path, "one-command-story-runner")

    assert resolved.story == STORY
    assert resolved.matched_by == "slug"


def test_dry_run_writes_plan_without_preparing_story(tmp_path: Path) -> None:
    create_project(tmp_path)
    story_path = create_story(tmp_path)

    result = run_story(tmp_path, STORY)

    assert result.executed is False
    assert result.status == "planned"
    assert result.planned_steps == [
        "prepare-story",
        "build-context",
        "codex-task-create",
        "automatic-agent-runtime",
        "verify-required-agent-reports",
        "local-finalize",
        "quality-gate",
    ]
    assert result.result_path == story_path / "reports" / RUNNER_RESULT_FILENAME
    assert result.report_path == story_path / "reports" / RUNNER_REPORT_FILENAME
    assert result.result_path.exists()
    assert result.report_path.exists()
    assert not (story_path / "agent_plan.yaml").exists()
    assert "Dry run only" in result.report_path.read_text(encoding="utf-8")
    assert f"Project: {tmp_path.resolve()}" in result.terminal_summary
    assert "Execute mode: off" in result.terminal_summary
    assert "Planned safe workflow steps:" in result.terminal_summary
    assert "prepare-story" in result.terminal_summary
    assert "automatic-agent-runtime" in result.terminal_summary
    assert "Next action: Review the planned story workflow." in result.terminal_summary


def test_execute_stops_clearly_when_no_automatic_runtime_is_configured(
    tmp_path: Path,
) -> None:
    create_project(tmp_path, runtime_config=default_runtime_config_text())
    story_path = create_story(tmp_path)

    result = run_story(tmp_path, STORY, execute=True)

    assert result.status == "BLOCKED_MISSING_RUNTIME"
    assert "No automatic agent runtime is configured" in result.next_action
    assert "Enable local_model_runtime.enabled" in result.next_action
    assert (story_path / "agent_plan.yaml").exists()
    assert (story_path / "prompt_pack").exists()
    assert (story_path / "reports" / "role_context_result.yaml").exists()
    assert (story_path / "reports" / "codex_task_result.yaml").exists()
    assert not (story_path / "reports" / "finalize_story_result.yaml").exists()


def test_story_runner_records_no_auto_merge_push_deploy_or_pr(tmp_path: Path) -> None:
    create_project(tmp_path)
    create_story(tmp_path)

    result = run_story(tmp_path, STORY)
    result_data = read_yaml(result.result_path)
    safety_flags = result_data["safety_flags"]

    assert safety_flags["committed_or_merged"] is False
    assert safety_flags["pushed"] is False
    assert safety_flags["merged"] is False
    assert safety_flags["deployed"] is False
    assert safety_flags["opened_pr"] is False
    assert "no merge, push, force-push, deploy, PR" in result.terminal_summary
    assert "Did not merge." in result.report_path.read_text(encoding="utf-8")


def test_run_next_story_uses_blueprint_order_not_alphabetical(tmp_path: Path) -> None:
    create_project(tmp_path)
    create_story(tmp_path, "story_z_later", slug="story_z_later")
    create_story(tmp_path, "story_a_next", slug="story_a_next")
    (tmp_path / "blueprints").mkdir()
    (tmp_path / "blueprints" / "blueprint.yaml").write_text(
        yaml.safe_dump(
            {
                "stories": [
                    {"id": "STORY-Z", "slug": "story_z_later"},
                    {"id": "STORY-A", "slug": "story_a_next"},
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = run_next_story(tmp_path)

    assert result.story == "story_z_later"


def test_run_next_story_does_not_fall_back_to_unordered_story_when_blueprint_exists(
    tmp_path: Path,
) -> None:
    create_project(tmp_path)
    create_story(tmp_path, "story_001_unordered", slug="story_001_unordered")
    create_story(tmp_path, "story_900_done", slug="story_900_done", status="ready_for_review")
    (tmp_path / "stories" / "story_900_done" / "status.yaml").write_text(
        yaml.safe_dump(
            {
                "story_id": "story_900_done",
                "slug": "story_900_done",
                "status": "ready_for_review",
                "ready_for_review": True,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "blueprints").mkdir()
    (tmp_path / "blueprints" / "blueprint.yaml").write_text(
        yaml.safe_dump(
            {"stories": [{"id": "STORY-900", "slug": "story_900_done"}]},
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No runnable story with blueprint order"):
        run_next_story(tmp_path)


def test_cli_run_story_dry_run_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    story_path = create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "run-story", "--story", STORY])

    main()

    captured = capsys.readouterr()
    assert "Story runner for" in captured.out
    assert "Project:" in captured.out
    assert "Execute mode: off" in captured.out
    assert "Planned safe workflow steps:" in captured.out
    assert "prepare-story" in captured.out
    assert "no merge, push, force-push, deploy, PR" in captured.out
    assert (story_path / "reports" / RUNNER_RESULT_FILENAME).exists()


def test_cli_run_story_execute_missing_runtime_exits_with_clear_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    create_project(tmp_path, runtime_config=default_runtime_config_text())
    create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "run-story", "--story", STORY, "--execute"],
    )

    with pytest.raises(SystemExit) as error:
        main()

    captured = capsys.readouterr()
    assert error.value.code == 1
    assert "BLOCKED_MISSING_RUNTIME" in captured.out
    assert "No automatic agent runtime is configured" in captured.out
    assert "Enable local_model_runtime.enabled" in captured.out
