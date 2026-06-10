from pathlib import Path

from agentic_dev.artifact_policy import find_artifact_policy_violations
from agentic_dev.public_readiness import find_public_readiness_violations


README_PATH = Path("README.md")
SYSTEM_MAP_PATH = Path("docs/system_map.md")
PUBLIC_LAUNCH_CHECKLIST_PATH = Path("docs/public_launch_checklist.md")
PUBLIC_READINESS_PATH = Path("docs/public_readiness.md")
GOLDEN_PATH_PATH = Path("docs/golden_path.md")
LOCAL_AGENT_CONTEXT_PACKETS_PATH = Path("docs/local_agent_context_packets.md")
LOCAL_AGENT_DRAFTS_PATH = Path("docs/local_agent_drafts.md")
LOCAL_MODELS_PATH = Path("docs/local_models.md")
LOCAL_MODEL_SCORECARD_PATH = Path("docs/local_model_scorecard.md")
TEST_LAYERS_PATH = Path("docs/test_layers.md")
REPO_SETTINGS_PATH = Path("docs/repo_settings.md")
GITHUB_METADATA_PATH = Path("docs/github_metadata.md")
RELEASE_NOTES_V0_1_PATH = Path("docs/release_notes_v0_1.md")
STORY_047_PATH = Path("stories/story_047_local_agent_prompt_slimming/story.md")
ARCHITECTURE_EXAMPLE_PATH = Path("blueprints/agentic-architecture.example.md")
PRIVATE_ARCHITECTURE_PATH = "blueprints/agentic-architecture.md"
PUBLIC_MARKDOWN_PATHS = [
    README_PATH,
    *sorted(Path("docs").glob("*.md")),
    STORY_047_PATH,
]
STORY_PLACEHOLDER_DOCS = [
    README_PATH,
    SYSTEM_MAP_PATH,
    GOLDEN_PATH_PATH,
    LOCAL_AGENT_CONTEXT_PACKETS_PATH,
    LOCAL_AGENT_DRAFTS_PATH,
    LOCAL_MODELS_PATH,
    TEST_LAYERS_PATH,
    STORY_047_PATH,
]
SUGGESTED_REPO_DESCRIPTION = (
    "A local-first agentic development workflow system with story workspaces, "
    "prompt packs, review bundles, quality gates, CI/CD, and LangGraph-safe "
    "workflow phases."
)


def test_public_launch_docs_exist() -> None:
    assert SYSTEM_MAP_PATH.exists()
    assert PUBLIC_LAUNCH_CHECKLIST_PATH.exists()
    assert REPO_SETTINGS_PATH.exists()
    assert GITHUB_METADATA_PATH.exists()
    assert RELEASE_NOTES_V0_1_PATH.exists()


def test_public_markdown_placeholders_render_visibly() -> None:
    rendered_empty_patterns = [
        "stories//",
        "_ _",
        "--story  ",
        "--prompt-file  ",
    ]
    hidden_placeholder_patterns = [
        "<story>",
        "<agent>",
        "<model-label>",
        "<prompt-file>",
        "<output-file>",
        "<path>",
        "<command>",
    ]

    for path in PUBLIC_MARKDOWN_PATHS:
        content = path.read_text(encoding="utf-8")
        for pattern in [*rendered_empty_patterns, *hidden_placeholder_patterns]:
            assert pattern not in content, f"{path} contains {pattern}"


def test_story_placeholder_docs_use_visible_story_values() -> None:
    for path in STORY_PLACEHOLDER_DOCS:
        content = path.read_text(encoding="utf-8")
        assert (
            "STORY_SLUG" in content
            or "story_047_local_agent_prompt_slimming" in content
        )


def test_readme_links_to_public_docs() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "docs/system_map.md" in readme
    assert "docs/public_launch_checklist.md" in readme
    assert "docs/public_readiness.md" in readme
    assert "docs/golden_path.md" in readme
    assert "docs/repo_settings.md" in readme
    assert "docs/github_metadata.md" in readme


def test_readme_public_repo_polish_content() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "actions/workflows/ci.yml/badge.svg" in readme
    assert "## Quick Demo" in readme
    assert "## Why This Project Matters" in readme
    assert "## Safety Model" in readme
    assert "local-first agentic development workflow system" in readme
    assert "does not call cloud models automatically" in readme
    assert "Human approval remains required" in readme


def test_readme_public_release_readiness_content_is_current() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "public and under active development" in readme
    assert "portfolio-ready v0.1 / early public version" in readme
    assert "preparing for a future public launch" not in readme


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
        "docs/repo_settings.md",
        "change GitHub repository visibility manually",
    ]

    for phrase in required_phrases:
        assert phrase in checklist


def test_github_metadata_doc_contains_suggested_metadata() -> None:
    metadata = GITHUB_METADATA_PATH.read_text(encoding="utf-8")

    required_phrases = [
        SUGGESTED_REPO_DESCRIPTION,
        "GitHub UI",
        "portfolio website URL can be added later",
    ]
    required_topics = [
        "agentic-ai",
        "ai-engineering",
        "developer-tools",
        "langgraph",
        "python",
        "docker",
        "ci-cd",
        "code-review",
        "software-automation",
    ]

    for phrase in [*required_phrases, *required_topics]:
        assert phrase in metadata


def test_release_notes_v0_1_mentions_required_features() -> None:
    release_notes = RELEASE_NOTES_V0_1_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "LangGraph",
        "review bundles",
        "quality gates",
        "Minimal demo project",
    ]

    for phrase in required_phrases:
        assert phrase in release_notes


def test_repo_settings_doc_links_to_github_metadata_and_keeps_license_manual() -> None:
    settings = REPO_SETTINGS_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "docs/github_metadata.md",
        "configured manually in the GitHub UI",
        "The owner should choose a license before inviting outside reuse",
        "Do not choose",
        "LICENSE",
    ]

    for phrase in required_phrases:
        assert phrase in settings
