from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/ci.yml")


def read_workflow() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_ci_workflow_file_exists() -> None:
    assert WORKFLOW_PATH.exists()


def test_ci_workflow_has_required_triggers_and_branches() -> None:
    workflow = read_workflow()

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "main" in workflow
    assert "story/**" in workflow


def test_ci_workflow_runs_required_quality_commands() -> None:
    workflow = read_workflow()

    assert "actions/checkout" in workflow
    assert "docker compose build" in workflow
    assert "docker compose run --rm dev pytest" in workflow
    assert "docker compose run --rm dev ruff check ." in workflow
    assert "docker compose run --rm dev agentic generate-stories" in workflow
    assert "docker compose run --rm dev agentic artifact-policy" in workflow


def test_ci_workflow_fails_when_generate_stories_changes_working_tree() -> None:
    workflow = read_workflow()

    assert "git status --short" in workflow
    assert 'if [ -n "$(git status --short)" ]; then' in workflow
    assert "exit 1" in workflow
