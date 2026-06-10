from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.micro_readiness import (
    MICRO_READY_WITH_WARNINGS,
    READY_FOR_MICRO,
    TOO_LARGE_FOR_MICRO,
)


BAD_RESULT_VALUES = {"REQUEST_CHANGES", "DEV_FAILED", "NOT_RUN", "request_changes"}
READY_REMOTE_DEV_STATUSES = {"DEV_VALIDATED", "DEV_VALIDATED_WITH_NOTES"}
READY_MERGE_STATUSES = {
    "READY_FOR_HUMAN_MERGE_DECISION",
    "READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION",
}
WORKFLOW_RUN_UNSAFE_FLAGS = (
    "executed_agents",
    "called_cloud_models",
    "called_github_apis",
    "committed_or_merged",
    "pushed",
    "merged",
    "deployed",
    "ran_destructive_commands",
    "ran_arbitrary_commands",
)
REQUIRED_AGENT_REPORTS = (
    "developer_report.md",
    "test_report.md",
    "local_review_report.md",
)
RESULT_FILES = (
    "test_layer_result.yaml",
    "quality_gate_result.yaml",
    "finalize_story_result.yaml",
    "workflow_run_result.yaml",
    "micro_readiness_result.yaml",
    "cloud_review_result.yaml",
    "merge_readiness_result.yaml",
    "remote_dev_validation_result.yaml",
)


@dataclass(frozen=True)
class StoryEvidence:
    story: str
    story_path: Path
    reports_path: Path
    status_data: dict[str, Any]
    agent_plan_exists: bool
    prompt_pack_exists: bool
    prompt_files: list[Path]
    reports: list[Path]
    review_bundle_files: list[Path]
    cloud_review_export_exists: bool
    remote_dev_packet_exists: bool
    test_plan_uses_layers: bool
    result_data: dict[str, dict[str, Any]]
    warnings: list[str]


@dataclass(frozen=True)
class NextStepRecommendation:
    title: str
    command: str | None
    reason: str
    details: list[str]


@dataclass(frozen=True)
class NextStepResult:
    story: str
    story_path: Path
    recommendation: NextStepRecommendation
    report_path: Path
    terminal_summary: str


def run_next_step(project_path: Path, story: str) -> NextStepResult:
    """Inspect a story workspace and recommend the next safe workflow action."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story
    validate_story_folder(story_path)

    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    evidence = inspect_story(project_path, story_path, story)
    recommendation = choose_recommendation(evidence)
    report_path = reports_path / "next_step_report.md"
    write_next_step_report(report_path, evidence, recommendation)

    terminal_summary = format_terminal_summary(story, recommendation, report_path)
    return NextStepResult(
        story=story,
        story_path=story_path,
        recommendation=recommendation,
        report_path=report_path,
        terminal_summary=terminal_summary,
    )


def validate_story_folder(story_path: Path) -> None:
    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")


def inspect_story(project_path: Path, story_path: Path, story: str) -> StoryEvidence:
    reports_path = story_path / "reports"
    warnings: list[str] = []
    status_data = load_optional_yaml_mapping(story_path / "status.yaml", "status.yaml", warnings)
    test_plan = load_optional_yaml_mapping(story_path / "test_plan.yaml", "test_plan.yaml", warnings)
    result_data = {
        filename: load_optional_yaml_mapping(reports_path / filename, filename, warnings)
        for filename in RESULT_FILES
        if (reports_path / filename).exists()
    }

    prompt_pack_path = story_path / "prompt_pack"
    review_bundle_path = story_path / "review_bundle"
    reports = sorted(reports_path.glob("*")) if reports_path.exists() else []
    review_bundle_files = sorted(review_bundle_path.glob("*")) if review_bundle_path.exists() else []

    return StoryEvidence(
        story=story,
        story_path=story_path,
        reports_path=reports_path,
        status_data=status_data,
        agent_plan_exists=(story_path / "agent_plan.yaml").is_file(),
        prompt_pack_exists=prompt_pack_path.is_dir(),
        prompt_files=sorted(prompt_pack_path.glob("*.md")) if prompt_pack_path.is_dir() else [],
        reports=reports,
        review_bundle_files=review_bundle_files,
        cloud_review_export_exists=(
            story_path / "cloud_review_packet" / "cloud_review_export.md"
        ).is_file(),
        remote_dev_packet_exists=(
            story_path / "remote_dev_validation" / "remote_dev_packet.md"
        ).is_file(),
        test_plan_uses_layers=test_plan.get("test_layers_version") == 1,
        result_data=result_data,
        warnings=warnings,
    )


def load_optional_yaml_mapping(path: Path, label: str, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as yaml_file:
            loaded = yaml.safe_load(yaml_file)
    except yaml.YAMLError as error:
        warnings.append(f"{label} has invalid YAML: {error}.")
        return {}

    if loaded is None:
        return {}

    if not isinstance(loaded, dict):
        warnings.append(f"{label} must be a YAML mapping.")
        return {}

    return loaded


def choose_recommendation(evidence: StoryEvidence) -> NextStepRecommendation:
    blocked_by = text_value(evidence.status_data.get("blocked_by"))
    status = text_value(evidence.status_data.get("status"))
    if status == "blocked" or blocked_by:
        ticket_text = f" {blocked_by}" if blocked_by else ""
        return NextStepRecommendation(
            title="Review the blocking support ticket.",
            command=None,
            reason=(
                "This story is blocked. Review the support ticket before continuing "
                "with implementation or review gates."
            ),
            details=[
                f"Blocking support ticket:{ticket_text or ' recorded in status.yaml'}",
                "Resume workflow only after the blocker is answered or closed.",
            ],
        )

    unsafe_workflow_run_details = find_unsafe_workflow_run_flags(evidence)
    if unsafe_workflow_run_details:
        return NextStepRecommendation(
            title="Investigate workflow-run safety flags.",
            command=None,
            reason=(
                "workflow_run_result.yaml records unsafe local workflow evidence. "
                "Treat this as REQUEST_CHANGES until it is investigated."
            ),
            details=unsafe_workflow_run_details
            + [
                "Do not continue to cloud review, merge, or deployment from this state.",
            ],
        )

    bad_details = find_bad_result_values(evidence)
    if bad_details:
        return NextStepRecommendation(
            title="Fix failed checks before continuing.",
            command=None,
            reason=(
                "One or more recorded workflow results request changes or show failed "
                "remote-dev validation."
            ),
            details=bad_details
            + [
                "Update the story work and rerun the failed gate before moving forward.",
            ],
        )

    if not evidence.agent_plan_exists or not evidence.prompt_pack_exists or not evidence.prompt_files:
        return NextStepRecommendation(
            title="Run workflow-run prepare.",
            command=f"agentic workflow-run --story {evidence.story} --phase prepare --execute",
            reason="The story is missing its agent plan or generated prompt files.",
            details=[
                f"agent_plan.yaml present: {format_bool(evidence.agent_plan_exists)}",
                f"prompt_pack present: {format_bool(evidence.prompt_pack_exists)}",
                f"prompt files found: {len(evidence.prompt_files)}",
                "workflow-run prepare wraps prepare-story and workflow-preview safely.",
                "The prepare phase also records micro-readiness story sizing guidance.",
                (
                    "It does not execute agents, run generated prompts, call cloud models, "
                    "call GitHub APIs, commit, push, merge, or deploy."
                ),
            ],
        )

    missing_agent_reports = [
        report for report in REQUIRED_AGENT_REPORTS if not (evidence.reports_path / report).is_file()
    ]
    if evidence.prompt_files and missing_agent_reports:
        micro_readiness_result = evidence.result_data.get("micro_readiness_result.yaml")
        micro_status = text_value((micro_readiness_result or {}).get("status"))
        micro_warnings = list_values((micro_readiness_result or {}).get("warnings"))
        if micro_readiness_result is None:
            return NextStepRecommendation(
                title="Run micro-readiness.",
                command=f"agentic micro-readiness --story {evidence.story}",
                reason=(
                    "The story is prepared with an agent plan and prompt pack, but "
                    "reports/micro_readiness_result.yaml is not recorded yet."
                ),
                details=[
                    "Run the direct micro-readiness command for sizing guidance.",
                    (
                        "If story setup should be refreshed, run "
                        f"agentic workflow-run --story {evidence.story} --phase "
                        "prepare --execute."
                    ),
                    (
                        "Micro-readiness helps choose micro, slim, or stronger "
                        "configured agent runtime usage before generated prompts are run."
                    ),
                ],
            )

        if micro_status == TOO_LARGE_FOR_MICRO:
            return NextStepRecommendation(
                title="Review story size or configured agent runtime.",
                command=None,
                reason=(
                    "micro_readiness_result.yaml reports TOO_LARGE_FOR_MICRO, so "
                    "micro mode is probably the wrong first choice for this story."
                ),
                details=[
                    "Split or narrow the story before relying on agent-specific micro prompts.",
                    "Alternatively use a stronger configured agent runtime for this story.",
                    "Warnings: " + format_inline_list(micro_warnings),
                    "Do not treat this as approval to merge or deploy automatically.",
                ],
            )

        details = [
            "Missing required reports: " + ", ".join(missing_agent_reports),
            f"Prompt files found: {len(evidence.prompt_files)}",
        ]
        if micro_status == READY_FOR_MICRO:
            details.append("micro-readiness status: READY_FOR_MICRO.")
        elif micro_status == MICRO_READY_WITH_WARNINGS:
            details.append(
                "micro-readiness warnings are guidance, not an automatic workflow failure."
            )
            details.append(
                "Local models may need micro mode, or the story may need splitting if "
                "warnings point to broad or unclear scope."
            )
            details.append("Micro-readiness warnings: " + format_inline_list(micro_warnings))
        return NextStepRecommendation(
            title="Run the generated agent prompts.",
            command=None,
            reason=(
                "Prompt files exist, but required agent reports are still missing. "
                "Run the generated prompts using the configured agent runtime."
            ),
            details=details,
        )

    workflow_run_result = evidence.result_data.get("workflow_run_result.yaml")
    if workflow_run_failed(workflow_run_result):
        workflow_run_phase = text_value(workflow_run_result.get("phase")) or "unknown"
        return NextStepRecommendation(
            title=f"Investigate failed workflow-run {workflow_run_phase}.",
            command=None,
            reason=f"workflow_run_result.yaml records a failed {workflow_run_phase} run.",
            details=[
                "Review reports/workflow_run_report.md and the failed local step result.",
                "Fix the failed local evidence before continuing.",
            ],
        )

    finalize_result = evidence.result_data.get("finalize_story_result.yaml")
    if not finalize_result or not finalize_result_ready(finalize_result):
        return workflow_run_local_finalize_recommendation(
            evidence,
            "Required local finalization evidence is missing or not ready.",
        )

    if finalize_result_stale(evidence):
        return workflow_run_local_finalize_recommendation(
            evidence,
            "Required story evidence changed after the last finalize result.",
        )

    if not evidence.cloud_review_export_exists:
        reason = "finalize-story is ready, but the cloud review export packet does not exist."
        if workflow_run_phase_completed(workflow_run_result, "local-finalize"):
            reason = (
                "workflow-run local-finalize completed and finalize-story is ready, "
                "but the cloud review export packet does not exist."
            )
        return workflow_run_cloud_review_prep_recommendation(
            evidence,
            reason,
        )

    if "cloud_review_result.yaml" not in evidence.result_data:
        return NextStepRecommendation(
            title="Record the cloud review result.",
            command=f"agentic record-cloud-review --story {evidence.story} --result-file <path>",
            reason=(
                "The cloud review packet exists, but the manual cloud review decision "
                "has not been recorded."
            ),
            details=[
                "Send cloud_review_packet/cloud_review_export.md for review first.",
                "Then record APPROVE, APPROVE_WITH_NOTES, or REQUEST_CHANGES.",
            ],
        )

    if "merge_readiness_result.yaml" not in evidence.result_data:
        return NextStepRecommendation(
            title="Run merge-readiness.",
            command=f"agentic merge-readiness --story {evidence.story}",
            reason="A cloud review result exists, but merge readiness has not been checked.",
            details=["This checks final local evidence for the human merge decision."],
        )

    if "remote_dev_validation_result.yaml" not in evidence.result_data:
        detail = "Remote dev validation has not been recorded."
        if evidence.remote_dev_packet_exists:
            detail = "A remote-dev packet exists, but validation has not been recorded."
        return NextStepRecommendation(
            title="Run remote-dev-packet.",
            command=f"agentic remote-dev-packet --story {evidence.story}",
            reason=(
                "Merge readiness exists, but remote dev validation is not recorded yet."
            ),
            details=[detail, "Remote dev validation is manual evidence, not a deployment."],
        )

    if ready_for_human_review(evidence):
        return NextStepRecommendation(
            title="Human PR/CI review is next.",
            command=None,
            reason=(
                "Merge readiness and/or remote dev validation indicate readiness for "
                "human review."
            ),
            details=[
                "The human owner should review the PR and confirm CI is passing.",
                "Human final approval is always required before merge.",
            ],
        )

    return NextStepRecommendation(
        title="Review current workflow evidence.",
        command=None,
        reason=(
            "The story has later-stage evidence, but no clear ready state was found. "
            "Review the reports before continuing."
        ),
        details=["Rerun merge-readiness after correcting or refreshing evidence."],
    )


def workflow_run_local_finalize_recommendation(
    evidence: StoryEvidence,
    reason: str,
) -> NextStepRecommendation:
    return NextStepRecommendation(
        title="Run workflow-run local-finalize.",
        command=f"agentic workflow-run --story {evidence.story} --phase local-finalize --execute",
        reason=reason,
        details=[
            "Required agent reports are present.",
            "workflow-run local-finalize runs the safe local finalization allowlist.",
            (
                "It does not execute agents through the configured agent runtime, call cloud "
                "models, call GitHub APIs, commit, push, merge, or deploy."
            ),
        ],
    )


def workflow_run_cloud_review_prep_recommendation(
    evidence: StoryEvidence,
    reason: str,
) -> NextStepRecommendation:
    return NextStepRecommendation(
        title="Run workflow-run cloud-review-prep.",
        command=f"agentic workflow-run --story {evidence.story} --phase cloud-review-prep --execute",
        reason=reason,
        details=[
            "Expected cloud_review_packet/cloud_review_export.md.",
            "workflow-run cloud-review-prep wraps cloud-review-packet and workflow-preview safely.",
            (
                "It creates local cloud review evidence only; it does not call cloud models, "
                "call GitHub APIs, commit, push, merge, or deploy."
            ),
        ],
    )


def find_bad_result_values(evidence: StoryEvidence) -> list[str]:
    findings: list[str] = []
    if text_value(evidence.status_data.get("status")) in BAD_RESULT_VALUES:
        findings.append(f"status.yaml status is {evidence.status_data.get('status')}.")

    for filename, data in evidence.result_data.items():
        matches = sorted(find_values(data, BAD_RESULT_VALUES))
        if matches:
            findings.append(f"{filename} contains: {', '.join(matches)}.")

    return findings


def find_unsafe_workflow_run_flags(evidence: StoryEvidence) -> list[str]:
    workflow_run_result = evidence.result_data.get("workflow_run_result.yaml")
    if not workflow_run_result:
        return []

    findings = [
        f"workflow_run_result.yaml has {flag}: true."
        for flag in WORKFLOW_RUN_UNSAFE_FLAGS
        if workflow_run_result.get(flag) is True
    ]
    return findings


def find_values(value: Any, expected: set[str]) -> set[str]:
    if isinstance(value, dict):
        matches: set[str] = set()
        for child in value.values():
            matches.update(find_values(child, expected))
        return matches

    if isinstance(value, list):
        matches = set()
        for child in value:
            matches.update(find_values(child, expected))
        return matches

    if isinstance(value, str) and value in expected:
        return {value}

    return set()


def finalize_result_ready(finalize_result: dict[str, Any]) -> bool:
    return (
        finalize_result.get("ready_for_review") is True
        or finalize_result.get("status") == "ready_for_review"
    )


def workflow_run_completed(workflow_run_result: dict[str, Any] | None) -> bool:
    if not workflow_run_result:
        return False

    return (
        workflow_run_result.get("status") == "completed"
        and workflow_run_result.get("executed") is True
    )


def workflow_run_phase_completed(
    workflow_run_result: dict[str, Any] | None,
    phase: str,
) -> bool:
    return workflow_run_completed(workflow_run_result) and workflow_run_result.get("phase") == phase


def workflow_run_failed(workflow_run_result: dict[str, Any] | None) -> bool:
    if not workflow_run_result:
        return False

    return workflow_run_result.get("status") == "failed"


def finalize_result_stale(evidence: StoryEvidence) -> bool:
    finalize_path = evidence.reports_path / "finalize_story_result.yaml"
    if not finalize_path.exists():
        return False

    finalize_mtime = finalize_path.stat().st_mtime
    evidence_paths = [
        evidence.story_path / "story.md",
        evidence.story_path / "test_plan.yaml",
        evidence.story_path / "monitoring_plan.yaml",
        evidence.story_path / "agent_plan.yaml",
        evidence.reports_path / "developer_report.md",
        evidence.reports_path / "test_report.md",
        evidence.reports_path / "local_review_report.md",
        evidence.reports_path / "test_layer_result.yaml",
        evidence.reports_path / "quality_gate_result.yaml",
    ]

    return any(path.exists() and path.stat().st_mtime > finalize_mtime for path in evidence_paths)


def ready_for_human_review(evidence: StoryEvidence) -> bool:
    remote_dev = evidence.result_data.get("remote_dev_validation_result.yaml", {})
    merge_readiness = evidence.result_data.get("merge_readiness_result.yaml", {})
    remote_status = text_value(remote_dev.get("validation_status"))
    merge_status = text_value(merge_readiness.get("status"))

    return remote_status in READY_REMOTE_DEV_STATUSES or merge_status in READY_MERGE_STATUSES


def write_next_step_report(
    report_path: Path,
    evidence: StoryEvidence,
    recommendation: NextStepRecommendation,
) -> None:
    content = f"""# Next Step Report

## Story

{evidence.story}

## Recommendation

{recommendation.title}

## Suggested command

{recommendation.command or "No command. Human review or manual correction is required."}

## Why

{recommendation.reason}

## Details

{format_bullet_list(recommendation.details)}
## Evidence inspected

- status.yaml status: {text_value(evidence.status_data.get("status")) or "missing"}
- ready_for_review: {format_optional_bool(evidence.status_data.get("ready_for_review"))}
- agent_plan.yaml: {format_bool(evidence.agent_plan_exists)}
- prompt_pack: {format_bool(evidence.prompt_pack_exists)} ({len(evidence.prompt_files)} prompt file(s))
- reports: {format_path_names(evidence.reports)}
- review_bundle: {format_path_names(evidence.review_bundle_files)}
- cloud_review_packet/cloud_review_export.md: {format_bool(evidence.cloud_review_export_exists)}
- remote_dev_validation/remote_dev_packet.md: {format_bool(evidence.remote_dev_packet_exists)}
- test_plan.yaml uses test_layers_version: 1: {format_bool(evidence.test_plan_uses_layers)}
- result files: {format_result_files(evidence.result_data)}

## Warnings

{format_bullet_list(evidence.warnings or ["None."])}
## Safety reminders

- This command did not execute the recommended command.
- This command did not call cloud models or GitHub APIs.
- This command did not commit, push, merge, deploy, or recommend automatic merge or deployment.
- Human final approval is always required before merge.
"""

    report_path.write_text(content, encoding="utf-8")


def format_terminal_summary(
    story: str,
    recommendation: NextStepRecommendation,
    report_path: Path,
) -> str:
    lines = [
        f"Next step for {story}:",
        f"Recommendation: {recommendation.title}",
        f"Why: {recommendation.reason}",
    ]
    if recommendation.command:
        lines.append(f"Suggested command: {recommendation.command}")
    else:
        lines.append("Suggested command: none")
    lines.extend(
        [
            "Reminder: do not merge or deploy automatically. Human final approval is required.",
            f"Report written to: {report_path}",
        ]
    )
    return "\n".join(lines)


def format_bullet_list(items: list[str]) -> str:
    if not items:
        return "- None.\n"

    return "\n".join(f"- {item}" for item in items) + "\n"


def format_path_names(paths: list[Path]) -> str:
    if not paths:
        return "none"

    return ", ".join(path.name for path in paths)


def format_result_files(result_data: dict[str, dict[str, Any]]) -> str:
    if not result_data:
        return "none"

    return ", ".join(sorted(result_data))


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def format_optional_bool(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()

    return "missing"


def text_value(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def list_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [str(item) for item in value if str(item).strip()]


def format_inline_list(values: list[str]) -> str:
    if not values:
        return "none recorded."

    return "; ".join(values)
