from pathlib import Path

import pytest
import yaml

from agentic_dev.agent_assignment import CORE_AGENT_TEAM, assign_agents


def create_story(project_path: Path, story: str = "story_004_agent_assignment") -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# Test Story\n", encoding="utf-8")
    (story_path / "status.yaml").write_text(
        "story_id: STORY-004\nslug: story-004-agent-assignment\n",
        encoding="utf-8",
    )
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


def test_assign_agents_uses_blueprint_defined_roles_models_and_writable_paths(tmp_path: Path) -> None:
    story = "story_004_agent_assignment"
    story_path = create_story(tmp_path, story)
    blueprints_path = tmp_path / "blueprints"
    blueprints_path.mkdir()
    (blueprints_path / "blueprint.yaml").write_text(
        yaml.safe_dump(
            {
                "stories": [
                    {
                        "id": "STORY-004",
                        "slug": "story-004-agent-assignment",
                        "agents": {
                            "planner": {
                                "model": "qwen3",
                                "writable_paths": ["stories/**/reports/**"],
                            },
                            "developer": {
                                "model": "gemma",
                                "writable_paths": ["src/**", "stories/**/reports/**"],
                            },
                        },
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    assign_agents(tmp_path, story, force=True)

    agent_plan = read_agent_plan(story_path)
    assert agent_plan["execution_order"] == ["planner_agent", "developer_agent"]
    assert [agent["id"] for agent in agent_plan["assigned_agents"]] == [
        "planner_agent",
        "developer_agent",
    ]
    assert agent_plan["assigned_agents"][0]["role"] == "planner"
    assert agent_plan["assigned_agents"][0]["model"] == "qwen3"
    assert agent_plan["assigned_agents"][1]["writable_paths"] == [
        "src/**",
        "stories/**/reports/**",
    ]


def test_assign_agents_matches_blueprint_story_id_and_preserves_execution_order(tmp_path: Path) -> None:
    story = "story_060"
    story_path = create_story(tmp_path, story)
    (story_path / "status.yaml").write_text(
        "story_id: story_060\nslug: blueprint-local-model-execution\n",
        encoding="utf-8",
    )
    blueprints_path = tmp_path / "blueprints"
    blueprints_path.mkdir()
    (blueprints_path / "blueprint.yaml").write_text(
        yaml.safe_dump(
            {
                "stories": [
                    {
                        "id": "STORY-060",
                        "story_id": "story_060",
                        "slug": "blueprint-local-model-execution",
                        "execution_order": ["documentation", "developer"],
                        "agents": {
                            "developer": {
                                "writable_paths": ["src/**", "stories/story_060/reports/**"],
                            },
                            "documentation": {
                                "model": "qwen/qwen3-coder-30b",
                                "writable_paths": [
                                    "README.md",
                                    "docs/**",
                                    "stories/story_060/reports/**",
                                ],
                            },
                        },
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    assign_agents(tmp_path, story, force=True)

    agent_plan = read_agent_plan(story_path)
    assert agent_plan["execution_order"] == ["docs_agent", "developer_agent"]
    assert [agent["id"] for agent in agent_plan["assigned_agents"]] == [
        "docs_agent",
        "developer_agent",
    ]
    assert agent_plan["assigned_agents"][0]["role"] == "documentation"
    assert agent_plan["assigned_agents"][0]["model"] == "qwen/qwen3-coder-30b"
    assert agent_plan["assigned_agents"][0]["writable_paths"] == [
        "README.md",
        "docs/**",
        "stories/story_060/reports/**",
    ]
