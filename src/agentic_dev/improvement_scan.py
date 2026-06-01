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


IMPROVEMENT_SCAN_PACKET_FILENAME = "improvement_scan_packet.md"
IMPROVEMENT_SUGGESTIONS_TEMPLATE_FILENAME = "improvement_suggestions_template.yaml"
IMPROVEMENT_RECORD_REPORT_FILENAME = "improvement_record_report.md"
IMPROVEMENT_QUEUE_TYPE = "improvement"

REQUIRED_SUGGESTION_FIELDS = (
    "title",
    "category",
    "priority",
    "details",
    "expected_benefit",
    "suggested_acceptance_criteria",
)

EVIDENCE_FILES = [
    ("story.md", "Story content"),
    ("status.yaml", "Story status"),
    ("reports/developer_report.md", "Developer report"),
    ("reports/test_report.md", "Test report"),
    ("reports/local_review_report.md", "Local review report"),
    ("reports/test_layer_result.yaml", "Test layer result"),
    ("reports/finalize_story_result.yaml", "Finalize story result"),
    ("review_bundle/handoff.md", "Review bundle handoff"),
]


@dataclass(frozen=True)
class ImprovementScanCreateResult:
    story: str
    story_path: Path
    improvements_path: Path
    packet_path: Path
    template_path: Path
    generated_files: list[Path]
    missing_optional_files: list[str]


@dataclass(frozen=True)
class RecordedImprovementItem:
    item_id: str
    item_path: Path
    data: dict[str, Any]


@dataclass(frozen=True)
class ImprovementScanRecordResult:
    story: str
    story_path: Path
    suggestions_file: Path
    report_path: Path
    queue_items: list[RecordedImprovementItem]


@dataclass(frozen=True)
class ImprovementScanEvidence:
    present_files: list[tuple[str, str, str]]
    missing_files: list[str]


def create_improvement_scan_packet(
    project_path: Path,
    story: str,
    force: bool = False,
) -> ImprovementScanCreateResult:
    """Create a post-story improvement scan packet without calling external services."""
    project_path = project_path.resolve()
    story_path = validate_story_path(project_path, story)
    improvements_path = story_path / "improvements"
    packet_path = improvements_path / IMPROVEMENT_SCAN_PACKET_FILENAME
    template_path = improvements_path / IMPROVEMENT_SUGGESTIONS_TEMPLATE_FILENAME

    existing_files = [path for path in (packet_path, template_path) if path.exists()]
    if existing_files and not force:
        existing_list = ", ".join(str(path) for path in existing_files)
        raise ValueError(
            "Improvement scan files already exist: "
            f"{existing_list}. Use --force to overwrite.",
        )

    evidence = read_improvement_scan_evidence(story_path)
    packet = build_improvement_scan_packet(story, evidence)
    template = build_suggestions_template()

    write_text(packet_path, packet)
    write_text(template_path, template)

    return ImprovementScanCreateResult(
        story=story,
        story_path=story_path,
        improvements_path=improvements_path,
        packet_path=packet_path,
        template_path=template_path,
        generated_files=[packet_path, template_path],
        missing_optional_files=evidence.missing_files,
    )


def record_improvement_suggestions(
    project_path: Path,
    story: str,
    suggestions_file: Path,
) -> ImprovementScanRecordResult:
    """Record validated post-story suggestions into the pending improvement queue."""
    project_path = project_path.resolve()
    story_path = validate_story_path(project_path, story)
    suggestions_path = suggestions_file.resolve()

    if not suggestions_path.exists():
        raise FileNotFoundError(f"Improvement suggestions file does not exist: {suggestions_path}")

    if not suggestions_path.is_file():
        raise ValueError(f"Improvement suggestions path is not a file: {suggestions_path}")

    suggestions = load_and_validate_suggestions(suggestions_path)
    queue_items = write_improvement_queue_items(project_path, story, suggestions)

    report_path = story_path / "improvements" / IMPROVEMENT_RECORD_REPORT_FILENAME
    write_improvement_record_report(
        report_path=report_path,
        story=story,
        suggestions_path=suggestions_path,
        queue_items=queue_items,
    )

    return ImprovementScanRecordResult(
        story=story,
        story_path=story_path,
        suggestions_file=suggestions_path,
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


def read_improvement_scan_evidence(story_path: Path) -> ImprovementScanEvidence:
    present_files: list[tuple[str, str, str]] = []
    missing_files: list[str] = []

    for relative_path, label in EVIDENCE_FILES:
        path = story_path / relative_path
        if path.exists() and path.is_file():
            present_files.append((relative_path, label, read_text(path)))
        else:
            missing_files.append(relative_path)

    return ImprovementScanEvidence(present_files=present_files, missing_files=missing_files)


def build_improvement_scan_packet(story: str, evidence: ImprovementScanEvidence) -> str:
    sections = [
        "# Improvement Scan Packet",
        "",
        "This packet is for a post-story improvement scan. Use only the context in this file.",
        "Do not call cloud models automatically. Do not call internet search.",
        "",
        "## Reviewer instructions",
        "",
        "- suggest improvements only within this story's scope.",
        "- do not propose unrelated features.",
        "- do not expand the completed story.",
        "- create suggestions for future review only.",
        "- use the suggestions template format.",
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
            "## Missing optional evidence",
            "",
            format_missing_optional_evidence(evidence.missing_files),
            "",
        ],
    )

    return "\n".join(sections).rstrip() + "\n"


def build_suggestions_template() -> str:
    return """suggestions:
  - title: Add clearer validation errors
    category: maintainability
    priority: medium
    details: Explain the proposed improvement.
    expected_benefit: Explain why this helps.
    suggested_acceptance_criteria:
      - Add tests for clearer validation errors.
      - Update docs with examples.
"""


def load_and_validate_suggestions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file_handle:
        loaded = yaml.safe_load(file_handle)

    if not isinstance(loaded, dict):
        raise ValueError(f"Improvement suggestions YAML must contain a mapping: {path}")

    suggestions = loaded.get("suggestions")
    if not isinstance(suggestions, list):
        raise ValueError("Improvement suggestions YAML must include a top-level suggestions list.")

    if not suggestions:
        raise ValueError("Improvement suggestions list must contain at least one suggestion.")

    return [
        validate_suggestion(index=index, suggestion=suggestion)
        for index, suggestion in enumerate(suggestions, start=1)
    ]


def validate_suggestion(index: int, suggestion: Any) -> dict[str, Any]:
    if not isinstance(suggestion, dict):
        raise ValueError(f"Suggestion {index} must be a YAML mapping.")

    missing_fields = [
        field
        for field in REQUIRED_SUGGESTION_FIELDS
        if field not in suggestion or suggestion[field] in (None, "")
    ]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise ValueError(f"Suggestion {index} is missing required fields: {joined}.")

    criteria = suggestion["suggested_acceptance_criteria"]
    if not isinstance(criteria, list) or not criteria:
        raise ValueError(
            "Suggestion "
            f"{index} field suggested_acceptance_criteria must be a non-empty list.",
        )

    return {
        "title": text_field(index, suggestion, "title"),
        "category": text_field(index, suggestion, "category"),
        "priority": text_field(index, suggestion, "priority"),
        "details": text_field(index, suggestion, "details"),
        "expected_benefit": text_field(index, suggestion, "expected_benefit"),
        "suggested_acceptance_criteria": [
            text_criteria(index, criterion_number, criterion)
            for criterion_number, criterion in enumerate(criteria, start=1)
        ],
    }


def text_field(index: int, suggestion: dict[str, Any], field: str) -> str:
    value = str(suggestion[field]).strip()
    if not value:
        raise ValueError(f"Suggestion {index} field {field} must not be blank.")

    return value


def text_criteria(index: int, criterion_number: int, criterion: Any) -> str:
    value = str(criterion).strip()
    if not value:
        raise ValueError(
            "Suggestion "
            f"{index} acceptance criterion {criterion_number} must not be blank.",
        )

    return value


def write_improvement_queue_items(
    project_path: Path,
    story: str,
    suggestions: list[dict[str, Any]],
) -> list[RecordedImprovementItem]:
    queue_items: list[RecordedImprovementItem] = []

    for suggestion in suggestions:
        directories = ensure_queue_directories(project_path, IMPROVEMENT_QUEUE_TYPE)
        item_id = generate_item_id(IMPROVEMENT_QUEUE_TYPE, directories)
        item_path = directories["pending"] / item_filename(item_id)
        item = build_queue_item(item_id, story, suggestion)
        write_yaml_mapping(item_path, item, allow_overwrite=False)
        queue_items.append(RecordedImprovementItem(item_id=item_id, item_path=item_path, data=item))

    return queue_items


def build_queue_item(
    item_id: str,
    story: str,
    suggestion: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": item_id,
        "queue_type": IMPROVEMENT_QUEUE_TYPE,
        "title": suggestion["title"],
        "source_story": story,
        "category": suggestion["category"],
        "priority": suggestion["priority"],
        "status": "pending",
        "details": suggestion["details"],
        "expected_benefit": suggestion["expected_benefit"],
        "suggested_acceptance_criteria": suggestion["suggested_acceptance_criteria"],
        "created_at": timestamp_now(),
        "next_action": NEXT_ACTION_BY_STATUS["pending"],
    }


def write_improvement_record_report(
    report_path: Path,
    story: str,
    suggestions_path: Path,
    queue_items: list[RecordedImprovementItem],
) -> None:
    item_lines = [
        f"- {item.item_id}: {item.data['title']} (`{item.item_path}`)" for item in queue_items
    ]
    content = f"""# Improvement Record Report

## Story

{story}

## Summary

Recorded {len(queue_items)} improvement suggestion(s) from `{suggestions_path}` into the pending
improvement queue.

## Queue items

{chr(10).join(item_lines)}

## Notes

- The command validated the suggestions YAML before writing queue items.
- The command did not promote items to stories.
- The command did not implement suggestions.
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


def format_missing_optional_evidence(missing_files: list[str]) -> str:
    if not missing_files:
        return "No optional evidence files are missing."

    return "\n".join(f"- `{relative_path}` was not found." for relative_path in missing_files)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
