from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.project_status import (
    build_summary_counts,
    collect_story_status,
    find_story_paths,
    format_terminal_summary,
)
from agentic_dev.queue_management import (
    NEXT_ACTION_BY_STATUS,
    QUEUE_STATUSES,
    ensure_queue_directories,
    generate_item_id,
    item_filename,
    list_queue_items,
    timestamp_now,
    write_yaml_mapping,
)


FEATURE_SCAN_PACKET_FILENAME = "feature_scan_packet.md"
FEATURE_SUGGESTIONS_TEMPLATE_FILENAME = "feature_suggestions_template.yaml"
FEATURE_RECORD_REPORT_FILENAME = "feature_record_report.md"
FEATURE_QUEUE_TYPE = "feature"
PROJECT_FEATURE_SCAN_SOURCE = "project_feature_scan"

REQUIRED_FEATURE_FIELDS = (
    "title",
    "category",
    "priority",
    "details",
    "expected_benefit",
    "strategic_fit",
    "evidence",
    "suggested_acceptance_criteria",
)

TEXT_DOCUMENT_SUFFIXES = {".md", ".txt", ".yaml", ".yml"}
README_EXCERPT_LIMIT = 6000
DOC_EXCERPT_LIMIT = 6000
BLUEPRINT_EXCERPT_LIMIT = 20000


@dataclass(frozen=True)
class FeatureScanCreateResult:
    project_path: Path
    feature_scan_path: Path
    packet_path: Path
    template_path: Path
    generated_files: list[Path]
    missing_optional_files: list[str]


@dataclass(frozen=True)
class RecordedFeatureItem:
    item_id: str
    item_path: Path
    data: dict[str, Any]


@dataclass(frozen=True)
class FeatureScanRecordResult:
    project_path: Path
    suggestions_file: Path
    report_path: Path
    queue_items: list[RecordedFeatureItem]


@dataclass(frozen=True)
class FeatureScanEvidence:
    project_name: str | None
    blueprint_summary: str
    blueprint_content: str | None
    project_status_summary: str
    story_list: str
    queue_count_summary: str
    feature_queue_items: str
    readme_summary: str
    docs_list: str
    docs_content: str
    missing_optional_files: list[str]


def create_feature_scan_packet(
    project_path: Path,
    force: bool = False,
    focus: str | None = None,
) -> FeatureScanCreateResult:
    """Create a project feature discovery packet without external calls."""
    project_path = project_path.resolve()
    feature_scan_path = project_path / ".agentic" / "feature_scan"
    packet_path = feature_scan_path / FEATURE_SCAN_PACKET_FILENAME
    template_path = feature_scan_path / FEATURE_SUGGESTIONS_TEMPLATE_FILENAME

    existing_files = [path for path in (packet_path, template_path) if path.exists()]
    if existing_files and not force:
        existing_list = ", ".join(str(path) for path in existing_files)
        raise ValueError(
            "Feature scan files already exist: "
            f"{existing_list}. Use --force to overwrite.",
        )

    evidence = collect_feature_scan_evidence(project_path)
    packet = build_feature_scan_packet(evidence, focus)
    template = build_feature_suggestions_template()

    write_text(packet_path, packet)
    write_text(template_path, template)

    return FeatureScanCreateResult(
        project_path=project_path,
        feature_scan_path=feature_scan_path,
        packet_path=packet_path,
        template_path=template_path,
        generated_files=[packet_path, template_path],
        missing_optional_files=evidence.missing_optional_files,
    )


def record_feature_suggestions(
    project_path: Path,
    suggestions_file: Path,
) -> FeatureScanRecordResult:
    """Record validated project feature suggestions into the pending feature queue."""
    project_path = project_path.resolve()
    suggestions_path = suggestions_file.resolve()

    if not suggestions_path.exists():
        raise FileNotFoundError(f"Feature suggestions file does not exist: {suggestions_path}")

    if not suggestions_path.is_file():
        raise ValueError(f"Feature suggestions path is not a file: {suggestions_path}")

    suggestions = load_and_validate_feature_suggestions(suggestions_path)
    queue_items = write_feature_queue_items(project_path, suggestions)

    report_path = project_path / ".agentic" / "feature_scan" / FEATURE_RECORD_REPORT_FILENAME
    write_feature_record_report(
        report_path=report_path,
        suggestions_path=suggestions_path,
        queue_items=queue_items,
    )

    return FeatureScanRecordResult(
        project_path=project_path,
        suggestions_file=suggestions_path,
        report_path=report_path,
        queue_items=queue_items,
    )


def collect_feature_scan_evidence(project_path: Path) -> FeatureScanEvidence:
    missing_optional_files: list[str] = []
    project_name = read_project_name(project_path, missing_optional_files)
    blueprint_summary, blueprint_content = read_blueprint_context(project_path, missing_optional_files)
    project_status_summary, story_list, queue_count_summary = build_project_status_context(
        project_path,
        missing_optional_files,
    )
    feature_queue_items = format_existing_feature_queue_items(project_path)
    readme_summary = read_readme_summary(project_path, missing_optional_files)
    docs_list, docs_content = read_docs_context(project_path, missing_optional_files)

    return FeatureScanEvidence(
        project_name=project_name,
        blueprint_summary=blueprint_summary,
        blueprint_content=blueprint_content,
        project_status_summary=project_status_summary,
        story_list=story_list,
        queue_count_summary=queue_count_summary,
        feature_queue_items=feature_queue_items,
        readme_summary=readme_summary,
        docs_list=docs_list,
        docs_content=docs_content,
        missing_optional_files=missing_optional_files,
    )


def read_project_name(project_path: Path, missing_optional_files: list[str]) -> str | None:
    project_yaml_path = project_path / ".agentic" / "project.yaml"
    if not project_yaml_path.exists():
        missing_optional_files.append(".agentic/project.yaml")
        return None

    data = load_optional_yaml_mapping(project_yaml_path)
    project_data = data.get("project")
    if isinstance(project_data, dict):
        name = text_or_none(project_data.get("name"))
        if name:
            return name

    return text_or_none(data.get("name"))


def read_blueprint_context(
    project_path: Path,
    missing_optional_files: list[str],
) -> tuple[str, str | None]:
    blueprint_path = project_path / "blueprints" / "blueprint.yaml"
    if not blueprint_path.exists():
        missing_optional_files.append("blueprints/blueprint.yaml")
        return "No blueprint file was found.", None

    content = read_text(blueprint_path)
    data = load_optional_yaml_mapping(blueprint_path)
    project_data = data.get("project") if isinstance(data.get("project"), dict) else {}
    stories = data.get("stories") if isinstance(data.get("stories"), list) else []
    project_name = text_or_none(project_data.get("name")) if isinstance(project_data, dict) else None
    project_type = text_or_none(project_data.get("type")) if isinstance(project_data, dict) else None
    description = (
        text_or_none(project_data.get("description")) if isinstance(project_data, dict) else None
    )

    lines = [
        f"- Project name: {project_name or 'not specified'}",
        f"- Project type: {project_type or 'not specified'}",
        f"- Description: {description or 'not specified'}",
        f"- Blueprint story count: {len(stories)}",
    ]
    latest_stories = [
        story for story in stories[-10:] if isinstance(story, dict)
    ]
    if latest_stories:
        lines.append("- Latest blueprint stories:")
        for story in latest_stories:
            story_id = text_or_none(story.get("id")) or "missing-id"
            slug = text_or_none(story.get("slug")) or "missing-slug"
            title = text_or_none(story.get("title")) or "untitled"
            lines.append(f"  - {story_id} / {slug}: {title}")

    return "\n".join(lines), content


def build_project_status_context(
    project_path: Path,
    missing_optional_files: list[str],
) -> tuple[str, str, str]:
    stories_path = project_path / "stories"
    if not stories_path.exists() or not stories_path.is_dir():
        missing_optional_files.append("stories/")
        return (
            "No stories folder was found.",
            "No story workspaces were found.",
            format_queue_counts(project_path),
        )

    story_paths = find_story_paths(stories_path, None)
    story_statuses = [collect_story_status(project_path, story_path) for story_path in story_paths]
    summary_counts = build_summary_counts(story_statuses)
    queue_counts_text = format_queue_counts(project_path)
    terminal_summary = format_terminal_summary(
        project_path,
        story_statuses,
        summary_counts,
        build_queue_count_mapping(project_path),
    )

    story_lines = []
    for story in story_statuses:
        story_lines.append(
            "- "
            f"{story.story}: category={story.category}, "
            f"status={story.status or 'missing'}, "
            f"ready_for_review={format_optional_bool(story.ready_for_review)}, "
            f"next={story.next_action}"
        )

    return terminal_summary, "\n".join(story_lines) or "No story workspaces were found.", queue_counts_text


def build_queue_count_mapping(project_path: Path) -> dict[str, dict[str, int]]:
    from agentic_dev.queue_management import count_queue_items

    return count_queue_items(project_path)


def format_queue_counts(project_path: Path) -> str:
    queue_counts = build_queue_count_mapping(project_path)
    lines = []
    for queue_type, counts in queue_counts.items():
        status_counts = ", ".join(f"{status}={counts[status]}" for status in QUEUE_STATUSES)
        lines.append(f"- {queue_type}: total={counts['total']} ({status_counts})")
    return "\n".join(lines)


def format_existing_feature_queue_items(project_path: Path) -> str:
    result = list_queue_items(project_path, queue_type=FEATURE_QUEUE_TYPE, status="all")
    feature_items = result.items_by_type_and_status.get(FEATURE_QUEUE_TYPE, {})
    lines: list[str] = []
    for status in QUEUE_STATUSES:
        items = feature_items.get(status, [])
        if not items:
            continue
        lines.append(f"### {status}")
        for item in items:
            lines.append(
                "- "
                f"{item.item_id} | priority={item.priority} | "
                f"category={item.category} | title={item.title}"
            )
        lines.append("")

    return "\n".join(lines).rstrip() or "No existing feature queue items were found."


def read_readme_summary(project_path: Path, missing_optional_files: list[str]) -> str:
    readme_path = project_path / "README.md"
    if not readme_path.exists():
        missing_optional_files.append("README.md")
        return "No README.md file was found."

    content = read_text(readme_path)
    headings = [line.strip() for line in content.splitlines() if line.startswith("#")]
    sections = [
        "Headings:",
        format_list(headings) if headings else "- No Markdown headings found.",
        "",
        "Excerpt:",
        excerpt(content, README_EXCERPT_LIMIT),
    ]
    return "\n".join(sections).rstrip()


def read_docs_context(project_path: Path, missing_optional_files: list[str]) -> tuple[str, str]:
    docs_path = project_path / "docs"
    if not docs_path.exists() or not docs_path.is_dir():
        missing_optional_files.append("docs/")
        return "No docs folder was found.", "No docs content was included."

    doc_files = sorted(
        path
        for path in docs_path.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    )
    if not doc_files:
        return "No docs files were found.", "No docs content was included."

    docs_list = "\n".join(f"- {path.relative_to(project_path)}" for path in doc_files)
    content_sections: list[str] = []
    for path in doc_files:
        if path.suffix.lower() not in TEXT_DOCUMENT_SUFFIXES:
            continue
        relative_path = path.relative_to(project_path)
        content_sections.extend(
            [
                f"### {relative_path}",
                "",
                fenced(format_hint(str(relative_path)), excerpt(read_text(path), DOC_EXCERPT_LIMIT)),
                "",
            ],
        )

    docs_content = "\n".join(content_sections).rstrip() or "No text docs content was included."
    return docs_list, docs_content


def build_feature_scan_packet(evidence: FeatureScanEvidence, focus: str | None) -> str:
    focus_text = focus.strip() if focus else ""
    sections = [
        "# Project Feature Discovery Scan Packet",
        "",
        "This packet is for project-level feature discovery. It is a planning aid only.",
        "Do not call cloud models automatically. Do not call internet search automatically.",
        "",
        "## Reviewer instructions",
        "",
        "- suggest project-level new features that could improve this project.",
        "- do not suggest tiny story-level improvements here.",
        "- do not suggest maintenance repairs here.",
        "- do not implement features.",
        "- do not create stories.",
        "- place suggestions into the feature suggestion template.",
        (
            "- if internet research is available, use it to identify new tools, patterns, "
            "ecosystem changes, and comparable project ideas."
        ),
        (
            "- clearly separate Project-derived observations from "
            "External/internet-derived observations."
        ),
        "- do not invent sources.",
        "- do not claim internet research was performed if it was not performed.",
        "- if no internet research was performed, say so explicitly.",
        "- include source_urls only for sources actually used.",
        "",
        "## Suggested response structure",
        "",
        "1. Project-derived observations.",
        "2. External/internet-derived observations, or a statement that none were performed.",
        "3. Completed YAML using `feature_suggestions_template.yaml`.",
        "",
        "## Project",
        "",
        f"- Name: {evidence.project_name or 'not specified'}",
    ]

    if focus_text:
        sections.extend(["", "## Focus area", "", focus_text])

    sections.extend(
        [
            "",
            "## Blueprint summary",
            "",
            evidence.blueprint_summary,
            "",
            "## Project status summary",
            "",
            fenced("text", evidence.project_status_summary),
            "",
            "## Story list",
            "",
            evidence.story_list,
            "",
            "## Queue count summary",
            "",
            evidence.queue_count_summary,
            "",
            "## Existing feature queue items",
            "",
            evidence.feature_queue_items,
            "",
            "## README summary",
            "",
            evidence.readme_summary,
            "",
            "## Relevant docs list",
            "",
            evidence.docs_list,
            "",
            "## Relevant docs content",
            "",
            evidence.docs_content,
            "",
        ],
    )

    if evidence.blueprint_content is not None:
        sections.extend(
            [
                "## Project blueprint",
                "",
                "Source: `blueprints/blueprint.yaml`",
                "",
                fenced("yaml", excerpt(evidence.blueprint_content, BLUEPRINT_EXCERPT_LIMIT)),
                "",
            ],
        )

    sections.extend(
        [
            "## Missing optional context",
            "",
            format_missing_optional_evidence(evidence.missing_optional_files),
            "",
        ],
    )

    return "\n".join(sections).rstrip() + "\n"


def build_feature_suggestions_template() -> str:
    return """suggestions:
  - title: Add visual project dashboard
    category: usability
    priority: medium
    details: Explain the proposed feature.
    expected_benefit: Explain how this improves the project.
    strategic_fit: Explain why this fits the project roadmap.
    evidence:
      - Project-derived observation or external research evidence.
    source_urls:
      - Optional URL if internet research was actually used.
    suggested_acceptance_criteria:
      - Add a project dashboard command or page.
      - Show story statuses and queue counts.
"""


def load_and_validate_feature_suggestions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file_handle:
        loaded = yaml.safe_load(file_handle)

    if not isinstance(loaded, dict):
        raise ValueError(f"Feature suggestions YAML must contain a mapping: {path}")

    suggestions = loaded.get("suggestions")
    if not isinstance(suggestions, list):
        raise ValueError("Feature suggestions YAML must include a top-level suggestions list.")

    if not suggestions:
        raise ValueError("Feature suggestions list must contain at least one suggestion.")

    return [
        validate_feature_suggestion(index=index, suggestion=suggestion)
        for index, suggestion in enumerate(suggestions, start=1)
    ]


def validate_feature_suggestion(index: int, suggestion: Any) -> dict[str, Any]:
    if not isinstance(suggestion, dict):
        raise ValueError(f"Suggestion {index} must be a YAML mapping.")

    missing_fields = [
        field
        for field in REQUIRED_FEATURE_FIELDS
        if field not in suggestion or suggestion[field] in (None, "")
    ]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise ValueError(f"Suggestion {index} is missing required fields: {joined}.")

    evidence = required_text_list(index, suggestion, "evidence")
    criteria = required_text_list(index, suggestion, "suggested_acceptance_criteria")
    source_urls = optional_text_list(index, suggestion, "source_urls")

    return {
        "title": text_field(index, suggestion, "title"),
        "category": text_field(index, suggestion, "category"),
        "priority": text_field(index, suggestion, "priority"),
        "details": text_field(index, suggestion, "details"),
        "expected_benefit": text_field(index, suggestion, "expected_benefit"),
        "strategic_fit": text_field(index, suggestion, "strategic_fit"),
        "evidence": evidence,
        "source_urls": source_urls,
        "suggested_acceptance_criteria": criteria,
    }


def required_text_list(index: int, suggestion: dict[str, Any], field: str) -> list[str]:
    items = suggestion[field]
    if not isinstance(items, list) or not items:
        raise ValueError(f"Suggestion {index} field {field} must be a non-empty list.")

    return [
        text_list_item(index, field, item_number, item)
        for item_number, item in enumerate(items, start=1)
    ]


def optional_text_list(index: int, suggestion: dict[str, Any], field: str) -> list[str]:
    if field not in suggestion or suggestion[field] is None:
        return []

    items = suggestion[field]
    if not isinstance(items, list):
        raise ValueError(f"Suggestion {index} field {field} must be a list when present.")

    return [
        text_list_item(index, field, item_number, item)
        for item_number, item in enumerate(items, start=1)
    ]


def text_field(index: int, suggestion: dict[str, Any], field: str) -> str:
    value = str(suggestion[field]).strip()
    if not value:
        raise ValueError(f"Suggestion {index} field {field} must not be blank.")

    return value


def text_list_item(index: int, field: str, item_number: int, item: Any) -> str:
    value = str(item).strip()
    if not value:
        raise ValueError(f"Suggestion {index} {field} item {item_number} must not be blank.")

    return value


def write_feature_queue_items(
    project_path: Path,
    suggestions: list[dict[str, Any]],
) -> list[RecordedFeatureItem]:
    queue_items: list[RecordedFeatureItem] = []

    for suggestion in suggestions:
        directories = ensure_queue_directories(project_path, FEATURE_QUEUE_TYPE)
        item_id = generate_item_id(FEATURE_QUEUE_TYPE, directories)
        item_path = directories["pending"] / item_filename(item_id)
        item = build_feature_queue_item(item_id, suggestion)
        write_yaml_mapping(item_path, item, allow_overwrite=False)
        queue_items.append(RecordedFeatureItem(item_id=item_id, item_path=item_path, data=item))

    return queue_items


def build_feature_queue_item(item_id: str, suggestion: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item_id,
        "queue_type": FEATURE_QUEUE_TYPE,
        "title": suggestion["title"],
        "source_story": PROJECT_FEATURE_SCAN_SOURCE,
        "category": suggestion["category"],
        "priority": suggestion["priority"],
        "status": "pending",
        "details": suggestion["details"],
        "expected_benefit": suggestion["expected_benefit"],
        "strategic_fit": suggestion["strategic_fit"],
        "evidence": suggestion["evidence"],
        "source_urls": suggestion["source_urls"],
        "suggested_acceptance_criteria": suggestion["suggested_acceptance_criteria"],
        "created_at": timestamp_now(),
        "next_action": NEXT_ACTION_BY_STATUS["pending"],
    }


def write_feature_record_report(
    report_path: Path,
    suggestions_path: Path,
    queue_items: list[RecordedFeatureItem],
) -> None:
    item_lines = [
        f"- {item.item_id}: {item.data['title']} (`{item.item_path}`)" for item in queue_items
    ]
    content = f"""# Feature Record Report

## Summary

Recorded {len(queue_items)} feature suggestion(s) from `{suggestions_path}` into the pending
feature queue.

## Queue items

{chr(10).join(item_lines)}

## Notes

- The command validated the suggestions YAML before writing queue items.
- The command did not promote items to stories.
- The command did not implement suggestions.
- The command did not call cloud models or internet search.
"""

    write_text(report_path, content)


def load_optional_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as yaml_file:
            loaded = yaml.safe_load(yaml_file)
    except yaml.YAMLError:
        return {}

    if isinstance(loaded, dict):
        return loaded

    return {}


def text_or_none(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def format_optional_bool(value: bool | None) -> str:
    if value is None:
        return "missing"
    return "yes" if value else "no"


def format_hint(relative_path: str) -> str:
    suffix = Path(relative_path).suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".md":
        return "markdown"
    return "text"


def fenced(language: str, content: str) -> str:
    return f"```{language}\n{content.rstrip()}\n```"


def format_list(items: list[str]) -> str:
    if not items:
        return "- None"

    return "\n".join(f"- {item}" for item in items)


def format_missing_optional_evidence(missing_files: list[str]) -> str:
    if not missing_files:
        return "No optional context files are missing."

    return "\n".join(f"- `{relative_path}` was not found." for relative_path in missing_files)


def excerpt(content: str, character_limit: int) -> str:
    normalized = content.rstrip()
    if len(normalized) <= character_limit:
        return normalized

    return normalized[:character_limit].rstrip() + "\n\n[content truncated]"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
