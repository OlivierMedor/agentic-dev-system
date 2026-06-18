from pathlib import Path

import pytest
import yaml

from agentic_dev.prompt_pack import generate_prompt_pack


STORY = "story_006_agent_prompt_packs"


def create_prompt_pack_story(project_path: Path, agents: list[dict] | None = None) -> Path:
    story_path = project_path / "stories" / STORY
    story_path.mkdir(parents=True)

    (story_path / "story.md").write_text(
        "# Prompt Pack Story\n\nBuild prompt files for every assigned agent.\n",
        encoding="utf-8",
    )
    (story_path / "test_plan.yaml").write_text(
        "tests:\n  - confirm prompt generation\n",
        encoding="utf-8",
    )
    (story_path / "monitoring_plan.yaml").write_text(
        "risk_signals:\n  - missing_prompt_pack\n",
        encoding="utf-8",
    )

    if agents is None:
        agents = [
            {
                "id": "developer_agent",
                "display_name": "Developer Agent",
                "responsibility": "Implement prompt pack generation.",
                "expected_output": "Write a developer report.",
            },
            {
                "id": "test_agent",
                "display_name": "Test Agent",
                "responsibility": "Write independent prompt pack tests.",
                "expected_output": "Write a test report.",
            },
            {
                "id": "local_reviewer_agent",
                "display_name": "Local Reviewer Agent",
                "responsibility": "Review the finished story locally.",
                "expected_output": "Write a local review report.",
            },
        ]

    agent_plan = {
        "story": STORY,
        "status": "pending_execution",
        "execution_order": [agent["id"] for agent in agents],
        "assigned_agents": agents,
    }
    (story_path / "agent_plan.yaml").write_text(
        yaml.safe_dump(agent_plan, sort_keys=False),
        encoding="utf-8",
    )

    return story_path


def add_project_rules(project_path: Path) -> None:
    rules_path = project_path / ".agentic" / "rules.yaml"
    rules_path.parent.mkdir()
    rules_path.write_text(
        "rules:\n  - Keep generated prompts deterministic.\n",
        encoding="utf-8",
    )


def read_prompt(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8")


def test_generate_prompts_creates_prompt_pack_with_one_file_per_agent(tmp_path: Path) -> None:
    story_path = create_prompt_pack_story(tmp_path)

    result = generate_prompt_pack(tmp_path, STORY)

    assert result.prompt_pack_path == story_path / "prompt_pack"
    assert result.prompt_pack_path.exists()
    assert len(result.created_files) == 3
    assert len(result.skipped_files) == 0

    prompt_files = sorted(path.name for path in result.prompt_pack_path.iterdir())
    assert prompt_files == [
        "03_developer_agent_prompt.md",
        "04_test_agent_prompt.md",
        "07_local_reviewer_agent_prompt.md",
    ]


def test_generated_prompts_include_story_plans_responsibility_and_output(
    tmp_path: Path,
) -> None:
    story_path = create_prompt_pack_story(tmp_path)
    add_project_rules(tmp_path)

    generate_prompt_pack(tmp_path, STORY)

    prompts = {
        path.name: read_prompt(path)
        for path in (story_path / "prompt_pack").iterdir()
        if path.is_file()
    }

    for prompt in prompts.values():
        assert "# Prompt Pack Story" in prompt
        assert "Build prompt files for every assigned agent." in prompt
        assert "confirm prompt generation" in prompt
        assert "missing_prompt_pack" in prompt
        assert "Keep generated prompts deterministic." in prompt

    developer_prompt = prompts["03_developer_agent_prompt.md"]
    assert "Implement prompt pack generation." in developer_prompt
    assert "Write a developer report." in developer_prompt

    test_prompt = prompts["04_test_agent_prompt.md"]
    assert "Write independent prompt pack tests." in test_prompt
    assert "Write a test report." in test_prompt

    reviewer_prompt = prompts["07_local_reviewer_agent_prompt.md"]
    assert "Review the finished story locally." in reviewer_prompt
    assert "Write a local review report." in reviewer_prompt


def test_generated_role_prompts_include_required_agent_specific_rules(tmp_path: Path) -> None:
    story_path = create_prompt_pack_story(tmp_path)

    generate_prompt_pack(tmp_path, STORY)

    developer_prompt = read_prompt(story_path / "prompt_pack" / "03_developer_agent_prompt.md")
    test_prompt = read_prompt(story_path / "prompt_pack" / "04_test_agent_prompt.md")
    reviewer_prompt = read_prompt(
        story_path / "prompt_pack" / "07_local_reviewer_agent_prompt.md"
    )

    assert "Do not write tests." in developer_prompt
    assert "Do not modify implementation code unless a tiny fix is required" in test_prompt
    assert "explain any such fix" in test_prompt
    assert "unit, integration, mock E2E, live read-only, and remote dev smoke" in test_prompt
    assert "add tests, update tests, confirm existing coverage" in test_prompt
    assert "explain why a layer is not applicable" in test_prompt
    assert "Do not approve unless pytest and Ruff pass." in reviewer_prompt


def test_generated_prompts_include_local_agent_safety_format_guidance(tmp_path: Path) -> None:
    story_path = create_prompt_pack_story(tmp_path)

    generate_prompt_pack(tmp_path, STORY)

    developer_prompt = read_prompt(story_path / "prompt_pack" / "03_developer_agent_prompt.md")
    assert "Prefer plain ASCII output." in developer_prompt
    assert "Avoid emoji/checkmark symbols." in developer_prompt
    assert "Avoid unnecessary nested Markdown code fences." in developer_prompt
    assert "Use requested headings exactly." in developer_prompt


def test_missing_story_folder_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        generate_prompt_pack(tmp_path, STORY)

    assert STORY in str(error.value)


def test_missing_agent_plan_raises_clear_error(tmp_path: Path) -> None:
    story_path = create_prompt_pack_story(tmp_path)
    (story_path / "agent_plan.yaml").unlink()

    with pytest.raises(FileNotFoundError, match="Required agent plan does not exist") as error:
        generate_prompt_pack(tmp_path, STORY)

    assert "agent_plan.yaml" in str(error.value)
    assert f"agentic assign-agents --story {STORY}" in str(error.value)


def test_existing_prompt_files_are_not_overwritten_by_default(tmp_path: Path) -> None:
    story_path = create_prompt_pack_story(tmp_path)
    prompt_pack_path = story_path / "prompt_pack"
    prompt_pack_path.mkdir()
    existing_prompt = prompt_pack_path / "03_developer_agent_prompt.md"
    existing_prompt.write_text("custom prompt content\n", encoding="utf-8")

    result = generate_prompt_pack(tmp_path, STORY)

    assert existing_prompt.read_text(encoding="utf-8") == "custom prompt content\n"
    assert existing_prompt in result.skipped_files
    assert prompt_pack_path / "04_test_agent_prompt.md" in result.created_files
    assert prompt_pack_path / "07_local_reviewer_agent_prompt.md" in result.created_files


def test_force_regenerates_existing_prompt_files(tmp_path: Path) -> None:
    story_path = create_prompt_pack_story(tmp_path)
    prompt_pack_path = story_path / "prompt_pack"
    prompt_pack_path.mkdir()
    existing_prompt = prompt_pack_path / "03_developer_agent_prompt.md"
    existing_prompt.write_text("custom prompt content\n", encoding="utf-8")

    result = generate_prompt_pack(tmp_path, STORY, force=True)

    regenerated_prompt = existing_prompt.read_text(encoding="utf-8")
    assert "custom prompt content" not in regenerated_prompt
    assert "Implement prompt pack generation." in regenerated_prompt
    assert existing_prompt in result.created_files
    assert len(result.skipped_files) == 0
