from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.review_state.service import validate_review_bundle
from agentic_dev.local_evidence_validation import validate_local_evidence, LocalEvidenceValidationResult


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
    
    local_ev = validate_local_evidence(project_path, story)
    if local_ev.execution_record_present:
        if not local_ev.execution_record_valid:
            reasons.append("Local execution record is present but invalid: " + "; ".join(local_ev.failure_reasons))
        elif not local_ev.ready_for_review:
            # Must never present story as ready if pending review
            reasons.append("Local execution record is valid, but structured local review decision is pending")
    
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        wt_class = manifest.get("working_tree", {}).get("classification")
        if wt_class not in ("clean", "normalization-only", "file-mode-only", "normalization_noise_only"):
            reasons.append("working tree is dirty or ambiguous")
        if not manifest.get("validation", {}).get("strict_clean_passed"):
            reasons.append("strict_clean_passed is false")
        
        host_matched = manifest.get("host", {}).get("matched")
        host_status = manifest.get("host", {}).get("status")
        host_validation = manifest.get("validation", {}).get("host_container_git_match")
        if host_status != "passed" or not host_matched or not host_validation:
            reasons.append("required host parity is not checked or failed")
            
        # Cleanliness validation for normalization
        wt = manifest.get("working_tree", {})
        wt_staged = wt.get("staged", [])
        wt_unstaged = wt.get("unstaged", [])
        wt_untracked = wt.get("untracked", [])
        normalization_paths = manifest.get("normalization", [])
        
        if wt_class == "normalization_noise_only":
            if manifest.get("validation", {}).get("normalization_matched") is False:
                reasons.append("normalized repository and working-tree content do not match")
            
            # semantic unstaged paths must be zero
            if len(wt_unstaged) > len(normalization_paths):
                reasons.append("there are semantic unstaged changes")
            
            if len(wt_staged) > 0:
                reasons.append("there are staged semantic changes")
                
            if len(wt_untracked) > 0:
                reasons.append("there are untracked implementation files")
                
    except Exception as e:
        reasons.append(f"Invalid manifest.yaml: {e}")

    # Validate story content
    story_content = read_text(story_file)
    if story_content.lstrip().startswith("# UNKNOWN"):
        reasons.append("story title starts with UNKNOWN")
        
    import re
    sections = re.split(r'^##\s+', story_content, flags=re.MULTILINE)
    for section in sections[1:]:
        lines = [line.strip() for line in section.split('\n')[1:] if line.strip()]
        if len(lines) == 1 and lines[0].lstrip('-* ').upper() == 'TODO':
            reasons.append(f"required section '{section.splitlines()[0].strip()}' contains only TODO")
            
    # Load blueprint
    blueprint_path = project_path / "blueprints" / "blueprint.yaml"
    blueprint_snippet = "Blueprint unavailable"
    if not blueprint_path.exists():
        reasons.append("no authoritative requirements source can be resolved")
    else:
        try:
            bp_data = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
            matches = [s for s in bp_data.get("stories", []) if s.get("slug") == story]
            if not matches:
                reasons.append("blueprint identity is missing")
            elif len(matches) > 1:
                reasons.append("multiple matching stories exist in blueprint")
            else:
                story_node = matches[0]
                bp_id = story_node.get("id") or story_node.get("story_id")
                if not bp_id or bp_id not in story_content:
                    reasons.append("generated workspace story does not match blueprint identity")
                blueprint_snippet = yaml.safe_dump(story_node, sort_keys=False)
        except Exception as e:
            reasons.append(f"Invalid blueprint.yaml: {e}")


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
            if qg_doc.get("status") != "READY_FOR_REVIEW":
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

    evidence = read_optional_evidence(story_path)

    prompt = build_prompt()
    context = build_context(story, story_content, evidence, local_ev, story_path, blueprint_snippet, manifest)
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


def build_context(story: str, story_content: str, evidence: Evidence, local_ev: LocalEvidenceValidationResult, story_path: Path, blueprint_snippet: str, manifest: dict) -> str:
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
    

    wt = manifest.get("working_tree", {})
    wt_class = wt.get("classification", "unknown")
    wt_staged = wt.get("staged", []) or []
    wt_unstaged = wt.get("unstaged", []) or []
    wt_untracked = wt.get("untracked", []) or []
    normalization_paths = manifest.get("normalization", []) or []
    
    porcelain_clean = len(wt_staged) == 0 and len(wt_unstaged) == 0 and len(wt_untracked) == 0
    norm_only = len(normalization_paths)
    semantic_unstaged = len(wt_unstaged) - norm_only if wt_class == "normalization_noise_only" else len(wt_unstaged)
    
    import yaml
    cleanliness_block = {
        "working_tree_cleanliness": {
            "git_porcelain_clean": porcelain_clean,
            "policy_cleanliness": wt_class,
            "strict_clean_passed": manifest.get("validation", {}).get("strict_clean_passed", False),
            "normalization_only_paths": norm_only,
            "semantic_unstaged_paths": max(0, semantic_unstaged),
            "staged_paths": len(wt_staged),
            "untracked_semantic_paths": len(wt_untracked),
            "committed_pr_changed_file_count": manifest.get("committed_diff", {}).get("changed_file_count", 0),
        }
    }
    
    sections.extend([
        "## Cleanliness Summary",
        "",
        fenced("yaml", yaml.safe_dump(cleanliness_block, sort_keys=False)),
        "",
    ])
    
    sections.extend([
        "## Blueprint requirements",
        "",
        fenced("yaml", blueprint_snippet),
        "",
    ])
    
    if local_ev.execution_record_present and local_ev.execution_record_valid:
        import yaml
        record_path = story_path / "reports" / "local_execution_record.yaml"
        decision_path = story_path / "reports" / "local_review_decision.yaml"
        
        record_data = yaml.safe_load(record_path.read_text(encoding="utf-8")) if record_path.exists() else {}
        decision_data = yaml.safe_load(decision_path.read_text(encoding="utf-8")) if decision_path.exists() else {}
        
        local_execution_block = {
            "local_execution": {
                "present": True,
                "valid": True,
                "execution_mode": local_ev.provenance.get("execution_mode"),
                "executor": local_ev.provenance.get("executor"),
                "roles_covered": local_ev.roles_covered,
                "role_evidence": record_data.get("execution", {}).get("role_evidence", {}),
                "record_checksum": local_ev.record_checksum,
                "manifest_checksum": record_data.get("review_evidence", {}).get("manifest_checksum"),
                "review_decision": {
                    "decision": decision_data.get("decision"),
                    "attestation_checksum": decision_data.get("attestation_checksum"),
                    "file_checksum": local_ev.review_decision_checksum,
                    "reviewer": decision_data.get("reviewer"),
                },
                "readiness_source": "structured_local_review"
            }
        }
        
        sections.extend([
            "## Local Execution Provenance",
            "",
            fenced("yaml", yaml.safe_dump(local_execution_block, sort_keys=False)),
            "",
        ])

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
