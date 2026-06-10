from pathlib import Path
from typing import Any

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.micro_readiness import (
    MICRO_READY_WITH_WARNINGS,
    READY_FOR_MICRO,
    TOO_LARGE_FOR_MICRO,
    run_micro_readiness,
)


STORY = "story_049_micro_readiness_story_sizing"
CORE_AGENT_IDS = [
    "research_agent",
    "planner_agent",
    "developer_agent",
    "test_agent",
    "docs_agent",
    "security_quality_agent",
    "local_reviewer_agent",
]


def focused_story_markdown(
    acceptance_criteria: list[str] | None = None,
    not_in_scope: list[str] | None = None,
) -> str:
    criteria = acceptance_criteria or [
        "Add a deterministic micro readiness command.",
        "Write YAML and Markdown reports.",
        "Print a beginner-friendly summary.",
        "Do not call local or cloud models.",
    ]
    boundaries = not_in_scope
    if boundaries is None:
        boundaries = [
            "No local model calls.",
            "No cloud model calls.",
            "No agent execution.",
        ]

    return f"""# STORY-049: Micro-Readiness and Story Sizing Guard

## Goal

Add a deterministic story sizing check for agent-specific micro prompts.

## Why This Matters

Focused agent prompts make local draft work easier to review.

## Acceptance Criteria

{format_markdown_list(criteria)}

## Not In Scope

{format_markdown_list(boundaries)}

## Definition of Done

- pytest passes.
- ruff passes.
- Reports are written.
"""


def format_markdown_list(items: list[str]) -> str:
    if not items:
        return ""
    return "\n".join(f"- {item}" for item in items)


def create_story(project_path: Path, write_agent_plan: bool = True) -> Path:
    story_path = project_path / "stories" / STORY
    instructions_path = story_path / "instructions"
    instructions_path.mkdir(parents=True)
    (story_path / "story.md").write_text(focused_story_markdown(), encoding="utf-8")

    for agent_id in CORE_AGENT_IDS:
        (instructions_path / f"{agent_id}.md").write_text(
            f"# {agent_id}\n\n## Role\n\nHandle the {agent_id} part of the story.\n",
            encoding="utf-8",
        )

    if write_agent_plan:
        (story_path / "agent_plan.yaml").write_text(
            yaml.safe_dump(
                {
                    "story": STORY,
                    "assigned_agents": [
                        {
                            "id": agent_id,
                            "responsibility": f"Handle the {agent_id} readiness task.",
                            "expected_output": f"reports/{agent_id}_report.md",
                        }
                        for agent_id in CORE_AGENT_IDS
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    return story_path


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_missing_story_folder_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        run_micro_readiness(tmp_path, STORY)

    assert STORY in str(error.value)


def test_valid_focused_story_returns_ready_for_micro(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)

    result = run_micro_readiness(tmp_path, STORY)

    assert result.status == READY_FOR_MICRO
    assert result.warnings == []
    assert result.failed_checks == []
    assert result.result_path == story_path / "reports" / "micro_readiness_result.yaml"
    assert result.report_path == story_path / "reports" / "micro_readiness_report.md"


def test_story_with_many_acceptance_criteria_returns_warning_or_too_large(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    criteria = [f"Criterion {index}." for index in range(1, 12)]
    (story_path / "story.md").write_text(
        focused_story_markdown(acceptance_criteria=criteria),
        encoding="utf-8",
    )

    result = run_micro_readiness(tmp_path, STORY)

    assert result.status in {MICRO_READY_WITH_WARNINGS, TOO_LARGE_FOR_MICRO}
    assert any("More than 10 acceptance criteria" in warning for warning in result.warnings)


def test_story_with_more_than_fifteen_acceptance_criteria_is_too_large(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    criteria = [f"Criterion {index}." for index in range(1, 17)]
    (story_path / "story.md").write_text(
        focused_story_markdown(acceptance_criteria=criteria),
        encoding="utf-8",
    )

    result = run_micro_readiness(tmp_path, STORY)

    assert result.status == TOO_LARGE_FOR_MICRO
    assert any("More than 15 acceptance criteria" in check for check in result.failed_checks)


def test_missing_not_in_scope_produces_warning(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    (story_path / "story.md").write_text(
        focused_story_markdown(not_in_scope=[]),
        encoding="utf-8",
    )

    result = run_micro_readiness(tmp_path, STORY)

    assert result.status == MICRO_READY_WITH_WARNINGS
    assert any("Not-in-scope is missing" in warning for warning in result.warnings)


def test_missing_agent_plan_produces_warning(tmp_path: Path) -> None:
    create_story(tmp_path, write_agent_plan=False)

    result = run_micro_readiness(tmp_path, STORY)

    assert result.status == MICRO_READY_WITH_WARNINGS
    assert any("agent_plan.yaml is missing" in warning for warning in result.warnings)


def test_per_agent_estimates_are_written(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)

    result = run_micro_readiness(tmp_path, STORY)

    data = read_yaml(result.result_path)
    assert len(data["agent_estimates"]) == len(CORE_AGENT_IDS)
    assert data["agent_estimates"][0]["agent_id"] == "research_agent"
    assert data["agent_estimates"][0]["estimated_characters"] > 0
    assert data["agent_estimates"][0]["fits_target"] is True
    assert (story_path / "reports" / "micro_readiness_report.md").exists()


def test_result_yaml_is_created(tmp_path: Path) -> None:
    create_story(tmp_path)

    result = run_micro_readiness(tmp_path, STORY)

    assert result.result_path.exists()
    data = read_yaml(result.result_path)
    assert data["story"] == STORY
    assert data["status"] == READY_FOR_MICRO
    assert data["target_characters"] == 2000


def test_report_markdown_is_created(tmp_path: Path) -> None:
    create_story(tmp_path)

    result = run_micro_readiness(tmp_path, STORY)

    assert result.report_path.exists()
    report = result.report_path.read_text(encoding="utf-8")
    assert "# Micro Readiness Report" in report
    assert "## Per-Agent Micro Prompt Estimate" in report
    assert "## Split Examples" in report


def test_target_character_override_works(tmp_path: Path) -> None:
    create_story(tmp_path)

    result = run_micro_readiness(tmp_path, STORY, target_characters=100)

    data = read_yaml(result.result_path)
    assert data["target_characters"] == 100
    assert all(estimate["target_characters"] == 100 for estimate in data["agent_estimates"])
    assert result.status == TOO_LARGE_FOR_MICRO


def test_cli_micro_readiness_does_not_call_models(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    create_story(tmp_path)

    def fail_if_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("model or cloud command should not be called")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("agentic_dev.cli.run_local_agent_draft", fail_if_called)
    monkeypatch.setattr("agentic_dev.cli.run_local_agent_prompt", fail_if_called)
    monkeypatch.setattr("agentic_dev.cli.run_local_model_dry_run", fail_if_called)
    monkeypatch.setattr("agentic_dev.cli.create_cloud_review_packet", fail_if_called)
    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "micro-readiness", "--story", STORY, "--target-chars", "2000"],
    )

    main()

    output = capsys.readouterr().out
    assert "Micro readiness checked for:" in output
    assert "Safety: no local models, cloud models, agents" in output


def test_command_does_not_require_real_git_repo(tmp_path: Path) -> None:
    create_story(tmp_path)

    result = run_micro_readiness(tmp_path, STORY)

    assert result.status == READY_FOR_MICRO
    assert not (tmp_path / ".git").exists()
