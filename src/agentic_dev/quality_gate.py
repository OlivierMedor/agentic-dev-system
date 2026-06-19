from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.artifact_policy import check_artifact_policy
from agentic_dev.review_bundle import CommandRunner, run_command
from agentic_dev.runtime_config import validate_runtime_config
from agentic_dev.test_layers import TEST_LAYER_PASSED, load_yaml_mapping
from agentic_dev.test_layers import test_plan_uses_test_layer_schema


READY_FOR_REVIEW = "READY_FOR_REVIEW"
REQUEST_CHANGES = "REQUEST_CHANGES"
POST_MERGE_VERIFIED = "POST_MERGE_VERIFIED"
POST_MERGE_FAILED = "POST_MERGE_FAILED"
POST_MERGE_GIT_STATUS_COMMAND = ["git", "-c", "core.autocrlf=true", "status", "--short"]

REQUIRED_STORY_FILES = [
    "story.md",
    "status.yaml",
    "test_plan.yaml",
    "monitoring_plan.yaml",
]

REQUIRED_WORKFLOW_FILES = [
    "agent_plan.yaml",
    "reports/developer_report.md",
    "reports/test_report.md",
    "reports/local_review_report.md",
    "review_bundle/handoff.md",
    "review_bundle/pytest_output.txt",
    "review_bundle/ruff_output.txt",
]


@dataclass(frozen=True)
class QualityGateResult:
    story: str
    status: str
    passed_checks: list[str]
    failed_checks: list[str]
    ready_for_review: bool
    next_action: str
    result_path: Path | None
    report_path: Path | None
    mode: str = "pre-merge"
    command_outputs: dict[str, str] | None = None


def text_file_contains(path: Path, expected_text: str) -> bool:
    if not path.exists():
        return False

    content = path.read_text(encoding="utf-8", errors="replace")
    return expected_text in content


def pytest_passed(output_path: Path) -> bool:
    if not output_path.exists():
        return False

    return pytest_passed_output_text(output_path.read_text(encoding="utf-8", errors="replace"))


def ruff_passed(output_path: Path) -> bool:
    if not output_path.exists():
        return False

    return ruff_passed_output_text(output_path.read_text(encoding="utf-8", errors="replace"))


def add_file_checks(
    story_path: Path,
    required_files: list[str],
    passed_checks: list[str],
    failed_checks: list[str],
) -> None:
    for relative_path in required_files:
        path = story_path / relative_path

        if path.exists() and path.is_file():
            passed_checks.append(f"Found required file: {relative_path}")
        else:
            failed_checks.append(f"Missing required file: {relative_path}")


def build_next_action(ready_for_review: bool) -> str:
    if ready_for_review:
        return "Send the story to a human or cloud reviewer."

    return "Fix the failed checks, regenerate any missing reports, then run the quality gate again."


def add_test_layer_checks(
    story_path: Path,
    passed_checks: list[str],
    failed_checks: list[str],
) -> None:
    result_path = story_path / "reports" / "test_layer_result.yaml"

    if result_path.exists():
        result_data = load_yaml_mapping(result_path, "test_layer_result.yaml")
        status = result_data.get("status")

        if status == TEST_LAYER_PASSED:
            passed_checks.append("Test layer result status is PASSED.")
        else:
            failed_checks.append(
                "Test layer result must have status PASSED before quality gate approval."
            )
        return

    if test_plan_uses_test_layer_schema(story_path):
        failed_checks.append(
            "test_plan.yaml uses test_layers_version: 1 but reports/test_layer_result.yaml "
            "is missing. Run agentic test-layers for this story."
        )


def write_yaml_result(path: Path, result: QualityGateResult) -> None:
    data = {
        "story": result.story,
        "mode": result.mode,
        "status": result.status,
        "passed_checks": result.passed_checks,
        "failed_checks": result.failed_checks,
        "ready_for_review": result.ready_for_review,
        "next_action": result.next_action,
    }

    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def format_check_list(checks: list[str]) -> str:
    if not checks:
        return "- None\n"

    return "\n".join(f"- {check}" for check in checks) + "\n"


def write_markdown_report(path: Path, result: QualityGateResult) -> None:
    if result.mode == "post-merge":
        explanation = (
            "Post-merge verification regenerates pytest and Ruff evidence on a clean checkout, "
            "checks the artifact policy and runtime config, and confirms Git stayed clean "
            "before and after verification. It does not decide merge readiness."
        )
    else:
        explanation = (
            "The quality gate checks that the story has the required planning files, "
            "workflow reports, review bundle files, passing pytest output, passing Ruff output, "
            "and local reviewer approval. If any required item is missing or failed, the story "
            "should stay in REQUEST_CHANGES until the evidence is fixed."
        )

    content = f"""# Quality Gate Report

## Story

{result.story}

## Final status

{result.status}

## Passed checks

{format_check_list(result.passed_checks)}
## Failed checks

{format_check_list(result.failed_checks)}
## Next recommended action

{result.next_action}

## Beginner-friendly explanation

{explanation}
"""

    path.write_text(content, encoding="utf-8")


def run_quality_gate(project_path: Path, story: str) -> QualityGateResult:
    return run_quality_gate_mode(project_path, story, mode="pre-merge")


def run_quality_gate_mode(
    project_path: Path,
    story: str,
    *,
    mode: str,
    command_runner: CommandRunner = run_command,
    artifact_policy_checker: Any = check_artifact_policy,
    runtime_config_validator: Any = validate_runtime_config,
) -> QualityGateResult:
    if mode == "pre-merge":
        return run_pre_merge_quality_gate(project_path, story)
    if mode == "post-merge":
        return run_post_merge_quality_gate(
            project_path,
            story,
            command_runner=command_runner,
            artifact_policy_checker=artifact_policy_checker,
            runtime_config_validator=runtime_config_validator,
        )
    raise ValueError("quality gate mode must be pre-merge or post-merge.")


def run_pre_merge_quality_gate(project_path: Path, story: str) -> QualityGateResult:
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    passed_checks: list[str] = []
    failed_checks: list[str] = []

    add_file_checks(story_path, REQUIRED_STORY_FILES, passed_checks, failed_checks)
    add_file_checks(story_path, REQUIRED_WORKFLOW_FILES, passed_checks, failed_checks)

    if pytest_passed(story_path / "review_bundle" / "pytest_output.txt"):
        passed_checks.append("pytest output shows a passing result.")
    else:
        failed_checks.append("pytest output does not clearly show a passing result.")

    if ruff_passed(story_path / "review_bundle" / "ruff_output.txt"):
        passed_checks.append("Ruff output shows a passing result.")
    else:
        failed_checks.append("Ruff output does not clearly show a passing result.")

    if text_file_contains(story_path / "reports" / "local_review_report.md", READY_FOR_REVIEW):
        passed_checks.append("Local reviewer marked the story READY_FOR_REVIEW.")
    else:
        failed_checks.append("Local reviewer report does not contain READY_FOR_REVIEW.")

    add_test_layer_checks(story_path, passed_checks, failed_checks)

    ready_for_review = not failed_checks
    status = READY_FOR_REVIEW if ready_for_review else REQUEST_CHANGES
    next_action = build_next_action(ready_for_review)

    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    result = QualityGateResult(
        story=story,
        mode="pre-merge",
        status=status,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        ready_for_review=ready_for_review,
        next_action=next_action,
        result_path=reports_path / "quality_gate_result.yaml",
        report_path=reports_path / "quality_gate_report.md",
    )

    write_yaml_result(result.result_path, result)
    write_markdown_report(result.report_path, result)

    return result


def run_post_merge_quality_gate(
    project_path: Path,
    story: str,
    *,
    command_runner: CommandRunner,
    artifact_policy_checker: Any,
    runtime_config_validator: Any,
) -> QualityGateResult:
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")
    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    passed_checks: list[str] = []
    failed_checks: list[str] = []
    command_outputs: dict[str, str] = {}

    add_file_checks(story_path, REQUIRED_STORY_FILES, passed_checks, failed_checks)

    git_status_before = command_runner(POST_MERGE_GIT_STATUS_COMMAND, project_path)
    command_outputs["git_status_before"] = git_status_before.stdout.strip()
    if git_status_before.returncode != 0:
        failed_checks.append("git status failed before post-merge verification.")
    elif git_status_before.stdout.strip():
        failed_checks.append("Post-merge verification requires a clean checkout before running.")
    else:
        passed_checks.append("Git checkout is clean before verification.")

    pytest_result = command_runner(["pytest"], project_path)
    command_outputs["pytest"] = (pytest_result.stdout + pytest_result.stderr).strip()
    if pytest_result.returncode == 0 and pytest_passed_output_text(command_outputs["pytest"]):
        passed_checks.append("Regenerated pytest evidence passed.")
    else:
        failed_checks.append("Regenerated pytest evidence failed.")

    ruff_result = command_runner(["ruff", "check", "."], project_path)
    command_outputs["ruff"] = (ruff_result.stdout + ruff_result.stderr).strip()
    if ruff_result.returncode == 0 and ruff_passed_output_text(command_outputs["ruff"]):
        passed_checks.append("Regenerated Ruff evidence passed.")
    else:
        failed_checks.append("Regenerated Ruff evidence failed.")

    artifact_result = artifact_policy_checker(project_path)
    if artifact_result.passed:
        passed_checks.append("Artifact policy passed.")
    else:
        failed_checks.append("Artifact policy failed.")

    try:
        runtime_config_validator(project_path)
    except (FileNotFoundError, ValueError) as error:
        failed_checks.append(f"Runtime config validation failed: {error}")
    else:
        passed_checks.append("Runtime config validation passed.")

    git_status_after = command_runner(POST_MERGE_GIT_STATUS_COMMAND, project_path)
    command_outputs["git_status_after"] = git_status_after.stdout.strip()
    if git_status_after.returncode != 0:
        failed_checks.append("git status failed after post-merge verification.")
    elif git_status_after.stdout.strip():
        failed_checks.append("Post-merge verification modified or created repo files.")
    else:
        passed_checks.append("Git checkout remained clean after verification.")

    passed = not failed_checks
    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)
    result = QualityGateResult(
        story=story,
        mode="post-merge",
        status=POST_MERGE_VERIFIED if passed else POST_MERGE_FAILED,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        ready_for_review=False,
        next_action=(
            "Record the clean-checkout verification result."
            if passed
            else "Fix the regenerated failing checks and rerun post-merge verification."
        ),
        result_path=reports_path / "post_merge_quality_gate_result.yaml",
        report_path=reports_path / "post_merge_quality_gate_report.md",
        command_outputs=command_outputs,
    )

    write_yaml_result(result.result_path, result)
    write_markdown_report(result.report_path, result)
    return result


def pytest_passed_output_text(output: str) -> bool:
    lines = [line.strip().lower() for line in output.splitlines()]
    if "status: passed" in lines or "pytest: passed" in lines or "passed" in lines:
        return True
    return any(" passed in " in line and " failed" not in line for line in lines)


def ruff_passed_output_text(output: str) -> bool:
    lines = [line.strip().lower() for line in output.splitlines()]
    if "status: passed" in lines or "ruff: passed" in lines:
        return True
    return "all checks passed" in output.lower()
