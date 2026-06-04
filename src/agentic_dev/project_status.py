from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.queue_management import QUEUE_STATUSES, QUEUE_TYPES, count_queue_items
from agentic_dev.remote_dev_validation import ACCEPTED_VALIDATION_STATUSES


NOT_STARTED = "NOT_STARTED"
IN_PROGRESS = "IN_PROGRESS"
BLOCKED = "BLOCKED"
READY_FOR_REVIEW = "READY_FOR_REVIEW"
REQUEST_CHANGES = "REQUEST_CHANGES"
CLOUD_REVIEW_RECORDED = "CLOUD_REVIEW_RECORDED"
READY_FOR_HUMAN_MERGE_DECISION = "READY_FOR_HUMAN_MERGE_DECISION"
UNKNOWN = "UNKNOWN"

PASSED = "PASSED"

WORKFLOW_RUN_SAFETY_FLAGS = (
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

SUPPORT_QUEUE_FOLDERS = (
    "pending",
    "answered",
    "escalated_to_human",
    "closed",
)


@dataclass(frozen=True)
class StoryProjectStatus:
    story: str
    story_path: Path
    story_id: str | None
    status: str | None
    ready_for_review: bool | None
    blocked_by: str | None
    support_ticket_blocking: bool
    support_ticket_queue: str | None
    agent_plan_exists: bool
    prompt_pack_exists: bool
    prompt_file_count: int
    test_layer_exists: bool
    test_layer_status: str | None
    test_layer_passed: bool | None
    quality_gate_exists: bool
    quality_gate_status: str | None
    quality_gate_ready: bool | None
    finalize_exists: bool
    finalize_status: str | None
    finalize_ready: bool | None
    workflow_run_exists: bool
    workflow_run_phase: str | None
    workflow_run_status: str | None
    workflow_run_executed: bool | None
    workflow_run_safety_summary: str
    cloud_review_exists: bool
    cloud_review_decision: str | None
    remote_dev_validation_exists: bool
    remote_dev_validation_status: str | None
    merge_readiness_exists: bool
    merge_readiness_status: str | None
    local_review_ready: bool
    developer_report_exists: bool
    test_report_exists: bool
    review_bundle_handoff_exists: bool
    cloud_review_export_exists: bool
    category: str
    missing_evidence: list[str]
    warnings: list[str]
    next_action: str


@dataclass(frozen=True)
class ProjectStatusResult:
    project_path: Path
    report_path: Path
    stories: list[StoryProjectStatus]
    summary_counts: dict[str, int]
    queue_counts: dict[str, dict[str, int]]
    terminal_summary: str


def run_project_status(project_path: Path, story: str | None = None) -> ProjectStatusResult:
    project_path = project_path.resolve()
    stories_path = project_path / "stories"

    if not stories_path.exists():
        raise FileNotFoundError(f"Stories folder does not exist: {stories_path}")

    if not stories_path.is_dir():
        raise ValueError(f"Stories path is not a folder: {stories_path}")

    story_paths = find_story_paths(stories_path, story)
    story_statuses = [collect_story_status(project_path, story_path) for story_path in story_paths]
    summary_counts = build_summary_counts(story_statuses)
    queue_counts = count_queue_items(project_path)

    reports_path = project_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)
    report_path = reports_path / "project_status_report.md"

    terminal_summary = format_terminal_summary(
        project_path,
        story_statuses,
        summary_counts,
        queue_counts,
    )
    report_path.write_text(
        format_markdown_report(project_path, story_statuses, summary_counts, queue_counts),
        encoding="utf-8",
    )

    return ProjectStatusResult(
        project_path=project_path,
        report_path=report_path,
        stories=story_statuses,
        summary_counts=summary_counts,
        queue_counts=queue_counts,
        terminal_summary=terminal_summary,
    )


def find_story_paths(stories_path: Path, story: str | None) -> list[Path]:
    if story:
        story_path = stories_path / story
        if not story_path.exists():
            raise FileNotFoundError(f"Story folder does not exist: {story_path}")
        if not story_path.is_dir():
            raise ValueError(f"Story path is not a folder: {story_path}")
        return [story_path]

    return sorted(path for path in stories_path.iterdir() if path.is_dir())


def collect_story_status(project_path: Path, story_path: Path) -> StoryProjectStatus:
    story = story_path.name
    reports_path = story_path / "reports"
    warnings: list[str] = []

    status_path = story_path / "status.yaml"
    test_layer_path = reports_path / "test_layer_result.yaml"
    quality_gate_path = reports_path / "quality_gate_result.yaml"
    finalize_path = reports_path / "finalize_story_result.yaml"
    workflow_run_path = reports_path / "workflow_run_result.yaml"
    cloud_review_path = reports_path / "cloud_review_result.yaml"
    remote_dev_validation_path = reports_path / "remote_dev_validation_result.yaml"
    merge_readiness_path = reports_path / "merge_readiness_result.yaml"

    status_data = load_optional_yaml_mapping(status_path, warnings)
    test_layer_data = load_optional_yaml_mapping(test_layer_path, warnings)
    quality_gate_data = load_optional_yaml_mapping(quality_gate_path, warnings)
    finalize_data = load_optional_yaml_mapping(finalize_path, warnings)
    workflow_run_data = load_optional_yaml_mapping(workflow_run_path, warnings)
    cloud_review_data = load_optional_yaml_mapping(cloud_review_path, warnings)
    remote_dev_validation_data = load_optional_yaml_mapping(remote_dev_validation_path, warnings)
    merge_readiness_data = load_optional_yaml_mapping(merge_readiness_path, warnings)

    blocked_by = optional_text(status_data.get("blocked_by"))
    support_ticket_queue = find_support_ticket_queue(project_path, blocked_by)
    support_ticket_blocking = is_support_ticket_blocking(status_data, blocked_by, support_ticket_queue)

    prompt_pack_path = story_path / "prompt_pack"
    prompt_files = find_prompt_files(prompt_pack_path)

    local_review_path = reports_path / "local_review_report.md"
    local_review_ready = text_file_contains(local_review_path, READY_FOR_REVIEW)

    test_layer_status = optional_text(test_layer_data.get("status"))
    quality_gate_status = optional_text(quality_gate_data.get("status"))
    finalize_status = optional_text(finalize_data.get("status"))
    workflow_run_phase = optional_text(workflow_run_data.get("phase"))
    workflow_run_status = optional_text(workflow_run_data.get("status"))
    workflow_run_executed = optional_bool(workflow_run_data.get("executed"))
    workflow_run_safety_summary = format_workflow_run_safety_summary(
        workflow_run_path.exists(),
        workflow_run_data,
    )
    cloud_review_decision = optional_text(cloud_review_data.get("decision"))
    remote_dev_validation_status = optional_text(remote_dev_validation_data.get("validation_status"))
    if (
        remote_dev_validation_path.exists()
        and remote_dev_validation_status
        and remote_dev_validation_status not in ACCEPTED_VALIDATION_STATUSES
    ):
        warnings.append(
            "Invalid remote dev validation_status "
            f"{remote_dev_validation_status!r} in {relative_display(remote_dev_validation_path)}."
        )
    elif remote_dev_validation_path.exists() and not remote_dev_validation_status:
        warnings.append(
            "Missing remote dev validation_status in "
            f"{relative_display(remote_dev_validation_path)}."
        )
    merge_readiness_status = optional_text(merge_readiness_data.get("status"))

    missing_evidence = collect_missing_evidence(
        story_path=story_path,
        prompt_file_count=len(prompt_files),
        local_review_ready=local_review_ready,
    )

    category = categorize_story(
        status=optional_text(status_data.get("status")),
        ready_for_review=optional_bool(status_data.get("ready_for_review")),
        support_ticket_blocking=support_ticket_blocking,
        agent_plan_exists=(story_path / "agent_plan.yaml").exists(),
        prompt_file_count=len(prompt_files),
        developer_report_exists=(reports_path / "developer_report.md").exists(),
        test_report_exists=(reports_path / "test_report.md").exists(),
        quality_gate_status=quality_gate_status,
        quality_gate_ready=optional_bool(quality_gate_data.get("ready_for_review")),
        finalize_ready=optional_bool(finalize_data.get("ready_for_review")),
        cloud_review_decision=cloud_review_decision,
        merge_readiness_status=merge_readiness_status,
    )
    next_action = build_next_action(
        category=category,
        support_ticket=blocked_by,
        missing_evidence=missing_evidence,
        cloud_review_exists=cloud_review_path.exists(),
        cloud_review_export_exists=(story_path / "cloud_review_packet" / "cloud_review_export.md").exists(),
        merge_readiness_exists=merge_readiness_path.exists(),
    )

    return StoryProjectStatus(
        story=story,
        story_path=story_path,
        story_id=optional_text(status_data.get("story_id")),
        status=optional_text(status_data.get("status")),
        ready_for_review=optional_bool(status_data.get("ready_for_review")),
        blocked_by=blocked_by,
        support_ticket_blocking=support_ticket_blocking,
        support_ticket_queue=support_ticket_queue,
        agent_plan_exists=(story_path / "agent_plan.yaml").exists(),
        prompt_pack_exists=prompt_pack_path.exists() and prompt_pack_path.is_dir(),
        prompt_file_count=len(prompt_files),
        test_layer_exists=test_layer_path.exists(),
        test_layer_status=test_layer_status,
        test_layer_passed=report_passed(test_layer_data, "status", PASSED),
        quality_gate_exists=quality_gate_path.exists(),
        quality_gate_status=quality_gate_status,
        quality_gate_ready=optional_bool(quality_gate_data.get("ready_for_review")),
        finalize_exists=finalize_path.exists(),
        finalize_status=finalize_status,
        finalize_ready=optional_bool(finalize_data.get("ready_for_review")),
        workflow_run_exists=workflow_run_path.exists(),
        workflow_run_phase=workflow_run_phase,
        workflow_run_status=workflow_run_status,
        workflow_run_executed=workflow_run_executed,
        workflow_run_safety_summary=workflow_run_safety_summary,
        cloud_review_exists=cloud_review_path.exists(),
        cloud_review_decision=cloud_review_decision,
        remote_dev_validation_exists=remote_dev_validation_path.exists(),
        remote_dev_validation_status=remote_dev_validation_status,
        merge_readiness_exists=merge_readiness_path.exists(),
        merge_readiness_status=merge_readiness_status,
        local_review_ready=local_review_ready,
        developer_report_exists=(reports_path / "developer_report.md").exists(),
        test_report_exists=(reports_path / "test_report.md").exists(),
        review_bundle_handoff_exists=(story_path / "review_bundle" / "handoff.md").exists(),
        cloud_review_export_exists=(
            story_path / "cloud_review_packet" / "cloud_review_export.md"
        ).exists(),
        category=category,
        missing_evidence=missing_evidence,
        warnings=warnings,
        next_action=next_action,
    )


def load_optional_yaml_mapping(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as yaml_file:
            loaded = yaml.safe_load(yaml_file)
    except yaml.YAMLError as error:
        warnings.append(f"Invalid YAML in {relative_display(path)}: {error}")
        return {}

    if loaded is None:
        return {}

    if not isinstance(loaded, dict):
        warnings.append(f"Expected YAML mapping in {relative_display(path)}.")
        return {}

    return loaded


def find_support_ticket_queue(project_path: Path, ticket_id: str | None) -> str | None:
    if not ticket_id:
        return None

    queue_root = project_path / ".agentic" / "support_queue"
    for queue_name in SUPPORT_QUEUE_FOLDERS:
        if (queue_root / queue_name / f"{ticket_id}.yaml").exists():
            return queue_name

    return None


def is_support_ticket_blocking(
    status_data: dict[str, Any],
    blocked_by: str | None,
    support_ticket_queue: str | None,
) -> bool:
    if optional_text(status_data.get("status")) == "blocked":
        return True

    if not blocked_by:
        return False

    return support_ticket_queue != "closed"


def find_prompt_files(prompt_pack_path: Path) -> list[Path]:
    if not prompt_pack_path.exists() or not prompt_pack_path.is_dir():
        return []

    return sorted(
        path
        for path in prompt_pack_path.iterdir()
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )


def text_file_contains(path: Path, expected_text: str) -> bool:
    if not path.exists() or not path.is_file():
        return False

    return expected_text in path.read_text(encoding="utf-8", errors="replace")


def collect_missing_evidence(
    story_path: Path,
    prompt_file_count: int,
    local_review_ready: bool,
) -> list[str]:
    checks = [
        ("status.yaml", story_path / "status.yaml"),
        ("agent_plan.yaml", story_path / "agent_plan.yaml"),
        ("reports/developer_report.md", story_path / "reports" / "developer_report.md"),
        ("reports/test_report.md", story_path / "reports" / "test_report.md"),
        ("review_bundle/handoff.md", story_path / "review_bundle" / "handoff.md"),
        ("reports/test_layer_result.yaml", story_path / "reports" / "test_layer_result.yaml"),
        ("reports/quality_gate_result.yaml", story_path / "reports" / "quality_gate_result.yaml"),
        (
            "reports/finalize_story_result.yaml",
            story_path / "reports" / "finalize_story_result.yaml",
        ),
        ("reports/cloud_review_result.yaml", story_path / "reports" / "cloud_review_result.yaml"),
        (
            "reports/merge_readiness_result.yaml",
            story_path / "reports" / "merge_readiness_result.yaml",
        ),
        (
            "cloud_review_packet/cloud_review_export.md",
            story_path / "cloud_review_packet" / "cloud_review_export.md",
        ),
    ]

    missing = [label for label, path in checks if not path.exists()]

    if prompt_file_count == 0:
        missing.append("prompt_pack prompt files")

    if not local_review_ready:
        missing.append("reports/local_review_report.md with READY_FOR_REVIEW")

    return missing


def categorize_story(
    status: str | None,
    ready_for_review: bool | None,
    support_ticket_blocking: bool,
    agent_plan_exists: bool,
    prompt_file_count: int,
    developer_report_exists: bool,
    test_report_exists: bool,
    quality_gate_status: str | None,
    quality_gate_ready: bool | None,
    finalize_ready: bool | None,
    cloud_review_decision: str | None,
    merge_readiness_status: str | None,
) -> str:
    normalized_status = (status or "").upper()

    if support_ticket_blocking:
        return BLOCKED

    if merge_readiness_status in {
        READY_FOR_HUMAN_MERGE_DECISION,
        "READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION",
    }:
        return READY_FOR_HUMAN_MERGE_DECISION

    if (
        cloud_review_decision == REQUEST_CHANGES
        or quality_gate_status == REQUEST_CHANGES
        or normalized_status == REQUEST_CHANGES
    ):
        return REQUEST_CHANGES

    if cloud_review_decision:
        return CLOUD_REVIEW_RECORDED

    if ready_for_review is True or quality_gate_ready is True or finalize_ready is True:
        return READY_FOR_REVIEW

    if not any([agent_plan_exists, prompt_file_count, developer_report_exists, test_report_exists]):
        return NOT_STARTED

    if status:
        return IN_PROGRESS

    return UNKNOWN


def build_next_action(
    category: str,
    support_ticket: str | None,
    missing_evidence: list[str],
    cloud_review_exists: bool,
    cloud_review_export_exists: bool,
    merge_readiness_exists: bool,
) -> str:
    if category == BLOCKED:
        ticket_text = f" {support_ticket}" if support_ticket else ""
        return f"Resolve the blocking support ticket{ticket_text}, then resume story work."

    if category == READY_FOR_HUMAN_MERGE_DECISION:
        return "Human owner should review the PR and make the final merge decision."

    if category == REQUEST_CHANGES:
        return "Address requested changes, refresh evidence, and rerun the failed gate."

    if category == CLOUD_REVIEW_RECORDED and not merge_readiness_exists:
        return "Run merge-readiness so the human owner can make a merge decision."

    if category == READY_FOR_REVIEW and not cloud_review_export_exists:
        return "Run cloud-review-packet, then send the export for human or cloud review."

    if category == READY_FOR_REVIEW and not cloud_review_exists:
        return "Record the human or cloud review decision when it is available."

    if missing_evidence:
        return f"Add or regenerate missing evidence, starting with {missing_evidence[0]}."

    return "Review the story state and continue the next workflow step."


def build_summary_counts(stories: list[StoryProjectStatus]) -> dict[str, int]:
    counts = {
        "total": len(stories),
        "ready_stories": 0,
        "blocked_stories": 0,
        "stories_needing_changes": 0,
        "stories_missing_evidence": 0,
        "ready_for_human_or_cloud_review": 0,
        "ready_for_human_merge_decision": 0,
    }

    for story in stories:
        if story.category == READY_FOR_REVIEW:
            counts["ready_stories"] += 1
            counts["ready_for_human_or_cloud_review"] += 1
        if story.category == BLOCKED:
            counts["blocked_stories"] += 1
        if story.category == REQUEST_CHANGES:
            counts["stories_needing_changes"] += 1
        if story.missing_evidence:
            counts["stories_missing_evidence"] += 1
        if story.category == READY_FOR_HUMAN_MERGE_DECISION:
            counts["ready_for_human_merge_decision"] += 1

    for category in [
        NOT_STARTED,
        IN_PROGRESS,
        BLOCKED,
        READY_FOR_REVIEW,
        REQUEST_CHANGES,
        CLOUD_REVIEW_RECORDED,
        READY_FOR_HUMAN_MERGE_DECISION,
        UNKNOWN,
    ]:
        counts[category] = sum(1 for story in stories if story.category == category)

    return counts


def format_terminal_summary(
    project_path: Path,
    stories: list[StoryProjectStatus],
    summary_counts: dict[str, int],
    queue_counts: dict[str, dict[str, int]],
) -> str:
    lines = [
        f"Project status for: {project_path}",
        f"Stories: {summary_counts['total']}",
        "",
        "Summary:",
        f"  Ready for human/cloud review: {summary_counts['ready_for_human_or_cloud_review']}",
        f"  Ready for human merge decision: {summary_counts['ready_for_human_merge_decision']}",
        f"  Blocked: {summary_counts['blocked_stories']}",
        f"  Needing changes: {summary_counts['stories_needing_changes']}",
        f"  Missing evidence: {summary_counts['stories_missing_evidence']}",
        "",
        "Queues:",
    ]

    for queue_type in QUEUE_TYPES:
        counts = queue_counts[queue_type]
        status_text = ", ".join(f"{status}={counts[status]}" for status in QUEUE_STATUSES)
        lines.append(f"  {queue_type}: total={counts['total']} ({status_text})")

    lines.extend(
        [
            "",
            "Stories:",
        ]
    )

    if not stories:
        lines.append("  - none")
        return "\n".join(lines)

    for story in stories:
        status_text = story.status or "missing"
        ready_text = format_optional_bool(story.ready_for_review)
        missing_text = f"{len(story.missing_evidence)} missing" if story.missing_evidence else "complete"
        lines.append(
            "  - "
            f"{story.story}: {story.category} | status={status_text} "
            f"| ready={ready_text} | evidence={missing_text}"
        )
        if story.blocked_by:
            queue_text = story.support_ticket_queue or "not found"
            lines.append(f"    blocked_by={story.blocked_by} ({queue_text})")
        if story.cloud_review_decision:
            lines.append(f"    cloud_review={story.cloud_review_decision}")
        workflow_run_status = story.workflow_run_status or "not recorded"
        workflow_run_phase = story.workflow_run_phase or "not recorded"
        lines.append(
            "    "
            f"workflow_run={workflow_run_status} "
            f"(phase={workflow_run_phase}, executed={format_optional_bool(story.workflow_run_executed)})"
        )
        lines.append(f"    workflow_run_safety_summary={story.workflow_run_safety_summary}")
        remote_dev_status = story.remote_dev_validation_status or "not recorded"
        lines.append(f"    remote_dev_validation={remote_dev_status}")
        if story.merge_readiness_status:
            lines.append(f"    merge_readiness={story.merge_readiness_status}")
        lines.append(f"    next: {story.next_action}")

    return "\n".join(lines)


def format_markdown_report(
    project_path: Path,
    stories: list[StoryProjectStatus],
    summary_counts: dict[str, int],
    queue_counts: dict[str, dict[str, int]],
) -> str:
    lines = [
        "# Project Status Report",
        "",
        "## Project",
        "",
        str(project_path),
        "",
        "## Summary Counts",
        "",
        f"- Total stories: {summary_counts['total']}",
        f"- Ready for human/cloud review: {summary_counts['ready_for_human_or_cloud_review']}",
        f"- Ready for human merge decision: {summary_counts['ready_for_human_merge_decision']}",
        f"- Blocked stories: {summary_counts['blocked_stories']}",
        f"- Stories needing changes: {summary_counts['stories_needing_changes']}",
        f"- Stories missing evidence: {summary_counts['stories_missing_evidence']}",
        "",
        "## Status Categories",
        "",
    ]

    for category in [
        NOT_STARTED,
        IN_PROGRESS,
        BLOCKED,
        READY_FOR_REVIEW,
        REQUEST_CHANGES,
        CLOUD_REVIEW_RECORDED,
        READY_FOR_HUMAN_MERGE_DECISION,
        UNKNOWN,
    ]:
        lines.append(f"- {category}: {summary_counts[category]}")

    lines.extend(["", "## Queue Counts", ""])

    for queue_type in QUEUE_TYPES:
        counts = queue_counts[queue_type]
        lines.append(f"### {queue_type}")
        lines.append("")
        lines.append(f"- Total: {counts['total']}")
        for status in QUEUE_STATUSES:
            lines.append(f"- {status}: {counts[status]}")
        lines.append("")

    lines.extend(["## Stories", ""])

    if not stories:
        lines.extend(["No story workspaces found.", ""])
    else:
        for story in stories:
            lines.extend(format_story_section(story))

    lines.extend(
        [
            "## Safety Notes",
            "",
            "- This command only reads story evidence and writes this project-level report.",
            "- It does not call cloud models, call GitHub APIs, commit, push, merge, or deploy.",
            "",
        ]
    )

    return "\n".join(lines)


def format_story_section(story: StoryProjectStatus) -> list[str]:
    support_ticket = "none"
    if story.blocked_by:
        support_ticket = story.blocked_by
        if story.support_ticket_queue:
            support_ticket = f"{support_ticket} ({story.support_ticket_queue})"

    return [
        f"### {story.story}",
        "",
        f"- Category: {story.category}",
        f"- Story ID: {story.story_id or 'missing'}",
        f"- status.yaml status: {story.status or 'missing'}",
        f"- ready_for_review: {format_optional_bool(story.ready_for_review)}",
        f"- Blocking support ticket: {support_ticket}",
        f"- agent_plan.yaml: {format_bool(story.agent_plan_exists)}",
        (
            "- prompt_pack prompts: "
            f"{story.prompt_file_count} ({format_bool(story.prompt_file_count > 0)})"
        ),
        (
            "- test_layer_result.yaml: "
            f"{format_present(story.test_layer_exists)}, status={story.test_layer_status or 'missing'} "
            f"(passed: {format_optional_bool(story.test_layer_passed)})"
        ),
        (
            "- quality_gate_result.yaml: "
            f"{format_present(story.quality_gate_exists)}, "
            f"status={story.quality_gate_status or 'missing'} "
            f"(ready: {format_optional_bool(story.quality_gate_ready)})"
        ),
        (
            "- finalize_story_result.yaml: "
            f"{format_present(story.finalize_exists)}, status={story.finalize_status or 'missing'} "
            f"(ready: {format_optional_bool(story.finalize_ready)})"
        ),
        (
            "- workflow_run_result.yaml: "
            f"{format_present(story.workflow_run_exists)}, "
            f"workflow_run_phase={story.workflow_run_phase or 'not recorded'}, "
            f"workflow_run_status={story.workflow_run_status or 'not recorded'}, "
            f"workflow_run_executed={format_optional_bool(story.workflow_run_executed)}"
        ),
        f"- workflow_run_safety_summary: {story.workflow_run_safety_summary}",
        (
            "- cloud_review_result.yaml: "
            f"{format_present(story.cloud_review_exists)}, "
            f"decision={story.cloud_review_decision or 'missing'}"
        ),
        (
            "- remote_dev_validation_result.yaml: "
            f"{format_present(story.remote_dev_validation_exists)}, "
            f"validation_status={story.remote_dev_validation_status or 'not recorded'}"
        ),
        (
            "- merge_readiness_result.yaml: "
            f"{format_present(story.merge_readiness_exists)}, "
            f"status={story.merge_readiness_status or 'missing'}"
        ),
        f"- local_review_report.md READY_FOR_REVIEW: {format_bool(story.local_review_ready)}",
        f"- developer_report.md: {format_bool(story.developer_report_exists)}",
        f"- test_report.md: {format_bool(story.test_report_exists)}",
        f"- review_bundle/handoff.md: {format_bool(story.review_bundle_handoff_exists)}",
        f"- cloud_review_packet/cloud_review_export.md: {format_bool(story.cloud_review_export_exists)}",
        "",
        "Missing evidence:",
        format_list(story.missing_evidence),
        "Warnings:",
        format_list(story.warnings),
        "Next recommended action:",
        "",
        story.next_action,
        "",
    ]


def report_passed(data: dict[str, Any], key: str, expected: str) -> bool | None:
    if not data:
        return None

    return data.get(key) == expected


def format_workflow_run_safety_summary(
    workflow_run_exists: bool,
    workflow_run_data: dict[str, Any],
) -> str:
    if not workflow_run_exists:
        return "not recorded"

    if not workflow_run_data:
        return "unavailable; see warnings"

    return ", ".join(
        f"{flag}={format_optional_bool(optional_bool(workflow_run_data.get(flag)))}"
        for flag in WORKFLOW_RUN_SAFETY_FLAGS
    )


def optional_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value

    return None


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def format_present(value: bool) -> str:
    return "present" if value else "missing"


def format_optional_bool(value: bool | None) -> str:
    if value is None:
        return "missing"

    return format_bool(value)


def format_list(items: list[str]) -> str:
    if not items:
        return "- None\n"

    return "\n".join(f"- {item}" for item in items) + "\n"


def relative_display(path: Path) -> str:
    return str(path)
