from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.prompt_pack import load_agent_plan, ordered_assigned_agents, text_value


DEFAULT_ROLE_CONTEXT_TARGET_CHARACTERS = 8000
ROLE_CONTEXT_STATUSES = {
    "CONTEXT_READY",
    "CONTEXT_READY_WITH_WARNINGS",
    "CONTEXT_FAILED",
}

EXCLUDED_STORY_CONTEXT_FOLDERS = {
    "cloud_review_packet",
    "local_agent_context",
    "local_agent_drafts",
    "remote_dev_validation",
}


@dataclass(frozen=True)
class RoleContextPacket:
    agent_id: str
    path: Path
    status: str
    character_count: int
    included_files: list[str]
    skipped_files: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class RoleContextResult:
    project_path: Path
    story: str
    agents_built: list[str]
    target_characters: int
    status: str
    context_packets: list[RoleContextPacket]
    warnings: list[str]
    failed_checks: list[str]
    result_path: Path
    report_path: Path
    role_context_path: Path

    @property
    def terminal_summary(self) -> str:
        lines = [
            f"Role context built for: {self.story}",
            f"Status: {self.status}",
            f"Agents built: {', '.join(self.agents_built) if self.agents_built else 'none'}",
            f"Result: {self.result_path}",
            f"Report: {self.report_path}",
            f"Packet folder: {self.role_context_path}",
        ]

        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"  - {warning}" for warning in self.warnings)

        return "\n".join(lines)


def build_role_context(
    project_path: Path,
    story: str,
    *,
    agent: str | None = None,
    all_agents: bool = False,
    force: bool = False,
    target_chars: int = DEFAULT_ROLE_CONTEXT_TARGET_CHARACTERS,
) -> RoleContextResult:
    """Build deterministic role-specific context packets for assigned story agents."""
    resolved_project_path = project_path.resolve()
    story_path = resolved_project_path / "stories" / story

    if not story_path.exists() or not story_path.is_dir():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if target_chars <= 0:
        raise ValueError("--target-chars must be greater than zero.")

    if agent and all_agents:
        raise ValueError("Use either --agent or --all, not both.")

    agent_plan_path = story_path / "agent_plan.yaml"
    if not agent_plan_path.exists():
        raise FileNotFoundError(f"Required agent plan does not exist: {agent_plan_path}")

    agent_plan = load_agent_plan(agent_plan_path)
    assigned_agents = ordered_assigned_agents(agent_plan)
    selected_agents = select_agents(assigned_agents, agent)

    role_context_path = story_path / "reports" / "role_context"
    role_context_path.mkdir(parents=True, exist_ok=True)
    (role_context_path / ".gitkeep").touch()

    packets: list[RoleContextPacket] = []
    result_warnings: list[str] = []
    failed_checks: list[str] = []

    for assigned_agent in selected_agents:
        packet = build_agent_context_packet(
            resolved_project_path,
            story_path,
            story,
            assigned_agent,
            agent_plan_path,
            role_context_path,
            force=force,
            target_chars=target_chars,
        )
        packets.append(packet)
        result_warnings.extend(packet.warnings)

    agents_built = [packet.agent_id for packet in packets if packet.status == "written"]

    if failed_checks:
        status = "CONTEXT_FAILED"
    elif result_warnings:
        status = "CONTEXT_READY_WITH_WARNINGS"
    else:
        status = "CONTEXT_READY"

    result_path = story_path / "reports" / "role_context_result.yaml"
    report_path = story_path / "reports" / "role_context_report.md"
    result = RoleContextResult(
        project_path=resolved_project_path,
        story=story,
        agents_built=agents_built,
        target_characters=target_chars,
        status=status,
        context_packets=packets,
        warnings=dedupe_preserve_order(result_warnings),
        failed_checks=failed_checks,
        result_path=result_path,
        report_path=report_path,
        role_context_path=role_context_path,
    )

    result_path.write_text(format_role_context_result_yaml(result), encoding="utf-8")
    report_path.write_text(format_role_context_report(result), encoding="utf-8")

    return result


def select_agents(assigned_agents: list[dict[str, Any]], agent: str | None) -> list[dict[str, Any]]:
    if agent is None:
        return assigned_agents

    for assigned_agent in assigned_agents:
        if text_value(assigned_agent, "id", "") == agent:
            return [assigned_agent]

    available_agents = ", ".join(text_value(assigned_agent, "id", "") for assigned_agent in assigned_agents)
    raise ValueError(f"Agent is not assigned to this story: {agent}. Available agents: {available_agents}")


def build_agent_context_packet(
    project_path: Path,
    story_path: Path,
    story: str,
    agent: dict[str, Any],
    agent_plan_path: Path,
    role_context_path: Path,
    *,
    force: bool,
    target_chars: int,
) -> RoleContextPacket:
    agent_id = text_value(agent, "id", "unknown_agent")
    packet_path = role_context_path / f"{agent_id}_context.md"
    skipped_files: list[str] = []
    warnings: list[str] = []

    if packet_path.exists() and not force:
        warning = f"Context packet already exists and was not overwritten: {packet_path}"
        return RoleContextPacket(
            agent_id=agent_id,
            path=packet_path,
            status="skipped_existing",
            character_count=len(packet_path.read_text(encoding="utf-8")),
            included_files=[],
            skipped_files=[relative_to_project(project_path, packet_path)],
            warnings=[warning],
        )

    sources = collect_context_sources(project_path, story_path, story, agent, agent_plan_path)
    skipped_files.extend(sources.skipped_files)
    warnings.extend(sources.warnings)

    content = format_context_packet(
        story=story,
        agent=agent,
        sources=sources,
        target_chars=target_chars,
    )

    character_count = len(content)
    if character_count > target_chars:
        warnings.append(
            f"{agent_id} context is {character_count} characters, above target {target_chars}.",
        )

    packet_path.write_text(content, encoding="utf-8")

    return RoleContextPacket(
        agent_id=agent_id,
        path=packet_path,
        status="written",
        character_count=character_count,
        included_files=sources.included_files,
        skipped_files=dedupe_preserve_order(skipped_files),
        warnings=dedupe_preserve_order(warnings),
    )


@dataclass(frozen=True)
class ContextSources:
    shared_sections: list[tuple[str, str]]
    role_sections: list[tuple[str, str]]
    included_files: list[str]
    skipped_files: list[str]
    warnings: list[str]


def collect_context_sources(
    project_path: Path,
    story_path: Path,
    story: str,
    agent: dict[str, Any],
    agent_plan_path: Path,
) -> ContextSources:
    agent_id = text_value(agent, "id", "unknown_agent")
    included_files: list[str] = []
    skipped_files: list[str] = []
    warnings: list[str] = []

    def include_file(
        title: str,
        path: Path,
        *,
        required: bool = False,
        max_chars: int | None = None,
        warn_on_truncate: bool = False,
    ) -> tuple[str, str] | None:
        if not path.exists():
            relative_path = relative_to_project(project_path, path)
            skipped_files.append(relative_path)
            if required:
                warnings.append(f"Required context file is missing: {relative_path}")
            return None

        content = path.read_text(encoding="utf-8")
        relative_path = relative_to_project(project_path, path)
        included_files.append(relative_path)
        if max_chars is not None and len(content) > max_chars:
            content = f"{content[:max_chars].rstrip()}\n\n[Truncated to {max_chars} characters.]"
            if warn_on_truncate:
                warnings.append(f"Truncated {relative_path} to {max_chars} characters.")

        return title, fenced_block(path, content)

    instruction_path = story_path / text_value(agent, "instruction_file", f"instructions/{agent_id}.md")
    shared_sections = [
        section
        for section in [
            include_file("Story File", story_path / "story.md", required=True, max_chars=600),
            include_file("Status", story_path / "status.yaml"),
            include_file("Agent Plan", agent_plan_path, required=True, max_chars=1000),
            include_file("Agent Instruction", instruction_path, required=True),
            include_file("Safety Rules", project_path / ".agentic" / "rules.yaml", max_chars=700),
            include_file(
                "Runtime Guidance",
                project_path / ".agentic" / "agent_runtime.yaml",
                max_chars=800,
            ),
        ]
        if section is not None
    ]

    story_text = (story_path / "story.md").read_text(encoding="utf-8")
    story_sections = parse_markdown_sections(story_text)
    role_sections = role_specific_sections(
        project_path,
        story_path,
        story,
        agent,
        story_sections,
        include_file,
    )

    skipped_files.extend(excluded_story_paths(project_path, story_path, agent_id))

    return ContextSources(
        shared_sections=shared_sections,
        role_sections=role_sections,
        included_files=dedupe_preserve_order(included_files),
        skipped_files=dedupe_preserve_order(skipped_files),
        warnings=dedupe_preserve_order(warnings),
    )


def role_specific_sections(
    project_path: Path,
    story_path: Path,
    story: str,
    agent: dict[str, Any],
    story_sections: dict[str, str],
    include_file: Any,
) -> list[tuple[str, str]]:
    agent_id = text_value(agent, "id", "unknown_agent")
    sections: list[tuple[str, str]] = [
        ("Role Responsibility", text_value(agent, "responsibility", "Use the story context for this role.")),
        ("Expected Output", text_value(agent, "expected_output", "Write the expected story report.")),
    ]

    if agent_id == "developer_agent":
        sections.extend(
            [
                ("Story Goal", section_text(story_sections, "Goal")),
                (
                    "Acceptance Criteria",
                    limit_text(section_text(story_sections, "Acceptance Criteria"), 700),
                ),
                ("Not In Scope", limit_text(section_text(story_sections, "Not In Scope"), 500)),
                (
                    "Definition Of Done",
                    limit_text(section_text(story_sections, "Definition of Done"), 500),
                ),
                ("Role Boundary", "Do not write tests. Implement only the approved story scope."),
            ],
        )
        sections.extend(
            optional_sections(
                include_file,
                [
                    ("Implementation Notes", story_path / "reports" / "planner_report.md"),
                    ("Research Notes", story_path / "reports" / "research_report.md"),
                    ("Story Runbook", story_path / "story_runbook.md"),
                ],
                max_chars=350,
            ),
        )
        return sections

    if agent_id == "test_agent":
        sections.extend(
            [
                ("Story Goal", section_text(story_sections, "Goal")),
                (
                    "Acceptance Criteria",
                    limit_text(section_text(story_sections, "Acceptance Criteria"), 700),
                ),
                (
                    "Role Boundary",
                    "Write independent tests; do not rewrite implementation except tiny "
                    "test-enabling fixes.",
                ),
            ],
        )
        sections.extend(
            optional_sections(
                include_file,
                [
                    ("Test Plan And Layer Expectations", story_path / "test_plan.yaml"),
                    (
                        "Developer Report And Changed Behavior Summary",
                        story_path / "reports" / "developer_report.md",
                    ),
                ],
                max_chars=500,
            ),
        )
        return sections

    if agent_id == "docs_agent":
        sections.extend(
            [
                ("Story Goal", section_text(story_sections, "Goal")),
                (
                    "Docs Acceptance Criteria",
                    matching_lines(
                        section_text(story_sections, "Acceptance Criteria"),
                        ["doc", "README"],
                    ),
                ),
                ("Docs References", docs_reference_list(project_path)),
                ("Role Boundary", "Update docs only and do not change implementation."),
            ],
        )
        return sections

    if agent_id == "local_reviewer_agent":
        sections.extend(
            [
                ("Story Goal", section_text(story_sections, "Goal")),
                (
                    "Acceptance Criteria",
                    limit_text(section_text(story_sections, "Acceptance Criteria"), 700),
                ),
                (
                    "Role Boundary",
                    "Do not mark READY_FOR_REVIEW unless checks pass.",
                ),
                ("Safety Checklist", safety_checklist()),
            ],
        )
        sections.extend(
            optional_sections(
                include_file,
                [
                    ("Developer Report", story_path / "reports" / "developer_report.md"),
                    ("Test Report", story_path / "reports" / "test_report.md"),
                    ("Test Layer Result", story_path / "reports" / "test_layer_result.yaml"),
                    ("Quality Gate Result", story_path / "reports" / "quality_gate_result.yaml"),
                    ("Finalize Result", story_path / "reports" / "finalize_story_result.yaml"),
                    ("Review Bundle Handoff", story_path / "review_bundle" / "handoff.md"),
                ],
                max_chars=150,
            ),
        )
        return sections

    if agent_id == "security_quality_agent":
        sections.extend(
            [
                ("Story Goal", section_text(story_sections, "Goal")),
                (
                    "Acceptance Criteria",
                    limit_text(section_text(story_sections, "Acceptance Criteria"), 700),
                ),
                (
                    "Review Focus",
                    "Focus on secrets, unsafe file access, merge/deploy risks, and generated artifacts.",
                ),
                (
                    "Artifact Policy Notes",
                    "Generated review_bundle, cloud_review_packet, remote_dev_validation, "
                    "local_agent_context, local_agent_drafts, raw model responses, and "
                    "role_context packet files must remain untracked except .gitkeep.",
                ),
            ],
        )
        sections.extend(
            optional_sections(
                include_file,
                [
                    ("Quality Gate Result", story_path / "reports" / "quality_gate_result.yaml"),
                    ("Finalize Result", story_path / "reports" / "finalize_story_result.yaml"),
                    ("Gitignore", project_path / ".gitignore"),
                ],
                max_chars=200,
            ),
        )
        return sections

    if agent_id == "research_agent":
        sections.extend(
            [
                ("Story Goal", section_text(story_sections, "Goal")),
                ("Why", section_text(story_sections, "Why This Matters")),
                ("Risks", limit_text(section_text(story_sections, "Not In Scope"), 700)),
                ("Relevant Docs", docs_reference_list(project_path)),
                (
                    "Role Boundary",
                    "Suggest scoped findings only; do not expand story scope.",
                ),
            ],
        )
        return sections

    if agent_id == "planner_agent":
        sections.extend(
            [
                ("Story Goal", section_text(story_sections, "Goal")),
                (
                    "Acceptance Criteria",
                    limit_text(section_text(story_sections, "Acceptance Criteria"), 1000),
                ),
                ("Dependencies", infer_dependencies(story_sections)),
                (
                    "Current Story Status",
                    read_optional_plain_text(story_path / "status.yaml", "No status.yaml found."),
                ),
                (
                    "Planning Focus",
                    f"Create the implementation plan and sequencing for `{story}`.",
                ),
            ],
        )
        return sections

    sections.append(("Role Boundary", "Follow only the responsibilities assigned to this agent."))
    return sections


def optional_sections(
    include_file: Any,
    file_specs: list[tuple[str, Path]],
    *,
    max_chars: int,
) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for title, path in file_specs:
        section = include_file(title, path, max_chars=max_chars)
        if section is not None:
            sections.append(section)
    return sections


def format_context_packet(
    *,
    story: str,
    agent: dict[str, Any],
    sources: ContextSources,
    target_chars: int,
) -> str:
    agent_id = text_value(agent, "id", "unknown_agent")
    display_name = text_value(agent, "display_name", agent_id.replace("_", " ").title())

    lines = [
        f"# {display_name} Context",
        "",
        "## Agent Identity",
        "",
        f"- Agent ID: `{agent_id}`",
        f"- Display name: {display_name}",
        "",
        "## Story",
        "",
        f"`{story}`",
        "",
        "## Role Responsibility",
        "",
        text_value(agent, "responsibility", "Use this packet for the assigned story role."),
        "",
        "## Shared Premise",
        "",
        "This packet is deterministic local context. It does not execute prompts, call local "
        "models, call cloud models, call GitHub APIs, commit, merge, or deploy.",
        f"Target packet size: {target_chars} characters.",
        "",
    ]

    lines.extend(format_named_sections(sources.shared_sections))
    lines.extend(["## Role-Specific Context", ""])
    lines.extend(format_named_sections(sources.role_sections))
    lines.extend(
        [
            "## Included Files",
            "",
            format_bullets(sources.included_files),
            "",
            "## Skipped Files",
            "",
            format_bullets(sources.skipped_files),
            "",
            "## Warnings",
            "",
            format_bullets(sources.warnings),
            "",
            "## Expected Output",
            "",
            text_value(agent, "expected_output", "Write the expected story report."),
            "",
            "## Safety Boundaries",
            "",
            "- Do not call cloud models.",
            "- Do not call local models.",
            "- Do not execute agent prompts.",
            "- Do not commit, merge, deploy, or call GitHub APIs from this context builder.",
            "- Do not track generated role_context packet files except `.gitkeep`.",
            "",
            "## Suggested Next Command Or Handoff Note",
            "",
            f"Give this packet to `{agent_id}` with its prompt pack. The next local handoff "
            "is the agent's expected report path, not model or prompt execution.",
            "",
        ],
    )

    return "\n".join(lines)


def format_named_sections(sections: list[tuple[str, str]]) -> list[str]:
    lines: list[str] = []
    for title, content in sections:
        lines.extend([f"### {title}", "", content.rstrip() or "Not provided.", ""])
    return lines


def format_role_context_result_yaml(result: RoleContextResult) -> str:
    data = {
        "story": result.story,
        "agents_built": result.agents_built,
        "target_characters": result.target_characters,
        "status": result.status,
        "context_packets": [
            {
                "agent": packet.agent_id,
                "path": relative_to_project(result.project_path, packet.path),
                "status": packet.status,
                "estimated_character_count": packet.character_count,
                "included_files": packet.included_files,
                "skipped_files": packet.skipped_files,
                "warnings": packet.warnings,
            }
            for packet in result.context_packets
        ],
        "warnings": result.warnings,
        "failed_checks": result.failed_checks,
        "safety_flags": {
            "called_cloud_models": False,
            "called_local_models": False,
            "executed_agents": False,
            "committed_or_merged": False,
            "deployed": False,
        },
    }

    return yaml.safe_dump(data, sort_keys=False)


def format_role_context_report(result: RoleContextResult) -> str:
    lines = [
        "# Role Context Report",
        "",
        f"- Story: `{result.story}`",
        f"- Status: {result.status}",
        f"- Target characters: {result.target_characters}",
        f"- Agents built: {', '.join(result.agents_built) if result.agents_built else 'none'}",
        "",
        "## Context Packets",
        "",
    ]

    for packet in result.context_packets:
        lines.extend(
            [
                f"### {packet.agent_id}",
                "",
                f"- Status: {packet.status}",
                f"- Path: `{relative_to_project(result.project_path, packet.path)}`",
                f"- Estimated characters: {packet.character_count}",
                f"- Included files: {len(packet.included_files)}",
                f"- Skipped files: {len(packet.skipped_files)}",
                "",
            ],
        )

    lines.extend(
        [
            "## Warnings",
            "",
            format_bullets(result.warnings),
            "",
            "## Safety Flags",
            "",
            "- called_cloud_models: false",
            "- called_local_models: false",
            "- executed_agents: false",
            "- committed_or_merged: false",
            "- deployed: false",
            "",
        ],
    )

    return "\n".join(lines)


def parse_markdown_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_heading = "Preamble"
    sections[current_heading] = []

    for line in markdown.splitlines():
        if line.startswith("## "):
            current_heading = line.removeprefix("## ").strip()
            sections.setdefault(current_heading, [])
            continue
        sections.setdefault(current_heading, []).append(line)

    return {heading: "\n".join(lines).strip() for heading, lines in sections.items()}


def section_text(sections: dict[str, str], heading: str) -> str:
    return sections.get(heading, "Not provided.")


def matching_lines(text: str, needles: list[str]) -> str:
    matches = [
        line
        for line in text.splitlines()
        if any(needle.lower() in line.lower() for needle in needles)
    ]
    if not matches:
        return "No docs-specific acceptance criteria found. Use the story goal and docs references."
    return "\n".join(matches)


def limit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}\n\n[Truncated to {max_chars} characters.]"


def docs_reference_list(project_path: Path) -> str:
    references = ["README.md"]
    docs_path = project_path / "docs"
    if docs_path.exists():
        references.extend(
            f"docs/{path.name}"
            for path in sorted(docs_path.glob("*.md"))
            if path.name in {"command_map.md", "code_tour.md", "role_context_builder.md"}
        )
    return format_bullets(references)


def infer_dependencies(story_sections: dict[str, str]) -> str:
    acceptance = section_text(story_sections, "Acceptance Criteria")
    dependencies = [
        line
        for line in acceptance.splitlines()
        if any(token in line.lower() for token in ["update", "add", "read", "write"])
    ]
    return "\n".join(dependencies) if dependencies else "No explicit dependencies found."


def safety_checklist() -> str:
    return "\n".join(
        [
            "- pytest passed or failures are explained.",
            "- Ruff passed or failures are explained.",
            "- artifact-policy passed.",
            "- public-readiness passed.",
            "- runtime-config validate passed.",
            "- Generated runtime artifacts are not tracked.",
            "- No cloud or local model calls were made by the context builder.",
        ],
    )


def read_optional_plain_text(path: Path, fallback: str) -> str:
    if not path.exists():
        return fallback
    return path.read_text(encoding="utf-8").rstrip()


def fenced_block(path: Path, content: str) -> str:
    suffix = path.suffix.lower()
    language = "yaml" if suffix in {".yaml", ".yml"} else "markdown"
    return f"```{language}\n{content.rstrip()}\n```"


def format_bullets(items: list[str]) -> str:
    if not items:
        return "- None."
    return "\n".join(f"- {item}" for item in items)


def excluded_story_paths(project_path: Path, story_path: Path, agent_id: str) -> list[str]:
    skipped: list[str] = []
    for folder_name in EXCLUDED_STORY_CONTEXT_FOLDERS:
        folder = story_path / folder_name if folder_name in {"cloud_review_packet", "remote_dev_validation"} else story_path / "reports" / folder_name
        if folder.exists():
            skipped.append(f"{relative_to_project(project_path, folder)}/*")

    if agent_id == "developer_agent" and (story_path / "review_bundle").exists():
        skipped.append(f"{relative_to_project(project_path, story_path / 'review_bundle')}/*")

    return skipped


def relative_to_project(project_path: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_path.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped
