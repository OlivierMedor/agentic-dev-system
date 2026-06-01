from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


READY_FOR_HUMAN_MERGE_DECISION = "READY_FOR_HUMAN_MERGE_DECISION"
READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION = "READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION"
REQUEST_CHANGES = "REQUEST_CHANGES"

CLOUD_APPROVE = "APPROVE"
CLOUD_APPROVE_WITH_NOTES = "APPROVE_WITH_NOTES"
CLOUD_REQUEST_CHANGES = "REQUEST_CHANGES"
TEST_LAYER_PASSED = "PASSED"
QUALITY_READY_FOR_REVIEW = "READY_FOR_REVIEW"

STATUS_MAPPING = {
    READY_FOR_HUMAN_MERGE_DECISION: ("ready_for_human_merge_decision", True),
    READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION: (
        "ready_with_notes_for_human_merge_decision",
        True,
    ),
    REQUEST_CHANGES: ("request_changes", False),
}


@dataclass(frozen=True)
class MergeReadinessResult:
    story: str
    story_path: Path
    status: str
    ready_for_human_merge_decision: bool
    cloud_review_decision: str | None
    passed_checks: list[str]
    failed_checks: list[str]
    next_action: str
    result_path: Path
    report_path: Path
    status_path: Path


def run_merge_readiness(project_path: Path, story: str) -> MergeReadinessResult:
    """Check final local evidence without committing, merging, deploying, or calling cloud models."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    passed_checks: list[str] = []
    failed_checks: list[str] = []

    quality_gate = load_optional_report(
        reports_path / "quality_gate_result.yaml",
        "quality_gate_result.yaml",
    )
    finalize_result = load_optional_report(
        reports_path / "finalize_story_result.yaml",
        "finalize_story_result.yaml",
    )
    test_layer_result = load_optional_report(
        reports_path / "test_layer_result.yaml",
        "test_layer_result.yaml",
    )
    cloud_review_result = load_optional_report(
        reports_path / "cloud_review_result.yaml",
        "cloud_review_result.yaml",
    )

    check_quality_gate(quality_gate, passed_checks, failed_checks)
    check_finalize_result(finalize_result, passed_checks, failed_checks)
    check_test_layer_result(test_layer_result, passed_checks, failed_checks)
    cloud_review_decision = check_cloud_review_result(
        cloud_review_result,
        passed_checks,
        failed_checks,
    )

    local_gates_pass = not failed_checks
    status = decide_status(local_gates_pass, cloud_review_decision)
    ready_for_human_merge_decision = status in {
        READY_FOR_HUMAN_MERGE_DECISION,
        READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION,
    }
    next_action = build_next_action(status)

    result = MergeReadinessResult(
        story=story,
        story_path=story_path,
        status=status,
        ready_for_human_merge_decision=ready_for_human_merge_decision,
        cloud_review_decision=cloud_review_decision,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        next_action=next_action,
        result_path=reports_path / "merge_readiness_result.yaml",
        report_path=reports_path / "merge_readiness_report.md",
        status_path=story_path / "status.yaml",
    )

    write_merge_readiness_result(result)
    write_merge_readiness_report(result)
    update_status(result.status_path, story, status, cloud_review_decision)

    return result


def load_optional_report(path: Path, label: str) -> dict[str, Any] | None:
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as report_file:
        loaded = yaml.safe_load(report_file)

    if loaded is None:
        return {}

    if not isinstance(loaded, dict):
        raise ValueError(f"{label} must be a YAML mapping: {path}")

    return loaded


def check_quality_gate(
    quality_gate: dict[str, Any] | None,
    passed_checks: list[str],
    failed_checks: list[str],
) -> None:
    if quality_gate is None:
        failed_checks.append("Missing required evidence: reports/quality_gate_result.yaml.")
        return

    if (
        quality_gate.get("ready_for_review") is True
        or quality_gate.get("status") == QUALITY_READY_FOR_REVIEW
    ):
        passed_checks.append("Quality gate is ready for review.")
    else:
        failed_checks.append(
            "Quality gate must have ready_for_review: true or status READY_FOR_REVIEW."
        )


def check_finalize_result(
    finalize_result: dict[str, Any] | None,
    passed_checks: list[str],
    failed_checks: list[str],
) -> None:
    if finalize_result is None:
        failed_checks.append("Missing required evidence: reports/finalize_story_result.yaml.")
        return

    if finalize_result.get("ready_for_review") is True:
        passed_checks.append("Finalize story result is ready for review.")
    else:
        failed_checks.append("Finalize story result must have ready_for_review: true.")


def check_test_layer_result(
    test_layer_result: dict[str, Any] | None,
    passed_checks: list[str],
    failed_checks: list[str],
) -> None:
    if test_layer_result is None:
        passed_checks.append("No test layer result was present; optional check skipped.")
        return

    if test_layer_result.get("status") == TEST_LAYER_PASSED:
        passed_checks.append("Test layer result status is PASSED.")
    else:
        failed_checks.append("Test layer result exists and must have status PASSED.")


def check_cloud_review_result(
    cloud_review_result: dict[str, Any] | None,
    passed_checks: list[str],
    failed_checks: list[str],
) -> str | None:
    if cloud_review_result is None:
        failed_checks.append("Missing required evidence: reports/cloud_review_result.yaml.")
        return None

    decision = cloud_review_result.get("decision")
    if decision in {CLOUD_APPROVE, CLOUD_APPROVE_WITH_NOTES}:
        passed_checks.append(f"Cloud review decision is {decision}.")
        return str(decision)

    if decision == CLOUD_REQUEST_CHANGES:
        failed_checks.append("Cloud review decision is REQUEST_CHANGES.")
        return str(decision)

    failed_checks.append(
        "Cloud review decision must be APPROVE, APPROVE_WITH_NOTES, or REQUEST_CHANGES."
    )
    return str(decision) if decision is not None else None


def decide_status(local_gates_pass: bool, cloud_review_decision: str | None) -> str:
    if not local_gates_pass:
        return REQUEST_CHANGES

    if cloud_review_decision == CLOUD_APPROVE:
        return READY_FOR_HUMAN_MERGE_DECISION

    if cloud_review_decision == CLOUD_APPROVE_WITH_NOTES:
        return READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION

    return REQUEST_CHANGES


def build_next_action(status: str) -> str:
    if status == READY_FOR_HUMAN_MERGE_DECISION:
        return (
            "Human owner should review the PR, confirm GitHub Actions are passing, "
            "and decide whether to merge."
        )

    if status == READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION:
        return (
            "Human owner should review cloud review notes, confirm GitHub Actions are passing, "
            "and decide whether to merge."
        )

    return (
        "Address missing evidence or requested changes, then rerun finalize-story, "
        "cloud review, and merge-readiness as needed."
    )


def write_merge_readiness_result(result: MergeReadinessResult) -> None:
    data = {
        "story": result.story,
        "status": result.status,
        "ready_for_human_merge_decision": result.ready_for_human_merge_decision,
        "cloud_review_decision": result.cloud_review_decision,
        "passed_checks": result.passed_checks,
        "failed_checks": result.failed_checks,
        "next_action": result.next_action,
    }

    result.result_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def write_merge_readiness_report(result: MergeReadinessResult) -> None:
    content = f"""# Merge Readiness Report

## Story

{result.story}

## What was checked

- reports/quality_gate_result.yaml
- reports/finalize_story_result.yaml
- reports/test_layer_result.yaml when present
- reports/cloud_review_result.yaml

## Passed checks

{format_check_list(result.passed_checks)}
## Failed checks

{format_check_list(result.failed_checks)}
## Cloud review decision

{result.cloud_review_decision or "missing"}

## Final recommendation

{result.status}

## Next recommended action

{result.next_action}

## Merge reminders

- The human owner must still approve the final merge decision.
- GitHub Actions should be passing before merge.
- This command did not commit, push, merge, deploy, or call cloud models.
"""

    result.report_path.write_text(content, encoding="utf-8")


def update_status(
    status_path: Path,
    story: str,
    merge_readiness_status: str,
    cloud_review_decision: str | None,
) -> None:
    status_text, ready_for_review = STATUS_MAPPING[merge_readiness_status]
    status_data = load_status(status_path)
    status_data["story_id"] = status_data.get("story_id") or story
    status_data["status"] = status_text
    status_data["ready_for_review"] = ready_for_review
    status_data["merge_readiness_status"] = merge_readiness_status
    status_data["ready_for_human_merge_decision"] = ready_for_review
    status_data["cloud_review_decision"] = cloud_review_decision

    safe_write_yaml(status_path, status_data)


def load_status(status_path: Path) -> dict[str, Any]:
    if not status_path.exists():
        return {}

    with status_path.open("r", encoding="utf-8") as status_file:
        loaded = yaml.safe_load(status_file)

    if loaded is None:
        return {}

    if not isinstance(loaded, dict):
        raise ValueError(f"status.yaml must be a YAML mapping: {status_path}")

    return loaded


def safe_write_yaml(path: Path, data: dict[str, Any]) -> None:
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    temporary_path.replace(path)


def format_check_list(checks: list[str]) -> str:
    if not checks:
        return "- None\n"

    return "\n".join(f"- {check}" for check in checks) + "\n"
