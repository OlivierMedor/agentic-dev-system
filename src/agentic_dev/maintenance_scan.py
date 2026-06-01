from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.queue_management import (
    NEXT_ACTION_BY_STATUS,
    ensure_queue_directories,
    generate_item_id,
    item_filename,
    timestamp_now,
    write_yaml_mapping,
)


MAINTENANCE_SCAN_PACKET_FILENAME = "maintenance_scan_packet.md"
MAINTENANCE_FINDINGS_TEMPLATE_FILENAME = "maintenance_findings_template.yaml"
MAINTENANCE_RECORD_REPORT_FILENAME = "maintenance_record_report.md"
MAINTENANCE_QUEUE_TYPE = "maintenance"

REQUIRED_FINDING_FIELDS = (
    "title",
    "severity",
    "source_type",
    "problem",
    "evidence",
    "suspected_cause",
    "recommended_action",
    "suggested_acceptance_criteria",
)

EVIDENCE_FILES = [
    ("story.md", "Story content"),
    ("monitoring_plan.yaml", "Monitoring plan"),
    ("test_plan.yaml", "Test plan"),
    ("status.yaml", "Story status"),
    ("reports/test_layer_result.yaml", "Test layer result"),
    ("reports/quality_gate_result.yaml", "Quality gate result"),
    ("reports/finalize_story_result.yaml", "Finalize story result"),
    ("reports/local_review_report.md", "Local review report"),
    ("review_bundle/handoff.md", "Review bundle handoff"),
    ("review_bundle/pytest_output.txt", "pytest output"),
    ("review_bundle/ruff_output.txt", "ruff output"),
]


@dataclass(frozen=True)
class MaintenanceScanCreateResult:
    story: str
    story_path: Path
    maintenance_path: Path
    packet_path: Path
    template_path: Path
    generated_files: list[Path]
    missing_optional_files: list[str]
    included_log_files: list[Path]


@dataclass(frozen=True)
class RecordedMaintenanceItem:
    item_id: str
    item_path: Path
    data: dict[str, Any]


@dataclass(frozen=True)
class MaintenanceScanRecordResult:
    story: str
    story_path: Path
    findings_file: Path
    report_path: Path
    queue_items: list[RecordedMaintenanceItem]


@dataclass(frozen=True)
class MaintenanceScanEvidence:
    present_files: list[tuple[str, str, str]]
    missing_files: list[str]
    log_files: list[tuple[str, Path, str]]


def create_maintenance_scan_packet(
    project_path: Path,
    story: str,
    force: bool = False,
    logs_path: Path | None = None,
) -> MaintenanceScanCreateResult:
    """Create a reactive maintenance scan packet without calling external services."""
    project_path = project_path.resolve()
    story_path = validate_story_path(project_path, story)
    maintenance_path = story_path / "maintenance"
    packet_path = maintenance_path / MAINTENANCE_SCAN_PACKET_FILENAME
    template_path = maintenance_path / MAINTENANCE_FINDINGS_TEMPLATE_FILENAME

    existing_files = [path for path in (packet_path, template_path) if path.exists()]
    if existing_files and not force:
        existing_list = ", ".join(str(path) for path in existing_files)
        raise ValueError(
            "Maintenance scan files already exist: "
            f"{existing_list}. Use --force to overwrite.",
        )

    evidence = read_maintenance_scan_evidence(story_path, logs_path)
    packet = build_maintenance_scan_packet(story, evidence)
    template = build_findings_template()

    write_text(packet_path, packet)
    write_text(template_path, template)

    return MaintenanceScanCreateResult(
        story=story,
        story_path=story_path,
        maintenance_path=maintenance_path,
        packet_path=packet_path,
        template_path=template_path,
        generated_files=[packet_path, template_path],
        missing_optional_files=evidence.missing_files,
        included_log_files=[path for _, path, _ in evidence.log_files],
    )


def record_maintenance_findings(
    project_path: Path,
    story: str,
    findings_file: Path,
) -> MaintenanceScanRecordResult:
    """Record validated maintenance findings into the pending maintenance queue."""
    project_path = project_path.resolve()
    story_path = validate_story_path(project_path, story)
    findings_path = findings_file.resolve()

    if not findings_path.exists():
        raise FileNotFoundError(f"Maintenance findings file does not exist: {findings_path}")

    if not findings_path.is_file():
        raise ValueError(f"Maintenance findings path is not a file: {findings_path}")

    findings = load_and_validate_findings(findings_path)
    queue_items = write_maintenance_queue_items(project_path, story, findings)

    report_path = story_path / "maintenance" / MAINTENANCE_RECORD_REPORT_FILENAME
    write_maintenance_record_report(
        report_path=report_path,
        story=story,
        findings_path=findings_path,
        queue_items=queue_items,
    )

    return MaintenanceScanRecordResult(
        story=story,
        story_path=story_path,
        findings_file=findings_path,
        report_path=report_path,
        queue_items=queue_items,
    )


def validate_story_path(project_path: Path, story: str) -> Path:
    story_path = project_path / "stories" / story

    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    return story_path


def read_maintenance_scan_evidence(
    story_path: Path,
    logs_path: Path | None,
) -> MaintenanceScanEvidence:
    present_files: list[tuple[str, str, str]] = []
    missing_files: list[str] = []

    for relative_path, label in EVIDENCE_FILES:
        path = story_path / relative_path
        if path.exists() and path.is_file():
            present_files.append((relative_path, label, read_text(path)))
        else:
            missing_files.append(relative_path)

    log_files = read_log_files(logs_path) if logs_path is not None else []

    return MaintenanceScanEvidence(
        present_files=present_files,
        missing_files=missing_files,
        log_files=log_files,
    )


def read_log_files(logs_path: Path) -> list[tuple[str, Path, str]]:
    resolved_logs_path = logs_path.resolve()

    if not resolved_logs_path.exists():
        raise FileNotFoundError(f"Logs path does not exist: {resolved_logs_path}")

    if resolved_logs_path.is_file():
        return [(resolved_logs_path.name, resolved_logs_path, read_text(resolved_logs_path))]

    if not resolved_logs_path.is_dir():
        raise ValueError(f"Logs path is not a file or folder: {resolved_logs_path}")

    log_files: list[tuple[str, Path, str]] = []
    for path in sorted(resolved_logs_path.rglob("*")):
        if path.is_file():
            relative_path = str(path.relative_to(resolved_logs_path))
            log_files.append((relative_path, path, read_text(path)))

    return log_files


def build_maintenance_scan_packet(story: str, evidence: MaintenanceScanEvidence) -> str:
    sections = [
        "# Maintenance Scan Packet",
        "",
        "This packet is for a reactive maintenance scan. Use only the context in this file.",
        "Do not call cloud models automatically. Do not call internet search.",
        "",
        "## Reviewer instructions",
        "",
        "- identify broken behavior, regressions, failing checks, missing evidence, or external dependency failures.",
        "- do not implement fixes.",
        "- do not expand scope.",
        "- create findings for maintenance queue review.",
        "- use the findings template format.",
        "",
        "## Story name",
        "",
        story,
        "",
    ]

    for relative_path, label, content in evidence.present_files:
        sections.extend(
            [
                f"## {label}",
                "",
                f"Source: `{relative_path}`",
                "",
                fenced(format_hint(relative_path), content),
                "",
            ],
        )

    sections.extend(
        [
            "## Optional log files",
            "",
            format_log_files(evidence.log_files),
            "",
            "## Missing optional evidence",
            "",
            format_missing_optional_evidence(evidence.missing_files),
            "",
        ],
    )

    return "\n".join(sections).rstrip() + "\n"


def build_findings_template() -> str:
    return """findings:
  - title: External API endpoint may have changed
    severity: high
    source_type: logs
    problem: Explain the failure.
    evidence:
      - Include relevant log or test output.
    suspected_cause: Explain suspected cause.
    recommended_action: Explain the repair direction.
    suggested_acceptance_criteria:
      - Add or update tests.
      - Update docs if behavior changes.
"""


def load_and_validate_findings(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file_handle:
        loaded = yaml.safe_load(file_handle)

    if not isinstance(loaded, dict):
        raise ValueError(f"Maintenance findings YAML must contain a mapping: {path}")

    findings = loaded.get("findings")
    if not isinstance(findings, list):
        raise ValueError("Maintenance findings YAML must include a top-level findings list.")

    if not findings:
        raise ValueError("Maintenance findings list must contain at least one finding.")

    return [
        validate_finding(index=index, finding=finding)
        for index, finding in enumerate(findings, start=1)
    ]


def validate_finding(index: int, finding: Any) -> dict[str, Any]:
    if not isinstance(finding, dict):
        raise ValueError(f"Finding {index} must be a YAML mapping.")

    missing_fields = [
        field
        for field in REQUIRED_FINDING_FIELDS
        if field not in finding or finding[field] in (None, "")
    ]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise ValueError(f"Finding {index} is missing required fields: {joined}.")

    evidence = finding["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"Finding {index} field evidence must be a non-empty list.")

    criteria = finding["suggested_acceptance_criteria"]
    if not isinstance(criteria, list) or not criteria:
        raise ValueError(
            "Finding "
            f"{index} field suggested_acceptance_criteria must be a non-empty list.",
        )

    return {
        "title": text_field(index, finding, "title"),
        "severity": text_field(index, finding, "severity"),
        "source_type": text_field(index, finding, "source_type"),
        "problem": text_field(index, finding, "problem"),
        "evidence": [
            text_list_item(index, "evidence", item_number, item)
            for item_number, item in enumerate(evidence, start=1)
        ],
        "suspected_cause": text_field(index, finding, "suspected_cause"),
        "recommended_action": text_field(index, finding, "recommended_action"),
        "suggested_acceptance_criteria": [
            text_list_item(index, "acceptance criterion", item_number, item)
            for item_number, item in enumerate(criteria, start=1)
        ],
    }


def text_field(index: int, finding: dict[str, Any], field: str) -> str:
    value = str(finding[field]).strip()
    if not value:
        raise ValueError(f"Finding {index} field {field} must not be blank.")

    return value


def text_list_item(index: int, field: str, item_number: int, item: Any) -> str:
    value = str(item).strip()
    if not value:
        raise ValueError(f"Finding {index} {field} {item_number} must not be blank.")

    return value


def write_maintenance_queue_items(
    project_path: Path,
    story: str,
    findings: list[dict[str, Any]],
) -> list[RecordedMaintenanceItem]:
    queue_items: list[RecordedMaintenanceItem] = []

    for finding in findings:
        directories = ensure_queue_directories(project_path, MAINTENANCE_QUEUE_TYPE)
        item_id = generate_item_id(MAINTENANCE_QUEUE_TYPE, directories)
        item_path = directories["pending"] / item_filename(item_id)
        item = build_queue_item(item_id, story, finding)
        write_yaml_mapping(item_path, item, allow_overwrite=False)
        queue_items.append(RecordedMaintenanceItem(item_id=item_id, item_path=item_path, data=item))

    return queue_items


def build_queue_item(
    item_id: str,
    story: str,
    finding: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": item_id,
        "queue_type": MAINTENANCE_QUEUE_TYPE,
        "title": finding["title"],
        "source_story": story,
        "severity": finding["severity"],
        "source_type": finding["source_type"],
        "status": "pending",
        "problem": finding["problem"],
        "evidence": finding["evidence"],
        "suspected_cause": finding["suspected_cause"],
        "recommended_action": finding["recommended_action"],
        "suggested_acceptance_criteria": finding["suggested_acceptance_criteria"],
        "created_at": timestamp_now(),
        "next_action": NEXT_ACTION_BY_STATUS["pending"],
    }


def write_maintenance_record_report(
    report_path: Path,
    story: str,
    findings_path: Path,
    queue_items: list[RecordedMaintenanceItem],
) -> None:
    item_lines = [
        f"- {item.item_id}: {item.data['title']} (`{item.item_path}`)" for item in queue_items
    ]
    content = f"""# Maintenance Record Report

## Story

{story}

## Summary

Recorded {len(queue_items)} maintenance finding(s) from `{findings_path}` into the pending
maintenance queue.

## Queue items

{chr(10).join(item_lines)}

## Notes

- The command validated the findings YAML before writing queue items.
- The command did not promote items to stories.
- The command did not implement fixes.
- The command did not call cloud models or internet search.
"""

    write_text(report_path, content)


def format_hint(relative_path: str) -> str:
    suffix = Path(relative_path).suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".md":
        return "markdown"
    return "text"


def fenced(language: str, content: str) -> str:
    return f"```{language}\n{content.rstrip()}\n```"


def format_log_files(log_files: list[tuple[str, Path, str]]) -> str:
    if not log_files:
        return "No optional log files were provided."

    sections: list[str] = []
    for relative_path, source_path, content in log_files:
        sections.extend(
            [
                f"### {relative_path}",
                "",
                f"Source: `{source_path}`",
                "",
                fenced(format_hint(relative_path), content),
                "",
            ],
        )

    return "\n".join(sections).rstrip()


def format_missing_optional_evidence(missing_files: list[str]) -> str:
    if not missing_files:
        return "No optional evidence files are missing."

    return "\n".join(f"- `{relative_path}` was not found." for relative_path in missing_files)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
