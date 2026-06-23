from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.review_state.service import validate_review_bundle


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
    ("review_bundle/manifest.yaml", "Review bundle manifest"),
    ("review_bundle/validation/checksums.yaml", "Review bundle checksums"),
    ("reports/quality_gate_result.yaml", "Quality gate result"),
    ("reports/post_merge_quality_gate_result.yaml", "Post-merge quality gate result"),
    ("reports/finalize_story_result.yaml", "Finalize story result"),
    ("reports/finalize_story_report.md", "Finalize story report"),
    ("reports/post_merge_quality_gate_report.md", "Post-merge quality gate report"),
    ("review_bundle/handoff.md", "Review bundle handoff"),
    ("review_bundle/git_status.txt", "Git status summary"),
    ("review_bundle/git_diff_stat.txt", "Git diff stat"),
    ("review_bundle/git_diff.patch", "Git diff patch"),
    ("review_bundle/git_diff_staged.patch", "Git staged diff"),
    ("review_bundle/committed_diff_metadata.txt", "Committed PR diff metadata"),
    ("review_bundle/committed_diff_stat.txt", "Committed PR diff stat"),
    ("review_bundle/committed_changed_files.txt", "Committed PR changed files"),
    ("review_bundle/committed_diff.patch", "Committed PR diff patch"),
    ("review_bundle/untracked_files.txt", "Untracked file list"),
    ("review_bundle/untracked_file_contents.md", "Untracked file contents"),
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

    import yaml
    review_bundle_path = story_path / "review_bundle"
    manifest_path = review_bundle_path / "manifest.yaml"
    status_path = story_path / "status.yaml"
    quality_gate_path = story_path / "reports" / "quality_gate_result.yaml"

    if not manifest_path.exists():
        raise ValueError("Missing mandatory evidence: review_bundle/manifest.yaml")

    validation = validate_review_bundle(project_path, story)
    if not validation.valid:
        raise ValueError("Review bundle validation failed: " + "; ".join(validation.reasons))

    reasons = []

    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        wt_class = manifest.get("working_tree", {}).get("classification")
        if wt_class not in ("clean", "normalization-only", "file-mode-only"):
            reasons.append("working tree is dirty or ambiguous")
        if not manifest.get("validation", {}).get("strict_clean_passed"):
            reasons.append("strict_clean_passed is false")
        
        host_matched = manifest.get("host", {}).get("matched")
        host_status = manifest.get("host", {}).get("status")
        host_validation = manifest.get("validation", {}).get("host_container_git_match")
        if host_status != "passed" or not host_matched or not host_validation:
            reasons.append("required host parity is not checked or failed")
    except Exception as e:
        reasons.append(f"Invalid manifest.yaml: {e}")

    try:
        if not status_path.exists():
            reasons.append("Missing mandatory evidence: status.yaml")
        else:
            status_doc = yaml.safe_load(status_path.read_text(encoding="utf-8"))
            if not status_doc.get("ready_for_review"):
                reasons.append("story ready_for_review is false")
    except Exception as e:
        reasons.append(f"Invalid status.yaml: {e}")

    try:
        if not quality_gate_path.exists():
            reasons.append("Missing mandatory evidence: reports/quality_gate_result.yaml")
        else:
            qg_doc = yaml.safe_load(quality_gate_path.read_text(encoding="utf-8"))
            if qg_doc.get("status") != "PASS":
                reasons.append("quality gate status is not passing")
    except Exception as e:
        reasons.append(f"Invalid quality_gate_result.yaml: {e}")

    if reasons:
        raise ValueError("Cloud packet readiness validation failed: " + "; ".join(reasons))

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
