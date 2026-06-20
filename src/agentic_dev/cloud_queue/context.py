from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.cloud_queue.redaction import RedactionSummary, redact_path_fragment, redact_text
from agentic_dev.cloud_queue.validation import normalize_relative_path


@dataclass(frozen=True)
class CloudQueueContext:
    story: str
    title: str
    details: str
    requirements: list[str]
    writable_paths: list[str]
    dependencies: list[str]
    blockers: list[str]
    context_files: list[str]
    evidence_sections: list[tuple[str, str]]
    redaction_summary: RedactionSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "story": self.story,
            "title": self.title,
            "details": self.details,
            "requirements": list(self.requirements),
            "writable_paths": list(self.writable_paths),
            "dependencies": list(self.dependencies),
            "blockers": list(self.blockers),
            "context_files": list(self.context_files),
            "evidence_sections": [{"label": label, "content": content} for label, content in self.evidence_sections],
            "redaction_summary": self.redaction_summary.to_dict(),
        }


def build_context(
    project_path: Path,
    story: str,
    title: str,
    details: str,
    requirements: list[str] | None = None,
    writable_paths: list[str] | None = None,
    dependencies: list[str] | None = None,
    blockers: list[str] | None = None,
    context_files: list[str] | None = None,
) -> CloudQueueContext:
    story_path = project_path.resolve() / "stories" / story
    evidence_sections: list[tuple[str, str]] = []
    filenames: list[str] = []
    redaction_summary = RedactionSummary(filename_count=0, content_count=0, pattern_counts={})

    for relative in context_files or []:
        normalized = normalize_relative_path(relative)
        path = (story_path / normalized).resolve()
        if not path.exists() or not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        redacted_content, summary = redact_text(content)
        redaction_summary = RedactionSummary(
            filename_count=redaction_summary.filename_count,
            content_count=redaction_summary.content_count + summary.content_count,
            pattern_counts=merge_counts(redaction_summary.pattern_counts, summary.pattern_counts),
        )
        filenames.append(redact_path_fragment(normalized))
        evidence_sections.append((normalized, redacted_content))

    return CloudQueueContext(
        story=story,
        title=title,
        details=details,
        requirements=list(requirements or []),
        writable_paths=list(writable_paths or []),
        dependencies=list(dependencies or []),
        blockers=list(blockers or []),
        context_files=filenames,
        evidence_sections=evidence_sections,
        redaction_summary=redaction_summary,
    )


def format_context_markdown(context: CloudQueueContext) -> str:
    sections = [
        "# Cloud Queue Request Context",
        "",
        f"- Story: `{context.story}`",
        f"- Title: {context.title}",
        "",
        "## Details",
        "",
        context.details or "No details provided.",
        "",
        "## Requirements",
        "",
        format_bullets(context.requirements),
        "",
        "## Writable Paths",
        "",
        format_bullets(context.writable_paths),
        "",
        "## Dependencies",
        "",
        format_bullets(context.dependencies),
        "",
        "## Blockers",
        "",
        format_bullets(context.blockers),
        "",
    ]

    if context.evidence_sections:
        sections.extend(["## Evidence", ""])
        for label, content in context.evidence_sections:
            sections.extend([f"### `{label}`", "", "```text", content.rstrip(), "```", ""])

    sections.extend(
        [
            "## Redaction Summary",
            "",
            yaml.safe_dump(context.redaction_summary.to_dict(), sort_keys=False).rstrip(),
            "",
        ],
    )

    return "\n".join(sections).rstrip() + "\n"


def merge_counts(first: dict[str, int], second: dict[str, int]) -> dict[str, int]:
    merged = dict(first)
    for key, value in second.items():
        merged[key] = merged.get(key, 0) + value
    return merged


def format_bullets(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)
