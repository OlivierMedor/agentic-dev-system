from pathlib import Path


README_PATH = Path("README.md")
PORTFOLIO_CASE_STUDY_PATH = Path("docs/portfolio_case_study.md")
INTERVIEW_TALKING_POINTS_PATH = Path("docs/interview_talking_points.md")
SKILLS_MATRIX_PATH = Path("docs/skills_matrix.md")


def test_portfolio_docs_exist() -> None:
    assert PORTFOLIO_CASE_STUDY_PATH.exists()
    assert INTERVIEW_TALKING_POINTS_PATH.exists()
    assert SKILLS_MATRIX_PATH.exists()


def test_readme_links_to_portfolio_docs() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "docs/portfolio_case_study.md" in readme
    assert "docs/interview_talking_points.md" in readme
    assert "docs/skills_matrix.md" in readme


def test_portfolio_case_study_mentions_required_review_topics() -> None:
    case_study = PORTFOLIO_CASE_STUDY_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "review bundles",
        "quality gates",
        "LangGraph",
        "CI/CD",
        "human approval",
    ]

    for phrase in required_phrases:
        assert phrase in case_study


def test_skills_matrix_mentions_required_skills() -> None:
    skills_matrix = SKILLS_MATRIX_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "Python",
        "Docker",
        "pytest",
        "Ruff",
        "GitHub Actions",
        "LangGraph",
    ]

    for phrase in required_phrases:
        assert phrase in skills_matrix
