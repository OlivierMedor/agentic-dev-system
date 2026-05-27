from pathlib import Path

import pytest
import yaml

from agentic_dev.agent_assignment import CORE_AGENT_TEAM, assign_agents


def create_story(project_path: Path, story: str = "story_004_agent_assignment") -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# Test Story\n", encoding="utf-8")
    return story_path


def read_agent_plan(story_path: Path) -> dict:
    return yaml.safe_load((story_path / "agent_plan.yaml").read_text(encoding="utf-8"))


def test_assign_agents_creates_agent_plan_with_core_team(tmp_path: Path) -> None:
    story = "story_004_agent_assignment"
    story_path = create_story(tmp_path, story)

    agent_plan_path = assign_agents(tmp_path, story)
    agent_plan = read_agent_plan(story_path)

    assert agent_plan_path == story_path / "agent_plan.yaml"
    assert agent_plan_path.exists()
    assert agent_plan["story"] == story
    assert agent_plan["status"] == "pending_execution"
    assert agent_plan["execution_order"] == [agent["id"] for agent in CORE_AGENT_TEAM]

    assigned_agents = agent_plan["assigned_agents"]
    assert [agent["display_name"] for agent in assigned_agents] == [
        "Research Agent",
        "Planner Agent",
        "Developer Agent",
        "Test Agent",
        "Docs Agent",
        "Security/Quality Agent",
        "Local Reviewer Agent",
    ]

    for agent in assigned_agents:
        assert agent["instruction_file"]
        assert agent["expected_output"]


def test_missing_story_folder_raises_clear_error(tmp_path: Path) -> None:
    missing_story = "story_does_not_exist"

    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        assign_agents(tmp_path, missing_story)

    assert missing_story in str(error.value)


def test_existing_agent_plan_is_not_overwritten_by_default(tmp_path: Path) -> None:
    story = "story_004_agent_assignment"
    story_path = create_story(tmp_path, story)
    existing_plan = story_path / "agent_plan.yaml"
    existing_content = "custom: keep me\n"
    existing_plan.write_text(existing_content, encoding="utf-8")

    with pytest.raises(ValueError, match="Use --force to regenerate it"):
        assign_agents(tmp_path, story)

    assert existing_plan.read_text(encoding="utf-8") == existing_content


def test_force_allows_existing_agent_plan_to_be_regenerated(tmp_path: Path) -> None:
    story = "story_004_agent_assignment"
    story_path = create_story(tmp_path, story)
    existing_plan = story_path / "agent_plan.yaml"
    existing_plan.write_text("custom: replace me\n", encoding="utf-8")

    assign_agents(tmp_path, story, force=True)

    agent_plan = read_agent_plan(story_path)
    assert agent_plan["story"] == story
    assert agent_plan["status"] == "pending_execution"
    assert "custom: replace me" not in existing_plan.read_text(encoding="utf-8")


def test_missing_core_instruction_files_are_created(tmp_path: Path) -> None:
    story = "story_004_agent_assignment"
    story_path = create_story(tmp_path, story)

    assign_agents(tmp_path, story)

    for agent in CORE_AGENT_TEAM:
        instruction_file = story_path / agent["instruction_file"]
        assert instruction_file.exists()
        assert "## Role" in instruction_file.read_text(encoding="utf-8")
