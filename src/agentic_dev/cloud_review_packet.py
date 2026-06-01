from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PACKET_FILENAMES = [
    "cloud_review_prompt.md",
    "cloud_review_context.md",
    "cloud_review_checklist.md",
    "cloud_review_result_template.md",
    "cloud_review_export.md",
]

OPTIONAL_EVIDENCE_FILES = [
    ("status.yaml", "Story status"),
    ("agent_plan.yaml", "Agent plan"),
    ("test_plan.yaml", "Test plan"),
    ("monitoring_plan.yaml", "Monitoring plan"),
    ("reports/quality_gate_result.yaml", "Quality gate result"),
    ("reports/finalize_story_result.yaml", "Finalize story result"),
    ("reports/finalize_story_report.md", "Finalize story report"),
    ("review_bundle/handoff.md", "Review bundle handoff"),
    ("review_bundle/git_status.txt", "Git status summary"),
    ("review_bundle/git_diff_stat.txt", "Git diff stat"),
    ("review_bundle/untracked_files.txt", "Untracked file list"),
]


@dataclass(frozen=True)
class CloudReviewPacketResult:
    story: str
    story_path: Path
    packet_path: Path
    generated_files: list[Path]
    missing_optional_files: list[str]


def create_cloud_review_packet(project_path: Path, story: str, force: bool = False) -> CloudReviewPacketResult:
    """Create a cloud-model-ready review packet without calling external services."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    story_file = story_path / "story.md"
    if not story_file.exists():
        raise FileNotFoundError(f"Required story file does not exist: {story_file}")

    packet_path = story_path / "cloud_review_packet"
    packet_path.mkdir(parents=True, exist_ok=True)

    packet_files = [packet_path / filename for filename in PACKET_FILENAMES]
    existing_files = [path for path in packet_files if path.exists()]
    if existing_files and not force:
        existing_list = ", ".join(str(path) for path in existing_files)
        raise ValueError(f"Cloud review packet files already exist: {existing_list}. Use --force to overwrite.")

    story_content = read_text(story_file)
    evidence = read_optional_evidence(story_path)

    prompt = build_prompt()
    context = build_context(story, story_content, evidence)
    checklist = build_checklist()
    result_template = build_result_template()

    files_to_content = {
        packet_path / "cloud_review_prompt.md": prompt,
        packet_path / "cloud_review_context.md": context,
        packet_path / "cloud_review_checklist.md": checklist,
        packet_path / "cloud_review_result_template.md": result_template,
        packet_path / "cloud_review_export.md": build_export(
            prompt,
            context,
            checklist,
            result_template,
        ),
    }

    generated_files: list[Path] = []
    for path, content in files_to_content.items():
        write_text(path, content)
        if path.name != "cloud_review_export.md":
            generated_files.append(path)

    gitkeep_path = packet_path / ".gitkeep"
    if not gitkeep_path.exists():
        write_text(gitkeep_path, "")

    return CloudReviewPacketResult(
        story=story,
        story_path=story_path,
        packet_path=packet_path,
        generated_files=generated_files,
        missing_optional_files=evidence.missing_files,
    )


@dataclass(frozen=True)
class Evidence:
    present_files: list[tuple[str, str, str]]
    missing_files: list[str]


def read_optional_evidence(story_path: Path) -> Evidence:
    present_files: list[tuple[str, str, str]] = []
    missing_files: list[str] = []

    for relative_path, label in OPTIONAL_EVIDENCE_FILES:
        path = story_path / relative_path
        if path.exists() and path.is_file():
            present_files.append((relative_path, label, read_text(path)))
        else:
            missing_files.append(relative_path)

    return Evidence(present_files=present_files, missing_files=missing_files)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def build_prompt() -> str:
    return """# Cloud Review Prompt

You are reviewing a completed story for merge readiness. Use only the facts in this packet.
Do not invent missing facts, test outcomes, implementation details, approvals, or risks.
If information needed for a confident review is missing, request it explicitly.

Review the packet for:

- Architecture and design fit
- Correctness and behavior
- Test coverage and test evidence
- Maintainability
- Security and secret risks
- Scope control
- Acceptance criteria coverage
- Documentation quality
- Merge readiness

Return exactly one decision:

- APPROVE
- APPROVE_WITH_NOTES
- REQUEST_CHANGES

Include a concise rationale, required changes, optional notes, risks, and questions for the
human reviewer. Do not call external tools or cloud APIs from this packet.
"""


def build_context(story: str, story_content: str, evidence: Evidence) -> str:
    sections = [
        "# Cloud Review Context",
        "",
        "## Story name",
        "",
        story,
        "",
        "## Story content",
        "",
        fenced("markdown", story_content),
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


def build_checklist() -> str:
    return """# Cloud Review Checklist

- [ ] Requirements coverage
- [ ] Tests
- [ ] Lint/Ruff
- [ ] Architecture
- [ ] Security
- [ ] Maintainability
- [ ] Scope control
- [ ] Documentation
- [ ] Merge readiness
"""


def build_result_template() -> str:
    return """# Cloud Review Result

## Decision

APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES

## Summary

-

## Required changes

-

## Optional notes

-

## Risks

-

## Questions for human reviewer

-
"""


def build_export(prompt: str, context: str, checklist: str, result_template: str) -> str:
    return f"""# Cloud Review Export

This is the single file to paste or upload to the main cloud model for review.
Do not call cloud models automatically from the local workflow.

---

{prompt.rstrip()}

---

{context.rstrip()}

---

{checklist.rstrip()}

---

{result_template.rstrip()}
"""
