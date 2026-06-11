from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.role_context import build_role_context


STORY = "story_051_role_specific_context_builder"


def create_role_context_story(project_path: Path, agents: list[dict] | None = None) -> Path:
    story_path = project_path / "stories" / STORY
    story_path.mkdir(parents=True)
    (story_path / "reports").mkdir()
    (story_path / "instructions").mkdir()

    (story_path / "story.md").write_text(
        """# STORY-051: Role-Specific Context Builder

## Goal

Build role-specific context packets.

## Why This Matters

Agents need focused context instead of the whole repository.

## Acceptance Criteria

- Add build-context command.
- Update README.md and docs references.
- Track included and skipped files.

## Not In Scope

- No local model calls.
- No cloud model calls.
- No generated prompt execution.

## Definition of Done

- pytest passes.
- ruff passes.
""",
        encoding="utf-8",
    )
    (story_path / "status.yaml").write_text("status: in_progress\n", encoding="utf-8")
    (story_path / "test_plan.yaml").write_text(
        "unit_tests:\n  required: true\n  evidence_or_reason: Cover build-context.\n",
        encoding="utf-8",
    )

    if agents is None:
        agents = [
            {
                "id": "developer_agent",
                "display_name": "Developer Agent",
                "responsibility": "Implement context builder.",
                "instruction_file": "instructions/developer_agent.md",
                "expected_output": "reports/developer_report.md",
            },
            {
                "id": "test_agent",
                "display_name": "Test Agent",
                "responsibility": "Write independent context tests.",
                "instruction_file": "instructions/test_agent.md",
                "expected_output": "reports/test_report.md",
            },
            {
                "id": "local_reviewer_agent",
                "display_name": "Local Reviewer Agent",
                "responsibility": "Review context builder evidence.",
                "instruction_file": "instructions/local_reviewer_agent.md",
                "expected_output": "reports/local_review_report.md",
            },
        ]

    for assigned_agent in agents:
        instruction_file = story_path / assigned_agent["instruction_file"]
        instruction_file.write_text(
            f"# {assigned_agent['display_name']} Instruction\n\nStay in role.\n",
            encoding="utf-8",
        )

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


def add_project_context(project_path: Path) -> None:
    agentic_path = project_path / ".agentic"
    agentic_path.mkdir()
    (agentic_path / "rules.yaml").write_text(
        "rules:\n  - Do not commit generated artifacts.\n",
        encoding="utf-8",
    )
    (agentic_path / "agent_runtime.yaml").write_text(
        "agents:\n  developer_agent:\n    provider: manual\n",
        encoding="utf-8",
    )
    (project_path / "README.md").write_text("# Readme\n", encoding="utf-8")
    docs_path = project_path / "docs"
    docs_path.mkdir()
    (docs_path / "command_map.md").write_text("# Command Map\n", encoding="utf-8")


def read_packet(story_path: Path, agent_id: str) -> str:
    return (story_path / "reports" / "role_context" / f"{agent_id}_context.md").read_text(
        encoding="utf-8",
    )


def test_build_context_creates_developer_context(tmp_path: Path) -> None:
    story_path = create_role_context_story(tmp_path)
    add_project_context(tmp_path)

    result = build_role_context(tmp_path, STORY, agent="developer_agent")

    packet = story_path / "reports" / "role_context" / "developer_agent_context.md"
    assert packet.exists()
    assert result.agents_built == ["developer_agent"]
    text = packet.read_text(encoding="utf-8")
    assert "Agent ID: `developer_agent`" in text
    assert "Build role-specific context packets." in text
    assert "Do not commit generated artifacts." in text


def test_build_context_creates_all_assigned_agent_contexts(tmp_path: Path) -> None:
    story_path = create_role_context_story(tmp_path)

    result = build_role_context(tmp_path, STORY, all_agents=True)

    assert result.agents_built == [
        "developer_agent",
        "test_agent",
        "local_reviewer_agent",
    ]
    assert (story_path / "reports" / "role_context" / "developer_agent_context.md").exists()
    assert (story_path / "reports" / "role_context" / "test_agent_context.md").exists()
    assert (story_path / "reports" / "role_context" / "local_reviewer_agent_context.md").exists()


def test_missing_story_folder_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        build_role_context(tmp_path, STORY)

    assert STORY in str(error.value)


def test_missing_agent_plan_raises_clear_error(tmp_path: Path) -> None:
    story_path = create_role_context_story(tmp_path)
    (story_path / "agent_plan.yaml").unlink()

    with pytest.raises(FileNotFoundError, match="Required agent plan does not exist") as error:
        build_role_context(tmp_path, STORY)

    assert "agent_plan.yaml" in str(error.value)


def test_force_overwrites_existing_context(tmp_path: Path) -> None:
    story_path = create_role_context_story(tmp_path)
    packet_folder = story_path / "reports" / "role_context"
    packet_folder.mkdir()
    packet = packet_folder / "developer_agent_context.md"
    packet.write_text("old context\n", encoding="utf-8")

    result = build_role_context(tmp_path, STORY, agent="developer_agent", force=True)

    assert "old context" not in packet.read_text(encoding="utf-8")
    assert result.agents_built == ["developer_agent"]


def test_without_force_does_not_overwrite_existing_context(tmp_path: Path) -> None:
    story_path = create_role_context_story(tmp_path)
    packet_folder = story_path / "reports" / "role_context"
    packet_folder.mkdir()
    packet = packet_folder / "developer_agent_context.md"
    packet.write_text("custom context\n", encoding="utf-8")

    result = build_role_context(tmp_path, STORY, agent="developer_agent")

    assert packet.read_text(encoding="utf-8") == "custom context\n"
    assert result.agents_built == []
    assert result.context_packets[0].status == "skipped_existing"


def test_developer_context_says_do_not_write_tests(tmp_path: Path) -> None:
    story_path = create_role_context_story(tmp_path)

    build_role_context(tmp_path, STORY, agent="developer_agent")

    assert "Do not write tests." in read_packet(story_path, "developer_agent")


def test_test_context_says_write_independent_tests(tmp_path: Path) -> None:
    story_path = create_role_context_story(tmp_path)

    build_role_context(tmp_path, STORY, agent="test_agent")

    packet = read_packet(story_path, "test_agent")
    assert "Write independent tests" in packet
    assert "tiny test-enabling fixes" in packet


def test_reviewer_context_includes_quality_and_review_evidence_when_present(
    tmp_path: Path,
) -> None:
    story_path = create_role_context_story(tmp_path)
    (story_path / "reports" / "quality_gate_result.yaml").write_text(
        "status: READY_FOR_REVIEW\n",
        encoding="utf-8",
    )
    (story_path / "reports" / "test_layer_result.yaml").write_text(
        "status: TEST_LAYERS_READY\n",
        encoding="utf-8",
    )
    review_bundle = story_path / "review_bundle"
    review_bundle.mkdir()
    (review_bundle / "handoff.md").write_text("Review handoff evidence\n", encoding="utf-8")

    build_role_context(tmp_path, STORY, agent="local_reviewer_agent")

    packet = read_packet(story_path, "local_reviewer_agent")
    assert "READY_FOR_REVIEW" in packet
    assert "TEST_LAYERS_READY" in packet
    assert "Review handoff evidence" in packet


def test_developer_context_excludes_review_bundle_and_cloud_review_packet_content(
    tmp_path: Path,
) -> None:
    story_path = create_role_context_story(tmp_path)
    review_bundle = story_path / "review_bundle"
    review_bundle.mkdir()
    (review_bundle / "handoff.md").write_text("SECRET_REVIEW_BUNDLE_CONTENT\n", encoding="utf-8")
    cloud_packet = story_path / "cloud_review_packet"
    cloud_packet.mkdir()
    (cloud_packet / "cloud_review_export.md").write_text("SECRET_CLOUD_PACKET_CONTENT\n", encoding="utf-8")

    build_role_context(tmp_path, STORY, agent="developer_agent")

    packet = read_packet(story_path, "developer_agent")
    assert "SECRET_REVIEW_BUNDLE_CONTENT" not in packet
    assert "SECRET_CLOUD_PACKET_CONTENT" not in packet
    assert "review_bundle/*" in packet
    assert "cloud_review_packet/*" in packet


def test_result_yaml_is_created_with_false_safety_flags(tmp_path: Path) -> None:
    story_path = create_role_context_story(tmp_path)

    result = build_role_context(tmp_path, STORY, agent="developer_agent")

    result_yaml = yaml.safe_load(result.result_path.read_text(encoding="utf-8"))
    assert result.result_path == story_path / "reports" / "role_context_result.yaml"
    assert result_yaml["status"] == "CONTEXT_READY"
    assert result_yaml["safety_flags"] == {
        "called_cloud_models": False,
        "called_local_models": False,
        "executed_agents": False,
        "committed_or_merged": False,
        "deployed": False,
    }


def test_tests_do_not_require_models_or_github_apis(tmp_path: Path) -> None:
    create_role_context_story(tmp_path)

    result = build_role_context(tmp_path, STORY, agent="developer_agent")

    result_yaml = yaml.safe_load(result.result_path.read_text(encoding="utf-8"))
    assert result_yaml["safety_flags"]["called_cloud_models"] is False
    assert result_yaml["safety_flags"]["called_local_models"] is False
    assert "github" not in result.report_path.read_text(encoding="utf-8").lower()


def test_cli_build_context_defaults_to_all_agents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    story_path = create_role_context_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "build-context", "--story", STORY])

    main()

    captured = capsys.readouterr()
    assert "Role context built for:" in captured.out
    assert (story_path / "reports" / "role_context" / "developer_agent_context.md").exists()
    assert (story_path / "reports" / "role_context" / "test_agent_context.md").exists()
    assert (story_path / "reports" / "role_context" / "local_reviewer_agent_context.md").exists()
