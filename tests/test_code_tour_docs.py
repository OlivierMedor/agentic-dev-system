from pathlib import Path


README_PATH = Path("README.md")
CODE_TOUR_PATH = Path("docs/code_tour.md")
COMMAND_MAP_PATH = Path("docs/command_map.md")


def test_code_tour_docs_exist() -> None:
    assert CODE_TOUR_PATH.exists()
    assert COMMAND_MAP_PATH.exists()


def test_readme_links_to_code_tour_docs() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "docs/code_tour.md" in readme
    assert "docs/command_map.md" in readme


def test_command_map_mentions_key_commands() -> None:
    command_map = COMMAND_MAP_PATH.read_text(encoding="utf-8")

    required_commands = [
        "generate-stories",
        "workflow-run",
        "review-bundle",
        "quality-gate",
        "project-status",
        "next-step",
        "public-readiness",
    ]

    for command in required_commands:
        assert command in command_map


def test_code_tour_mentions_required_areas() -> None:
    code_tour = CODE_TOUR_PATH.read_text(encoding="utf-8")

    required_areas = [
        "src/agentic_dev",
        "stories",
        "tests",
        "docs",
        "blueprints",
        ".agentic",
    ]

    for area in required_areas:
        assert area in code_tour
