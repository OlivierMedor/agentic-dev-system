from pathlib import Path


GOLDEN_PATH_PATH = Path("docs/golden_path.md")
README_PATH = Path("README.md")

REQUIRED_COMMANDS = [
    "agentic generate-stories",
    "agentic workflow-run --story STORY_SLUG --phase prepare --execute",
    "agentic workflow-run --story STORY_SLUG --phase local-finalize --execute",
    "agentic workflow-run --story STORY_SLUG --phase cloud-review-prep --execute",
    "agentic next-step --story STORY_SLUG",
    "agentic project-status",
    "agentic record-cloud-review",
    "agentic merge-readiness",
    "agentic remote-dev-packet",
    "agentic record-remote-dev",
    "agentic artifact-policy",
]


def test_golden_path_doc_exists() -> None:
    assert GOLDEN_PATH_PATH.exists()


def test_golden_path_doc_mentions_required_commands() -> None:
    guide = GOLDEN_PATH_PATH.read_text(encoding="utf-8")

    for command in REQUIRED_COMMANDS:
        assert command in guide


def test_readme_links_to_golden_path_doc() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "docs/golden_path.md" in readme
