from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.scaffolding import CORE_AGENT_INSTRUCTIONS
from agentic_dev.story_generator import generate_stories


def write_blueprint(path: Path, story_slug: str = "story_010_example") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""stories:
  - id: STORY-010
    slug: {story_slug}
    title: Example Generated Story
    goal: Build a generated story workspace.
    why_it_matters: It proves the generator reads YAML content.
    acceptance_criteria:
      - Story markdown includes this YAML value.
    not_in_scope:
      - Production deployment.
    definition_of_done:
      - Workspace files exist.
    test_plan:
      unit_tests:
        - Generator unit test.
      integration_tests:
        - CLI smoke test.
      frequency: Every change.
    monitoring_plan:
      logs_required:
        - generator_errors
      watch_for:
        - missing_files
""",
        encoding="utf-8",
    )


def assert_story_workspace_exists(project_path: Path, story_slug: str) -> Path:
    story_path = project_path / "stories" / story_slug

    assert story_path.exists()
    assert (story_path / "story.md").exists()
    assert (story_path / "status.yaml").exists()
    assert (story_path / "test_plan.yaml").exists()
    assert (story_path / "monitoring_plan.yaml").exists()

    assert (story_path / "instructions").exists()
    for filename in CORE_AGENT_INSTRUCTIONS:
        assert (story_path / "instructions" / filename).exists()

    assert (story_path / "reports").exists()
    assert (story_path / "review_bundle").exists()
    assert (story_path / "docs").exists()
    assert (story_path / "improvements").exists()

    return story_path


def test_generate_stories_reads_yaml_and_creates_expected_workspace(tmp_path: Path) -> None:
    blueprint_path = tmp_path / "blueprints" / "blueprint.yaml"
    story_slug = "story_010_example"
    write_blueprint(blueprint_path, story_slug)

    created_paths = generate_stories(tmp_path)

    assert created_paths
    story_path = assert_story_workspace_exists(tmp_path, story_slug)

    story_markdown = (story_path / "story.md").read_text(encoding="utf-8")
    assert "# STORY-010: Example Generated Story" in story_markdown
    assert "It proves the generator reads YAML content." in story_markdown

    test_plan = (story_path / "test_plan.yaml").read_text(encoding="utf-8")
    assert "Generator unit test." in test_plan

    monitoring_plan = (story_path / "monitoring_plan.yaml").read_text(encoding="utf-8")
    assert "generator_errors" in monitoring_plan


def test_generate_stories_creates_full_test_layer_template(tmp_path: Path) -> None:
    blueprint_path = tmp_path / "blueprints" / "blueprint.yaml"
    story_slug = "story_014_test_layers"
    write_blueprint(blueprint_path, story_slug)

    generate_stories(tmp_path)

    test_plan = yaml.safe_load(
        (tmp_path / "stories" / story_slug / "test_plan.yaml").read_text(
            encoding="utf-8",
        ),
    )
    assert test_plan["test_layers_version"] == 1

    for layer_name in [
        "unit_tests",
        "integration_tests",
        "mock_e2e_tests",
        "live_read_only_checks",
        "remote_dev_smoke_tests",
    ]:
        assert set(test_plan[layer_name]) == {
            "required",
            "action",
            "frequency",
            "evidence_or_reason",
        }
        assert isinstance(test_plan[layer_name]["required"], bool)
        assert test_plan[layer_name]["action"]
        assert test_plan[layer_name]["frequency"]
        assert test_plan[layer_name]["evidence_or_reason"]


def test_generate_stories_uses_default_blueprint_path(tmp_path: Path) -> None:
    write_blueprint(tmp_path / "blueprints" / "blueprint.yaml", "story_011_default")

    generate_stories(tmp_path)

    assert_story_workspace_exists(tmp_path, "story_011_default")


def test_generate_stories_supports_project_and_blueprint_overrides(tmp_path: Path) -> None:
    project_path = tmp_path / "target_project"
    custom_blueprint = tmp_path / "custom_blueprints" / "stories.yaml"
    write_blueprint(custom_blueprint, "story_012_custom")

    generate_stories(project_path, custom_blueprint)

    assert_story_workspace_exists(project_path, "story_012_custom")


def test_generate_stories_does_not_overwrite_existing_story_markdown(tmp_path: Path) -> None:
    story_slug = "story_013_existing"
    write_blueprint(tmp_path / "blueprints" / "blueprint.yaml", story_slug)
    story_markdown = tmp_path / "stories" / story_slug / "story.md"
    story_markdown.parent.mkdir(parents=True)
    story_markdown.write_text("Keep this hand-written story.\n", encoding="utf-8")

    generate_stories(tmp_path)

    assert story_markdown.read_text(encoding="utf-8") == "Keep this hand-written story.\n"
    assert (story_markdown.parent / "status.yaml").exists()


def test_generate_stories_handles_missing_default_blueprint_with_clear_error(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="Default blueprint not found"):
        generate_stories(tmp_path)


def test_generate_stories_handles_missing_stories_list_with_clear_error(
    tmp_path: Path,
) -> None:
    blueprint_path = tmp_path / "blueprints" / "blueprint.yaml"
    blueprint_path.parent.mkdir(parents=True)
    blueprint_path.write_text("name: Missing Stories List\n", encoding="utf-8")

    with pytest.raises(ValueError, match="top-level 'stories' list"):
        generate_stories(tmp_path)


def test_cli_generate_stories_uses_current_directory_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_blueprint(tmp_path / "blueprints" / "blueprint.yaml", "story_014_cli")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "generate-stories"])

    main()

    assert_story_workspace_exists(tmp_path, "story_014_cli")
    output = capsys.readouterr().out
    assert "Generated story workspaces" in output
