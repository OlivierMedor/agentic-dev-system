from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.prompt_pack import generate_prompt_pack
from agentic_dev.runtime_config import (
    default_runtime_config_text,
    show_runtime_config,
    validate_runtime_config,
)
from agentic_dev.scaffolding import init_project


STORY = "story_013_dynamic_agent_runtime_config"


def runtime_config_data() -> dict:
    return yaml.safe_load(default_runtime_config_text())


def write_runtime_config(project_path: Path, config: dict | None = None) -> Path:
    config_path = project_path / ".agentic" / "agent_runtime.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config is None:
        config_path.write_text(default_runtime_config_text(), encoding="utf-8")
    else:
        config_path.write_text(
            yaml.safe_dump(config, sort_keys=False),
            encoding="utf-8",
        )

    return config_path


def create_prompt_pack_story(project_path: Path) -> Path:
    init_project(project_path)

    story_path = project_path / "stories" / STORY
    story_path.mkdir(parents=True, exist_ok=True)
    (story_path / "story.md").write_text(
        "# Runtime Config Story\n\nGenerate prompts with runtime guidance.\n",
        encoding="utf-8",
    )
    (story_path / "test_plan.yaml").write_text(
        "unit_tests: true\n",
        encoding="utf-8",
    )
    (story_path / "monitoring_plan.yaml").write_text(
        "watch_for:\n  - missing_agent_runtime_config\n",
        encoding="utf-8",
    )
    (story_path / "agent_plan.yaml").write_text(
        yaml.safe_dump(
            {
                "story": STORY,
                "status": "pending_execution",
                "execution_order": [
                    "developer_agent",
                    "test_agent",
                    "local_reviewer_agent",
                ],
                "assigned_agents": [
                    {
                        "id": "developer_agent",
                        "display_name": "Developer Agent",
                        "responsibility": "Implement runtime config support.",
                        "expected_output": "Write a developer report.",
                    },
                    {
                        "id": "test_agent",
                        "display_name": "Test Agent",
                        "responsibility": "Write runtime config tests.",
                        "expected_output": "Write a test report.",
                    },
                    {
                        "id": "local_reviewer_agent",
                        "display_name": "Local Reviewer Agent",
                        "responsibility": "Review runtime config changes locally.",
                        "expected_output": "Write a local review report.",
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return story_path


def read_prompt(story_path: Path, filename: str) -> str:
    return (story_path / "prompt_pack" / filename).read_text(encoding="utf-8")


def test_init_project_creates_default_runtime_config(tmp_path: Path) -> None:
    init_project(tmp_path)

    config_path = tmp_path / ".agentic" / "agent_runtime.yaml"

    assert config_path.exists()

    config_text = config_path.read_text(encoding="utf-8")
    assert "cloud_reviewer:" in config_text
    assert "provider: manual_cloud_model" in config_text
    assert "provider: local_model_optional" in config_text


def test_validate_runtime_config_passes_for_valid_config(tmp_path: Path) -> None:
    config_path = write_runtime_config(tmp_path)

    result = validate_runtime_config(tmp_path)

    assert result.config_path == config_path.resolve()
    assert result.config["agents"]["cloud_reviewer"]["provider"] == "manual_cloud_model"


def test_validate_runtime_config_fails_for_missing_required_agent(tmp_path: Path) -> None:
    config = runtime_config_data()
    del config["agents"]["test_agent"]
    write_runtime_config(tmp_path, config)

    with pytest.raises(ValueError, match=r"agents\.test_agent must exist and be a mapping"):
        validate_runtime_config(tmp_path)


def test_validate_runtime_config_fails_for_invalid_provider(tmp_path: Path) -> None:
    config = runtime_config_data()
    config["agents"]["developer_agent"]["provider"] = "bad_provider"
    write_runtime_config(tmp_path, config)

    with pytest.raises(ValueError, match=r"agents\.developer_agent\.provider must be one of"):
        validate_runtime_config(tmp_path)


def test_validate_runtime_config_fails_for_invalid_approval_mode(tmp_path: Path) -> None:
    config = runtime_config_data()
    config["agents"]["developer_agent"]["approval_mode"] = "always_yes"
    write_runtime_config(tmp_path, config)

    with pytest.raises(
        ValueError,
        match=r"agents\.developer_agent\.approval_mode must be one of",
    ):
        validate_runtime_config(tmp_path)


def test_validate_runtime_config_fails_when_cloud_reviewer_is_not_manual_cloud_model(
    tmp_path: Path,
) -> None:
    config = runtime_config_data()
    config["agents"]["cloud_reviewer"]["provider"] = "codex"
    write_runtime_config(tmp_path, config)

    with pytest.raises(
        ValueError,
        match=r"agents\.cloud_reviewer\.provider must be manual_cloud_model",
    ):
        validate_runtime_config(tmp_path)


def test_validate_runtime_config_requires_risky_commands_to_need_human_approval(
    tmp_path: Path,
) -> None:
    config = runtime_config_data()
    config["command_policy"]["requires_human_approval"] = [
        command
        for command in config["command_policy"]["requires_human_approval"]
        if command != "git push"
    ]
    config["command_policy"]["allowed_without_approval"].append("git push")
    write_runtime_config(tmp_path, config)

    with pytest.raises(ValueError) as error:
        validate_runtime_config(tmp_path)

    message = str(error.value)
    assert "requires_human_approval must include an entry covering 'git push'" in message
    assert "allowed_without_approval must not include risky command 'git push'" in message


def test_show_runtime_config_returns_yaml_content(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)

    output = show_runtime_config(tmp_path)

    assert "agents:" in output
    assert "cloud_reviewer:" in output
    assert "allowed_without_approval:" in output


def test_cli_runtime_config_validate_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_runtime_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "runtime-config", "validate"])

    main()

    captured = capsys.readouterr()
    assert "Runtime config is valid:" in captured.out


def test_cli_runtime_config_show_prints_config_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_runtime_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "runtime-config", "show"])

    main()

    captured = capsys.readouterr()
    assert "agents:" in captured.out
    assert "cloud_reviewer:" in captured.out
    assert "manual_cloud_model" in captured.out


def test_prompt_pack_includes_runtime_config_and_approval_guidance(tmp_path: Path) -> None:
    story_path = create_prompt_pack_story(tmp_path)

    generate_prompt_pack(tmp_path, STORY)

    developer_prompt = read_prompt(story_path, "03_developer_agent_prompt.md")
    assert "## Runtime Config" in developer_prompt
    assert "cloud_reviewer:" in developer_prompt
    assert "manual_cloud_model" in developer_prompt
    assert "requires_human_approval:" in developer_prompt
    assert "git push" in developer_prompt
    assert "- Approval mode: `workspace_write_no_prompt`" in developer_prompt


def test_local_reviewer_prompt_references_manual_cloud_review_runtime(tmp_path: Path) -> None:
    story_path = create_prompt_pack_story(tmp_path)

    generate_prompt_pack(tmp_path, STORY)

    reviewer_prompt = read_prompt(story_path, "07_local_reviewer_agent_prompt.md")
    assert "cloud_reviewer:" in reviewer_prompt
    assert "provider: manual_cloud_model" in reviewer_prompt
    assert "- Fallback provider: `manual_cloud_model`" in reviewer_prompt
