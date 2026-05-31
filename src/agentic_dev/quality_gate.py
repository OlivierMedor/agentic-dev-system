from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from agentic_dev.test_layers import TEST_LAYER_PASSED, load_yaml_mapping
from agentic_dev.test_layers import test_plan_uses_test_layer_schema


READY_FOR_REVIEW = "READY_FOR_REVIEW"
REQUEST_CHANGES = "REQUEST_CHANGES"

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
    result_path: Path
    report_path: Path


def text_file_contains(path: Path, expected_text: str) -> bool:
    if not path.exists():
        return False

    content = path.read_text(encoding="utf-8", errors="replace")
    return expected_text in content


def pytest_passed(output_path: Path) -> bool:
    if not output_path.exists():
        return False

    content = output_path.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip().lower() for line in content.splitlines()]

    if "status: passed" in lines or "pytest: passed" in lines or "passed" in lines:
        return True

    return any(" passed in " in line and " failed" not in line for line in lines)


def ruff_passed(output_path: Path) -> bool:
    if not output_path.exists():
        return False

    content = output_path.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip().lower() for line in content.splitlines()]

    if "status: passed" in lines or "ruff: passed" in lines:
        return True

    return "all checks passed" in content.lower()


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
