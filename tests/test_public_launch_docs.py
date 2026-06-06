from pathlib import Path

from agentic_dev.artifact_policy import find_artifact_policy_violations
from agentic_dev.public_readiness import find_public_readiness_violations


README_PATH = Path("README.md")
SYSTEM_MAP_PATH = Path("docs/system_map.md")
PUBLIC_LAUNCH_CHECKLIST_PATH = Path("docs/public_launch_checklist.md")
PUBLIC_READINESS_PATH = Path("docs/public_readiness.md")
GOLDEN_PATH_PATH = Path("docs/golden_path.md")
ARCHITECTURE_EXAMPLE_PATH = Path("blueprints/agentic-architecture.example.md")
PRIVATE_ARCHITECTURE_PATH = "blueprints/agentic-architecture.md"


def test_public_launch_docs_exist() -> None:
    assert SYSTEM_MAP_PATH.exists()
    assert PUBLIC_LAUNCH_CHECKLIST_PATH.exists()


def test_readme_links_to_public_docs() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "docs/system_map.md" in readme
    assert "docs/public_launch_checklist.md" in readme
    assert "docs/public_readiness.md" in readme
    assert "docs/golden_path.md" in readme


def test_public_architecture_example_exists() -> None:
    assert ARCHITECTURE_EXAMPLE_PATH.exists()


def test_private_architecture_guidance_is_ignored_and_blocked_by_policy() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert PRIVATE_ARCHITECTURE_PATH in gitignore
    assert [
        violation.path
        for violation in find_artifact_policy_violations([PRIVATE_ARCHITECTURE_PATH])
    ] == [PRIVATE_ARCHITECTURE_PATH]
    assert [
        violation.path
        for violation in find_public_readiness_violations([PRIVATE_ARCHITECTURE_PATH])
    ] == [PRIVATE_ARCHITECTURE_PATH]


def test_system_map_mentions_required_flows() -> None:
    system_map = SYSTEM_MAP_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "Blueprint To Story Flow",
        "Story Workspace Structure",
        "Agent Prompt Pack Flow",
        "Review Bundle, Quality Gate, And Finalize Flow",
        "Cloud Review And Merge Readiness Flow",
        "Queue Loops",
        "LangGraph Workflow-Run Phases",
    ]

    for phrase in required_phrases:
        assert phrase in system_map


def test_public_launch_checklist_mentions_required_checks() -> None:
    checklist = PUBLIC_LAUNCH_CHECKLIST_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "docker compose build",
        "docker compose run --rm dev pytest",
        "docker compose run --rm dev ruff check .",
        "docker compose run --rm dev agentic artifact-policy",
        "docker compose run --rm dev agentic public-readiness",
        "docker compose run --rm dev agentic runtime-config validate",
        "docker compose run --rm dev agentic project-status",
        "Confirm no `.env` files",
        "Confirm no review bundle files",
        "Confirm no cloud review packet files",
        "Confirm no remote dev validation files",
        "Confirm no support queue runtime tickets",
        "Confirm `blueprints/agentic-architecture.md` is not tracked",
        "MIT is a common permissive option",
        "change GitHub repository visibility manually",
    ]

    for phrase in required_phrases:
        assert phrase in checklist
