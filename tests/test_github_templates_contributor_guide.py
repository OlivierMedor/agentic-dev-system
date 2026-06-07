from pathlib import Path


README_PATH = Path("README.md")
CONTRIBUTING_PATH = Path("CONTRIBUTING.md")
SECURITY_PATH = Path("SECURITY.md")
PR_TEMPLATE_PATH = Path(".github/pull_request_template.md")
BUG_REPORT_PATH = Path(".github/ISSUE_TEMPLATE/bug_report.md")
FEATURE_REQUEST_PATH = Path(".github/ISSUE_TEMPLATE/feature_request.md")
IMPROVEMENT_SUGGESTION_PATH = Path(
    ".github/ISSUE_TEMPLATE/improvement_suggestion.md",
)


def test_public_collaboration_files_exist() -> None:
    required_paths = [
        CONTRIBUTING_PATH,
        SECURITY_PATH,
        PR_TEMPLATE_PATH,
        BUG_REPORT_PATH,
        FEATURE_REQUEST_PATH,
        IMPROVEMENT_SUGGESTION_PATH,
    ]

    for path in required_paths:
        assert path.exists()


def test_readme_links_to_contributing_and_security_docs() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "CONTRIBUTING.md" in readme
    assert "SECURITY.md" in readme


def test_pull_request_template_mentions_required_checks() -> None:
    template = PR_TEMPLATE_PATH.read_text(encoding="utf-8").lower()

    required_phrases = [
        "pytest",
        "ruff",
        "artifact-policy",
        "public-readiness",
        "no generated review artifacts",
    ]

    for phrase in required_phrases:
        assert phrase in template


def test_security_doc_mentions_sensitive_material() -> None:
    security = SECURITY_PATH.read_text(encoding="utf-8").lower()

    required_phrases = [
        "secrets",
        ".env",
        "private prompts",
    ]

    for phrase in required_phrases:
        assert phrase in security


def test_issue_templates_map_to_project_queues() -> None:
    bug_report = BUG_REPORT_PATH.read_text(encoding="utf-8").lower()
    feature_request = FEATURE_REQUEST_PATH.read_text(encoding="utf-8").lower()
    improvement_suggestion = IMPROVEMENT_SUGGESTION_PATH.read_text(
        encoding="utf-8",
    ).lower()

    assert "maintenance queue" in bug_report
    assert "feature queue" in feature_request
    assert "improvement queue" in improvement_suggestion
