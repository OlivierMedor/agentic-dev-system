from pathlib import Path

import yaml

from agentic_dev.finalize_story import finalize_story
from agentic_dev.prepare_story import prepare_story
from agentic_dev.review_bundle import CommandResult
from agentic_dev.scaffolding import init_project
from agentic_dev.story_generator import generate_stories
from agentic_dev.test_layers import TEST_LAYER_PASSED, run_test_layers


SAMPLE_STORY = "story_002_mock_e2e_sample"


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_sample_blueprint(project_path: Path) -> None:
    blueprint_path = project_path / "blueprints" / "blueprint.yaml"
    blueprint_path.write_text(
        f"""stories:
  - id: STORY-002
    slug: {SAMPLE_STORY}
    title: Mock E2E Sample
    goal: Prove the local workflow can run from initialization to finalization.
    why_it_matters: It checks the workflow pieces together without external systems.
    acceptance_criteria:
      - Generated story can be prepared and finalized.
    not_in_scope:
      - Live services.
      - Real Git operations.
      - Cloud model calls.
    definition_of_done:
      - Story is ready for review.
    test_plan:
      unit_tests:
        required: true
        action: add_or_update
        frequency: every_commit
        evidence_or_reason: Unit coverage is represented by this mock E2E test.
      integration_tests:
        required: true
        action: confirm_existing
        frequency: every_pull_request
        evidence_or_reason: Existing workflow functions are exercised together.
      mock_e2e_tests:
        required: true
        action: add_or_update
        frequency: before_merge
        evidence_or_reason: This test covers the full local workflow with mocks.
      live_read_only_checks:
        required: false
        action: not_applicable_with_reason
        frequency: scheduled_or_before_release
        evidence_or_reason: No live services are touched by this story.
      remote_dev_smoke_tests:
        required: false
        action: not_applicable_with_reason
        frequency: after_remote_dev_deploy
        evidence_or_reason: No remote development environment is required.
""",
        encoding="utf-8",
    )


def write_required_reports(story_path: Path) -> None:
    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)
    (reports_path / "developer_report.md").write_text(
        "# Developer Report\n\nImplementation completed in the temporary project.\n",
        encoding="utf-8",
    )
    (reports_path / "test_report.md").write_text(
        "# Test Report\n\nMock E2E workflow evidence was created.\n",
        encoding="utf-8",
    )
    (reports_path / "local_review_report.md").write_text(
        "# Local Review Report\n\nREADY_FOR_REVIEW\n",
        encoding="utf-8",
    )


def write_simulated_review_bundle_evidence(story_path: Path) -> None:
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir(parents=True, exist_ok=True)
    (review_bundle_path / "handoff.md").write_text(
        "# Review Bundle Handoff\n\nSimulated handoff evidence.\n",
        encoding="utf-8",
    )
    (review_bundle_path / "pytest_output.txt").write_text(
        "1 passed in 0.01s\n",
        encoding="utf-8",
    )
    (review_bundle_path / "ruff_output.txt").write_text(
        "All checks passed!\n",
        encoding="utf-8",
    )


def fake_review_bundle_command_runner(command: list[str], cwd: Path) -> CommandResult:
    command_text = " ".join(command)
    outputs = {
        "git merge-base HEAD origin/main": "5f0d9fda8b6b0a89ed6c6ef819a6937630d79d3e\n",
        "git rev-parse HEAD": "c2ec13bfefe6e8cf35d2f6ac4dc2f3a20193b47a\n",
        "git status --short": "",
        "git log --oneline -5": "abc123 Mock commit\n",
        "git diff --stat": "",
        "git diff --cached": "",
        "git diff": "",
        "git diff --stat 5f0d9fda8b6b0a89ed6c6ef819a6937630d79d3e..HEAD": "",
        "git diff --name-only 5f0d9fda8b6b0a89ed6c6ef819a6937630d79d3e..HEAD": "",
        "git diff 5f0d9fda8b6b0a89ed6c6ef819a6937630d79d3e..HEAD": "",
        "git ls-files --others --exclude-standard": "",
        "git rev-parse --show-toplevel": f"{cwd}\n",
        "git rev-parse --git-dir": ".git\n",
        "git branch --show-current": "main\n",
        "git rev-parse --is-shallow-repository": "false\n",
        "git rev-parse --verify origin/main": "5f0d9fda8b6b0a89ed6c6ef819a6937630d79d3e\n",
        "git rev-parse --verify refs/remotes/origin/main": "5f0d9fda8b6b0a89ed6c6ef819a6937630d79d3e\n",
        "git rev-parse --is-inside-work-tree": "true\n",
        "git ls-files": "",
        "pytest": "1 passed in 0.01s\n",
        "ruff check .": "All checks passed!\n",
    }
    return CommandResult(
        command=command_text,
        returncode=0,
        stdout=outputs.get(command_text, ""),
        stderr="",
    )


def test_full_local_workflow_with_mocked_review_bundle(tmp_path: Path) -> None:
    project_path = tmp_path / "sample_project"
    project_path.mkdir()

    init_project(project_path)
    assert not (project_path / ".git").exists()

    write_sample_blueprint(project_path)
    generate_stories(project_path)

    story_path = project_path / "stories" / SAMPLE_STORY
    prepare_story(project_path, SAMPLE_STORY)

    assert (story_path / "agent_plan.yaml").exists()
    assert len(list((story_path / "prompt_pack").glob("*_prompt.md"))) == 7

    write_required_reports(story_path)
    write_simulated_review_bundle_evidence(story_path)

    test_layer_result = run_test_layers(project_path, SAMPLE_STORY)
    assert test_layer_result.status == TEST_LAYER_PASSED

    finalize_story(
        project_path,
        SAMPLE_STORY,
        command_runner=fake_review_bundle_command_runner,
    )

    status = read_yaml(story_path / "status.yaml")
    finalize_result = read_yaml(story_path / "reports" / "finalize_story_result.yaml")

    assert status["ready_for_review"] is True
    assert finalize_result["ready_for_review"] is True
