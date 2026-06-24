from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.quality_gate import READY_FOR_REVIEW, REQUEST_CHANGES, QualityGateResult
from agentic_dev.quality_gate import run_quality_gate
from agentic_dev.review_bundle import CommandRunner, ReviewBundleResult, create_review_bundle
from agentic_dev.test_layers import TestLayerResult, run_test_layers, test_plan_uses_test_layer_schema


STATUS_READY_FOR_REVIEW = "ready_for_review"
STATUS_REQUEST_CHANGES = "request_changes"


@dataclass(frozen=True)
class FinalizeStoryResult:
    story: str
    story_path: Path
    status: str
    ready_for_review: bool
    review_bundle_path: Path
    quality_gate_result_path: Path
    quality_gate_report_path: Path
    test_layer_result_path: Path | None
    finalize_report_path: Path
    finalize_result_path: Path
    next_action: str
    execution_provenance: dict[str, str] | None
    execution_record_checksum: str | None


def finalize_story(
    project_path: Path,
    story: str,
    force: bool = False,
    command_runner: CommandRunner | None = None,
) -> FinalizeStoryResult:
    """Finalize a story for review without committing, pushing, or running cloud models."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    review_bundle_result = create_review_bundle_with_runner(project_path, story, command_runner)
    test_layer_result = run_test_layers_if_applicable(project_path, story_path, story)
    quality_gate_result = run_quality_gate(project_path, story)

    status, ready_for_review = status_from_quality_gate(quality_gate_result)
    
    from agentic_dev.local_evidence_validation import validate_local_evidence
    local_ev = validate_local_evidence(project_path, story)
    
    execution_provenance = None
    execution_record_checksum = None
    
    if local_ev.execution_record_present:
        if not local_ev.execution_record_valid:
            raise ValueError("Local execution record is present but invalid: " + "; ".join(local_ev.failure_reasons))
            
        execution_provenance = local_ev.provenance
        execution_record_checksum = local_ev.record_checksum
        
        # Override readiness if decision is pending
        if not local_ev.ready_for_review:
            ready_for_review = False
            status = STATUS_REQUEST_CHANGES

    status_path = story_path / "status.yaml"
    update_status(status_path, story, status, ready_for_review)

    result = FinalizeStoryResult(
        story=story,
        story_path=story_path,
        status=status,
        ready_for_review=ready_for_review,
        review_bundle_path=review_bundle_result.review_bundle_path,
        quality_gate_result_path=quality_gate_result.result_path,
        quality_gate_report_path=quality_gate_result.report_path,
        test_layer_result_path=test_layer_result.result_path if test_layer_result else None,
        finalize_report_path=reports_path / "finalize_story_report.md",
        finalize_result_path=reports_path / "finalize_story_result.yaml",
        next_action=quality_gate_result.next_action,
        execution_provenance=execution_provenance,
        execution_record_checksum=execution_record_checksum,
    )

    write_finalize_result(result)
    write_finalize_report(result, quality_gate_result, review_bundle_result, force)

    review_bundle_result = create_review_bundle_with_runner(project_path, story, command_runner)
    write_finalize_report(result, quality_gate_result, review_bundle_result, force)

    return result


def create_review_bundle_with_runner(
    project_path: Path,
    story: str,
    command_runner: CommandRunner | None,
) -> ReviewBundleResult:
    if command_runner is None:
        return create_review_bundle(project_path, story)

    return create_review_bundle(project_path, story, command_runner=command_runner)


def run_test_layers_if_applicable(
    project_path: Path,
    story_path: Path,
    story: str,
) -> TestLayerResult | None:
    if not test_plan_uses_test_layer_schema(story_path):
        return None

    return run_test_layers(project_path, story)


def status_from_quality_gate(quality_gate_result: QualityGateResult) -> tuple[str, bool]:
    if quality_gate_result.status == READY_FOR_REVIEW:
        return STATUS_READY_FOR_REVIEW, True

    if quality_gate_result.status == REQUEST_CHANGES:
        return STATUS_REQUEST_CHANGES, False

    raise ValueError(f"Unknown quality gate status: {quality_gate_result.status}")


def update_status(status_path: Path, story: str, status: str, ready_for_review: bool) -> None:
    status_data = load_status(status_path)
    status_data["story_id"] = status_data.get("story_id") or story
    status_data["status"] = status
    status_data["ready_for_review"] = ready_for_review

    status_path.write_text(yaml.safe_dump(status_data, sort_keys=False), encoding="utf-8")


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


def write_finalize_result(result: FinalizeStoryResult) -> None:
    data = {
        "story": result.story,
        "status": result.status,
        "ready_for_review": result.ready_for_review,
        "review_bundle_path": str(result.review_bundle_path),
        "quality_gate_result_path": str(result.quality_gate_result_path),
        "test_layer_result_path": str(result.test_layer_result_path)
        if result.test_layer_result_path
        else None,
        "finalize_report_path": str(result.finalize_report_path),
        "next_action": result.next_action,
        "execution_provenance": result.execution_provenance,
        "execution_record_checksum": result.execution_record_checksum,
    }

    result.finalize_result_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def write_finalize_report(
    result: FinalizeStoryResult,
    quality_gate_result: QualityGateResult,
    review_bundle_result: ReviewBundleResult,
    force: bool,
) -> None:
    content = f"""# Finalize Story Report

## Story

{result.story}

## What finalize-story did

- Created or refreshed the review bundle at `{result.review_bundle_path}`.
- Ran test layer validation when `test_plan.yaml` used `test_layers_version: 1`.
- Ran the quality gate and wrote `{result.quality_gate_result_path}`.
- Regenerated the review bundle after the quality gate so final evidence is captured.
- Wrote finalize result data to `{result.finalize_result_path}`.
- Updated `status.yaml` without committing, pushing, merging, deploying, or calling cloud models.

## Quality gate result

- Quality gate status: {quality_gate_result.status}
- Test layer result: {format_optional_path(result.test_layer_result_path)}
- Ready for review: {result.ready_for_review}
- pytest in final review bundle passed: {review_bundle_result.pytest_passed}
- Ruff in final review bundle passed: {review_bundle_result.ruff_passed}

## Story status update

- status: {result.status}
- ready_for_review: {str(result.ready_for_review).lower()}

## Next recommended action

{result.next_action}

Human or cloud review is still required before merge.

## Notes

- force: {str(force).lower()}
"""

    result.finalize_report_path.write_text(content, encoding="utf-8")


def format_optional_path(path: Path | None) -> str:
    if path is None:
        return "not applicable"

    return str(path)
