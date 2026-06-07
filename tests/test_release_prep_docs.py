from pathlib import Path


README_PATH = Path("README.md")
RELEASE_PROCESS_PATH = Path("docs/release_process.md")
V0_1_RELEASE_CHECKLIST_PATH = Path("docs/v0_1_release_checklist.md")
RELEASE_NOTES_V0_1_PATH = Path("docs/release_notes_v0_1.md")
CHANGELOG_PATH = Path("CHANGELOG.md")


def test_release_docs_exist() -> None:
    assert RELEASE_PROCESS_PATH.exists()
    assert V0_1_RELEASE_CHECKLIST_PATH.exists()
    assert RELEASE_NOTES_V0_1_PATH.exists()
    assert CHANGELOG_PATH.exists()


def test_readme_links_to_release_docs() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    required_links = [
        "docs/release_process.md",
        "docs/v0_1_release_checklist.md",
        "docs/release_notes_v0_1.md",
        "CHANGELOG.md",
    ]

    for link in required_links:
        assert link in readme


def test_v0_1_release_checklist_mentions_required_checks() -> None:
    checklist = V0_1_RELEASE_CHECKLIST_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "pytest",
        "ruff check",
        "artifact-policy",
        "public-readiness",
        "runtime-config validate",
        "GitHub Actions CI passes",
    ]

    for phrase in required_phrases:
        assert phrase in checklist


def test_release_process_requires_owner_approval_and_no_automatic_deploy() -> None:
    process = RELEASE_PROCESS_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "The human owner must approve every release",
        "Do not deploy anything automatically",
        "Do not call cloud models automatically",
    ]

    for phrase in required_phrases:
        assert phrase in process


def test_release_process_documents_default_copyright_when_no_license() -> None:
    process = RELEASE_PROCESS_PATH.read_text(encoding="utf-8")

    assert "default copyright applies" in process
    assert "does not grant outside reuse" in process


def test_changelog_v0_1_mentions_major_capabilities() -> None:
    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "v0.1.0 - Unreleased",
        "Blueprint-to-story workflow",
        "Story workspaces",
        "Prompt packs",
        "Review bundles",
        "Quality gates",
        "Test layers",
        "Queue loops",
        "Support queue",
        "Public-readiness guard",
        "Minimal demo project",
        "Code tour",
        "command map",
        "LangGraph workflow preview and workflow-run phases",
    ]

    for phrase in required_phrases:
        assert phrase in changelog
