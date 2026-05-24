from pathlib import Path

from agentic_dev.scaffolding import init_project


def test_init_project_creates_expected_structure(tmp_path: Path) -> None:
    created_paths = init_project(tmp_path)

    assert created_paths

    assert (tmp_path / ".agentic" / "project.yaml").exists()
    assert (tmp_path / ".agentic" / "rules.yaml").exists()
    assert (tmp_path / ".agentic" / "quality_gates.yaml").exists()

    assert (tmp_path / "blueprints" / "blueprint.md").exists()

    story_path = tmp_path / "stories" / "story_001_project_setup"
    assert (story_path / "story.md").exists()
    assert (story_path / "status.yaml").exists()
    assert (story_path / "instructions" / "developer_agent.md").exists()
    assert (story_path / "instructions" / "test_agent.md").exists()
    assert (story_path / "reports").exists()
    assert (story_path / "review_bundle").exists()
    assert (story_path / "docs").exists()
    assert (story_path / "improvements").exists()

    assert (tmp_path / "src").exists()
    assert (tmp_path / "tests").exists()
    assert (tmp_path / "docs").exists()


def test_init_project_does_not_overwrite_existing_blueprint(tmp_path: Path) -> None:
    blueprint = tmp_path / "blueprints" / "blueprint.md"
    blueprint.parent.mkdir(parents=True)
    blueprint.write_text("Existing blueprint", encoding="utf-8")

    init_project(tmp_path)

    assert blueprint.read_text(encoding="utf-8") == "Existing blueprint"