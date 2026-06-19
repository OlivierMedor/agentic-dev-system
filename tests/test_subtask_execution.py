from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_dev.subtask_execution import (
    assemble_subtask_context,
    estimate_input_tokens,
    parse_blueprint_subtasks,
    ready_subtasks,
    topological_subtasks,
)


def blueprint_story(*, subtasks: list[dict] | None = None) -> dict:
    return {
        "id": "STORY-061",
        "story_id": "story_061",
        "slug": "blueprint-defined-context-safe-subtask-execution",
        "goal": "Implement context-safe sub-task execution.",
        "acceptance_criteria": [
            "AC-001: A blueprint can define multiple ordered sub-tasks for a story.",
            "AC-002: Each sub-task has a stable unique ID.",
            "AC-003: Each sub-task has a role assignment.",
            "AC-004: Each sub-task can declare dependencies.",
        ],
        "subtasks": subtasks if subtasks is not None else [task("first"), task("second", depends_on=["first"])],
    }


def task(
    task_id: str,
    *,
    depends_on: list[str] | None = None,
    max_input_tokens: int = 4000,
    reserved_output_tokens: int = 1000,
) -> dict:
    return {
        "id": task_id,
        "title": f"Task {task_id}",
        "role": "developer",
        "depends_on": depends_on or [],
        "requirement_ids": ["AC-001", "AC-002"],
        "required_context": {
            "files": ["story.md"],
            "summaries": ["Use the existing conventions."],
            "prior_task_outputs": depends_on or [],
            "architecture_decisions": ["No cloud fallback."],
        },
        "writable_paths": ["src/**", "stories/story_061/reports/**"],
        "expected_outputs": ["Implementation and tests."],
        "validation": ["pytest passes."],
        "context_budget": {
            "max_input_tokens": max_input_tokens,
            "reserved_output_tokens": reserved_output_tokens,
            "required_context_must_fit": True,
            "allow_required_context_trimming": False,
            "oversized_task_policy": "reject_for_cloud_redecomposition",
        },
    }


def create_context_project(tmp_path: Path) -> Path:
    story_path = tmp_path / "stories" / "story_061"
    (story_path / "instructions").mkdir(parents=True)
    (story_path / "instructions" / "developer_agent.md").write_text(
        "# Developer Agent\n\n## Role\n\nImplement only approved scope.\n",
        encoding="utf-8",
    )
    (tmp_path / "story.md").write_text("# Root Story\n", encoding="utf-8")
    return story_path


def test_parse_valid_subtask_blueprint() -> None:
    subtasks = parse_blueprint_subtasks(blueprint_story())

    assert [subtask.id for subtask in subtasks] == ["first", "second"]
    assert subtasks[1].depends_on == ["first"]
    assert subtasks[0].context_budget.usable_input_tokens == 3000


def test_legacy_blueprint_without_subtasks_is_compatible() -> None:
    assert parse_blueprint_subtasks({"id": "STORY-060"}) == []


def test_duplicate_task_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate sub-task id"):
        parse_blueprint_subtasks(blueprint_story(subtasks=[task("same"), task("same")]))


def test_missing_dependency_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing dependencies"):
        parse_blueprint_subtasks(blueprint_story(subtasks=[task("one", depends_on=["missing"])]))


def test_self_dependency_is_rejected() -> None:
    with pytest.raises(ValueError, match="depend on itself"):
        parse_blueprint_subtasks(blueprint_story(subtasks=[task("one", depends_on=["one"])]))


def test_dependency_cycle_is_rejected() -> None:
    with pytest.raises(ValueError, match="dependency cycle"):
        parse_blueprint_subtasks(
            blueprint_story(
                subtasks=[
                    task("one", depends_on=["two"]),
                    task("two", depends_on=["one"]),
                ],
            )
        )


def test_topological_order_is_deterministic() -> None:
    subtasks = parse_blueprint_subtasks(
        blueprint_story(
            subtasks=[
                task("schema"),
                task("budget", depends_on=["schema"]),
                task("graph", depends_on=["schema"]),
                task("execute", depends_on=["graph", "budget"]),
            ],
        )
    )

    assert [subtask.id for subtask in topological_subtasks(subtasks)] == [
        "schema",
        "budget",
        "graph",
        "execute",
    ]


def test_ready_subtasks_skip_completed_and_require_dependencies() -> None:
    subtasks = parse_blueprint_subtasks(blueprint_story())

    assert [subtask.id for subtask in ready_subtasks(subtasks, {})] == ["first"]
    assert [subtask.id for subtask in ready_subtasks(subtasks, {"first": {"status": "completed"}})] == ["second"]


def test_invalid_context_budget_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive usable input budget"):
        parse_blueprint_subtasks(
            blueprint_story(
                subtasks=[task("bad", max_input_tokens=1000, reserved_output_tokens=1000)],
            )
        )


def test_context_assembly_preserves_mandatory_sections(tmp_path: Path) -> None:
    story_path = create_context_project(tmp_path)
    subtasks = parse_blueprint_subtasks(blueprint_story())

    assembled = assemble_subtask_context(
        tmp_path,
        story_path,
        "story_061",
        blueprint_story(),
        subtasks[0],
    )

    assert assembled.fits
    assert "## system_and_safety_instructions" in assembled.prompt
    assert "## role_instructions" in assembled.prompt
    assert "## required_context" in assembled.prompt
    assert "## response_contract" in assembled.prompt
    assert "Return YAML only." in assembled.prompt
    assert "You may return raw YAML or a single outer ```yaml fenced YAML document." in assembled.prompt
    assert "The YAML must have exactly this shape:" in assembled.prompt
    assert "handoff_summary:" in assembled.prompt
    assert "Expected outputs for this task: Implementation and tests." in assembled.prompt
    assert assembled.estimated_input_tokens == estimate_input_tokens(assembled.prompt)


def test_context_assembly_rejects_missing_required_file(tmp_path: Path) -> None:
    story_path = create_context_project(tmp_path)
    bad_story = blueprint_story(subtasks=[task("bad")])
    bad_story["subtasks"][0]["required_context"]["files"] = ["missing.md"]
    subtasks = parse_blueprint_subtasks(bad_story)

    with pytest.raises(FileNotFoundError, match="Required context file does not exist"):
        assemble_subtask_context(tmp_path, story_path, "story_061", bad_story, subtasks[0])


def test_story_061_blueprint_has_fourteen_subtasks() -> None:
    loaded = yaml.safe_load(Path("blueprints/blueprint.yaml").read_text(encoding="utf-8"))
    story = [entry for entry in loaded["stories"] if entry.get("story_id") == "story_061"][0]

    subtasks = parse_blueprint_subtasks(story)

    assert story["slug"] == "blueprint-defined-context-safe-subtask-execution"
    assert len(subtasks) == 14
    assert all(not subtask.context_budget.allow_required_context_trimming for subtask in subtasks)
