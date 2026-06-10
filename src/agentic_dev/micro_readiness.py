from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


READY_FOR_MICRO = "READY_FOR_MICRO"
MICRO_READY_WITH_WARNINGS = "MICRO_READY_WITH_WARNINGS"
TOO_LARGE_FOR_MICRO = "TOO_LARGE_FOR_MICRO"
NEEDS_REVIEW = "NEEDS_REVIEW"

DEFAULT_TARGET_CHARACTERS = 2000

CORE_AGENT_IDS = [
    "research_agent",
    "planner_agent",
    "developer_agent",
    "test_agent",
    "docs_agent",
    "security_quality_agent",
    "local_reviewer_agent",
]

DEFAULT_AGENT_EXPECTED_OUTPUTS = {
    "research_agent": "reports/research_report.md",
    "planner_agent": "reports/planner_report.md",
    "developer_agent": "reports/developer_report.md",
    "test_agent": "reports/test_report.md",
    "docs_agent": "reports/docs_report.md",
    "security_quality_agent": "reports/security_quality_report.md",
    "local_reviewer_agent": "reports/local_review_report.md",
}

VAGUE_GOAL_TERMS = {
    "etc",
    "stuff",
    "things",
    "various",
    "many",
    "everything",
    "all the",
    "improve",
    "enhance",
    "optimize",
    "cleanup",
    "clean up",
}

SPLIT_SIGNAL_TERMS = {
    "and/or",
    "multiple",
    "several",
    "many",
    "unrelated",
    "across the system",
    "entire system",
    "all commands",
    "all docs",
    "all modules",
}

MODULE_SIGNAL_TERMS = {
    "src/",
    "tests/",
    "docs/",
    "README",
    "blueprints/",
    "stories/",
    ".agentic/",
    "CLI",
    "runtime",
    "workflow",
    "review bundle",
    "cloud review",
    "local model",
    "queue",
    "artifact policy",
    "public readiness",
}


@dataclass(frozen=True)
class AgentMicroEstimate:
    agent_id: str
    responsibility: str
    expected_output: str
    estimated_characters: int
    target_characters: int
    fits_target: bool
    source_files: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class MicroReadinessResult:
    story: str
    status: str
    target_characters: int
    passed_checks: list[str]
    warnings: list[str]
    failed_checks: list[str]
    agent_estimates: list[AgentMicroEstimate]
    recommended_action: str
    result_path: Path
    report_path: Path
    terminal_summary: str


def run_micro_readiness(
    project_path: Path,
    story: str,
    target_characters: int = DEFAULT_TARGET_CHARACTERS,
) -> MicroReadinessResult:
    project_path = project_path.resolve()
    if target_characters <= 0:
        raise ValueError("--target-chars must be greater than 0.")

    story_path = project_path / "stories" / story
    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")
    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    passed_checks: list[str] = []
    warnings: list[str] = []
    failed_checks: list[str] = []

    story_file = story_path / "story.md"
    if not story_file.exists():
        failed_checks.append("story.md is missing, so story scope cannot be evaluated.")
        result = build_result(
            story=story,
            target_characters=target_characters,
            passed_checks=passed_checks,
            warnings=warnings,
            failed_checks=failed_checks,
            agent_estimates=[],
            reports_path=reports_path,
        )
        write_micro_readiness_result(result.result_path, result)
        write_micro_readiness_report(result.report_path, result)
        return result

    story_text = story_file.read_text(encoding="utf-8")
    story_sections = parse_story_sections(story_text)
    goal = first_nonempty_line(story_sections.get("Goal", ""))
    acceptance_criteria = markdown_bullets(story_sections.get("Acceptance Criteria", ""))
    not_in_scope = markdown_bullets(story_sections.get("Not In Scope", ""))
    definition_of_done = markdown_bullets(story_sections.get("Definition of Done", ""))

    add_story_shape_checks(
        goal=goal,
        acceptance_criteria=acceptance_criteria,
        not_in_scope=not_in_scope,
        definition_of_done=definition_of_done,
        full_story_text=story_text,
        passed_checks=passed_checks,
        warnings=warnings,
        failed_checks=failed_checks,
    )

    agent_plan_path = story_path / "agent_plan.yaml"
    assigned_agents, agent_plan_warnings, agent_plan_failed = load_assigned_agents(agent_plan_path)
    warnings.extend(agent_plan_warnings)
    failed_checks.extend(agent_plan_failed)
    if agent_plan_path.exists() and not agent_plan_failed:
        passed_checks.append("agent_plan.yaml exists and lists assigned agents.")

    instruction_roles = load_instruction_roles(story_path)
    estimates = build_agent_estimates(
        story_path=story_path,
        story=story,
        goal=goal,
        acceptance_criteria=acceptance_criteria,
        assigned_agents=assigned_agents,
        instruction_roles=instruction_roles,
        target_characters=target_characters,
    )

    oversized_agents = [estimate for estimate in estimates if not estimate.fits_target]
    if oversized_agents:
        warnings.append(
            "At least one agent micro prompt estimate exceeds the target character count."
        )
    if len(oversized_agents) >= 2:
        failed_checks.append(
            "Several assigned agents exceed the target character count; split or narrow the story."
        )
    else:
        passed_checks.append("Most assigned agent prompts fit within the target character count.")

    for estimate in estimates:
        warnings.extend(estimate.warnings)

    result = build_result(
        story=story,
        target_characters=target_characters,
        passed_checks=dedupe(passed_checks),
        warnings=dedupe(warnings),
        failed_checks=dedupe(failed_checks),
        agent_estimates=estimates,
        reports_path=reports_path,
    )
    write_micro_readiness_result(result.result_path, result)
    write_micro_readiness_report(result.report_path, result)
    return result


def add_story_shape_checks(
    goal: str,
    acceptance_criteria: list[str],
    not_in_scope: list[str],
    definition_of_done: list[str],
    full_story_text: str,
    passed_checks: list[str],
    warnings: list[str],
    failed_checks: list[str],
) -> None:
    if goal:
        passed_checks.append("Story goal is present.")
    else:
        warnings.append("Story goal is missing or empty.")

    if len(goal) > 360:
        warnings.append("Story goal is very long; make the goal sharper before using micro mode.")
    if looks_vague(goal):
        warnings.append("Story goal contains vague terms; clarify the concrete outcome.")

    if not acceptance_criteria:
        warnings.append("Acceptance criteria are missing or empty.")
    elif len(acceptance_criteria) <= 10:
        passed_checks.append("Acceptance criteria count is within the focused-story range.")
    elif len(acceptance_criteria) <= 15:
        warnings.append("More than 10 acceptance criteria may be too broad for micro prompts.")
    else:
        failed_checks.append("More than 15 acceptance criteria usually means the story is too large.")

    if not_in_scope:
        passed_checks.append("Not-in-scope boundaries are present.")
    else:
        warnings.append("Not-in-scope is missing or empty; add explicit boundaries.")

    if definition_of_done:
        passed_checks.append("Definition of Done is present.")
    else:
        warnings.append("Definition of Done is missing or empty.")

    unrelated_module_count = count_module_signals(full_story_text)
    if unrelated_module_count >= 12:
        failed_checks.append("Story appears to touch many unrelated modules or workflow areas.")
    elif unrelated_module_count >= 8:
        warnings.append("Story appears to touch several modules; confirm the scope is cohesive.")
    else:
        passed_checks.append("Story does not appear to touch many unrelated modules.")

    split_signals = matching_terms(full_story_text, SPLIT_SIGNAL_TERMS)
    if len(split_signals) >= 3:
        failed_checks.append(
            "Story contains several split signals: " + ", ".join(sorted(split_signals))
        )
    elif split_signals:
        warnings.append("Story has possible split signals: " + ", ".join(sorted(split_signals)))


def load_assigned_agents(agent_plan_path: Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    warnings: list[str] = []
    failed_checks: list[str] = []

    if not agent_plan_path.exists():
        warnings.append(
            "agent_plan.yaml is missing; using core agents with fallback responsibilities."
        )
        return [fallback_agent(agent_id) for agent_id in CORE_AGENT_IDS], warnings, failed_checks

    try:
        loaded = yaml.safe_load(agent_plan_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        failed_checks.append(f"agent_plan.yaml is not valid YAML: {error}")
        return [fallback_agent(agent_id) for agent_id in CORE_AGENT_IDS], warnings, failed_checks

    if not isinstance(loaded, dict):
        failed_checks.append("agent_plan.yaml must be a YAML mapping.")
        return [fallback_agent(agent_id) for agent_id in CORE_AGENT_IDS], warnings, failed_checks

    assigned = loaded.get("assigned_agents")
    if not isinstance(assigned, list) or not assigned:
        warnings.append(
            "agent_plan.yaml does not list assigned agents; using core agents for estimates."
        )
        return [fallback_agent(agent_id) for agent_id in CORE_AGENT_IDS], warnings, failed_checks

    agents: list[dict[str, str]] = []
    for index, entry in enumerate(assigned, start=1):
        if not isinstance(entry, dict):
            failed_checks.append(f"assigned_agents[{index}] must be a YAML mapping.")
            continue
        agent_id = text_value(entry, "id", f"agent_{index}")
        responsibility = text_value(entry, "responsibility", "")
        expected_output = text_value(
            entry,
            "expected_output",
            DEFAULT_AGENT_EXPECTED_OUTPUTS.get(agent_id, f"reports/{agent_id}_report.md"),
        )
        if not responsibility.strip():
            warnings.append(f"{agent_id} is missing a responsibility in agent_plan.yaml.")
        agents.append(
            {
                "id": agent_id,
                "responsibility": responsibility,
                "expected_output": expected_output,
            }
        )

    return agents or [fallback_agent(agent_id) for agent_id in CORE_AGENT_IDS], warnings, failed_checks


def fallback_agent(agent_id: str) -> dict[str, str]:
    return {
        "id": agent_id,
        "responsibility": "",
        "expected_output": DEFAULT_AGENT_EXPECTED_OUTPUTS.get(
            agent_id,
            f"reports/{agent_id}_report.md",
        ),
    }


def load_instruction_roles(story_path: Path) -> dict[str, tuple[str, str]]:
    instruction_dir = story_path / "instructions"
    roles: dict[str, tuple[str, str]] = {}
    if not instruction_dir.exists() or not instruction_dir.is_dir():
        return roles

    for instruction_path in sorted(instruction_dir.glob("*.md")):
        agent_id = instruction_path.stem
        text = instruction_path.read_text(encoding="utf-8")
        role = first_nonempty_line(markdown_section(text, "Role"))
        roles[agent_id] = (role, relative_path(story_path, instruction_path))
    return roles


def build_agent_estimates(
    story_path: Path,
    story: str,
    goal: str,
    acceptance_criteria: list[str],
    assigned_agents: list[dict[str, str]],
    instruction_roles: dict[str, tuple[str, str]],
    target_characters: int,
) -> list[AgentMicroEstimate]:
    estimates: list[AgentMicroEstimate] = []
    for agent in assigned_agents:
        agent_id = agent["id"]
        responsibility = agent["responsibility"].strip()
        source_files = ["story.md"]
        if (story_path / "agent_plan.yaml").exists():
            source_files.append("agent_plan.yaml")
        if not responsibility and agent_id in instruction_roles:
            responsibility = instruction_roles[agent_id][0]
            source_files.append(instruction_roles[agent_id][1])
        if not responsibility:
            responsibility = "Use the story and assigned role to produce a bounded report."

        expected_output = agent["expected_output"]
        prompt = format_micro_prompt_estimate(
            story=story,
            agent_id=agent_id,
            responsibility=responsibility,
            goal=goal or "Not specified.",
            acceptance_criteria=acceptance_criteria[:5] or ["Not specified."],
            expected_output=expected_output,
        )
        character_count = len(prompt)
        estimate_warnings: list[str] = []
        if character_count > target_characters:
            estimate_warnings.append(
                f"{agent_id} estimated micro prompt is {character_count} characters."
            )
        estimates.append(
            AgentMicroEstimate(
                agent_id=agent_id,
                responsibility=responsibility,
                expected_output=expected_output,
                estimated_characters=character_count,
                target_characters=target_characters,
                fits_target=character_count <= target_characters,
                source_files=dedupe(source_files),
                warnings=estimate_warnings,
            )
        )
    return estimates


def format_micro_prompt_estimate(
    story: str,
    agent_id: str,
    responsibility: str,
    goal: str,
    acceptance_criteria: list[str],
    expected_output: str,
) -> str:
    lines = [
        "# Local Agent Micro Prompt Estimate",
        "",
        f"story: {story}",
        f"agent: {agent_id}",
        f"agent_responsibility: {one_line(responsibility, 220)}",
        f"story_goal: {one_line(goal, 300)}",
        "",
        "top_acceptance_criteria:",
    ]
    lines.extend(f"- {one_line(item, 220)}" for item in acceptance_criteria)
    lines.extend(
        [
            "",
            f"expected_output: {expected_output}",
            "",
            "safety_rules: Save a draft/report only. Do not edit source files, execute model "
            "output, call cloud models, call GitHub APIs, commit, push, merge, or deploy.",
            "",
            "final_visible_answer: Return only the final visible answer in message.content. "
            "Do not rely on hidden reasoning_content.",
        ]
    )
    return "\n".join(lines)


def build_result(
    story: str,
    target_characters: int,
    passed_checks: list[str],
    warnings: list[str],
    failed_checks: list[str],
    agent_estimates: list[AgentMicroEstimate],
    reports_path: Path,
) -> MicroReadinessResult:
    status = choose_status(failed_checks, warnings)
    recommended_action = recommended_action_for_status(status)
    result_path = reports_path / "micro_readiness_result.yaml"
    report_path = reports_path / "micro_readiness_report.md"

    result = MicroReadinessResult(
        story=story,
        status=status,
        target_characters=target_characters,
        passed_checks=passed_checks,
        warnings=warnings,
        failed_checks=failed_checks,
        agent_estimates=agent_estimates,
        recommended_action=recommended_action,
        result_path=result_path,
        report_path=report_path,
        terminal_summary="",
    )
    return MicroReadinessResult(
        story=result.story,
        status=result.status,
        target_characters=result.target_characters,
        passed_checks=result.passed_checks,
        warnings=result.warnings,
        failed_checks=result.failed_checks,
        agent_estimates=result.agent_estimates,
        recommended_action=result.recommended_action,
        result_path=result.result_path,
        report_path=result.report_path,
        terminal_summary=format_terminal_summary(result),
    )


def choose_status(failed_checks: list[str], warnings: list[str]) -> str:
    if any("story.md is missing" in check for check in failed_checks):
        return NEEDS_REVIEW
    if any("agent_plan.yaml is not valid YAML" in check for check in failed_checks):
        return NEEDS_REVIEW
    if any("agent_plan.yaml must be a YAML mapping" in check for check in failed_checks):
        return NEEDS_REVIEW
    if any("More than 15 acceptance criteria" in check for check in failed_checks):
        return TOO_LARGE_FOR_MICRO
    if any("Several assigned agents exceed" in check for check in failed_checks):
        return TOO_LARGE_FOR_MICRO
    if any("touch many unrelated modules" in check for check in failed_checks):
        return TOO_LARGE_FOR_MICRO
    if any("several split signals" in check for check in failed_checks):
        return TOO_LARGE_FOR_MICRO
    if failed_checks:
        return NEEDS_REVIEW
    if warnings:
        return MICRO_READY_WITH_WARNINGS
    return READY_FOR_MICRO


def recommended_action_for_status(status: str) -> str:
    if status == READY_FOR_MICRO:
        return "Proceed with micro-mode local-agent assignments for focused agent tasks."
    if status == MICRO_READY_WITH_WARNINGS:
        return "Address the warnings if practical, then use micro mode with human review."
    if status == TOO_LARGE_FOR_MICRO:
        return "Split or narrow the story before relying on agent-specific micro prompts."
    return "Review and complete the missing or invalid story planning information."


def write_micro_readiness_result(path: Path, result: MicroReadinessResult) -> None:
    data = {
        "story": result.story,
        "status": result.status,
        "target_characters": result.target_characters,
        "passed_checks": result.passed_checks,
        "warnings": result.warnings,
        "failed_checks": result.failed_checks,
        "agent_estimates": [agent_estimate_to_mapping(estimate) for estimate in result.agent_estimates],
        "recommended_action": result.recommended_action,
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def agent_estimate_to_mapping(estimate: AgentMicroEstimate) -> dict[str, Any]:
    return {
        "agent_id": estimate.agent_id,
        "responsibility": estimate.responsibility,
        "expected_output": estimate.expected_output,
        "estimated_characters": estimate.estimated_characters,
        "target_characters": estimate.target_characters,
        "fits_target": estimate.fits_target,
        "source_files": estimate.source_files,
        "warnings": estimate.warnings,
    }


def write_micro_readiness_report(path: Path, result: MicroReadinessResult) -> None:
    content = f"""# Micro Readiness Report

## Story

{result.story}

## Plain-English Explanation

Micro readiness asks whether each assigned agent can receive a short, clear micro prompt for its own responsibility. The whole story does not need to fit in one tiny prompt, but each agent task should be small enough to summarize without dragging in unrelated context.

## Story Sizing Verdict

{result.status}

## Per-Agent Micro Prompt Estimate

{format_agent_estimate_sections(result.agent_estimates)}
## Warnings

{format_check_list(result.warnings)}
## Failed Checks

{format_check_list(result.failed_checks)}
## Recommended Action

{result.recommended_action}

## Split Examples

- Split by workflow area, such as CLI behavior first and documentation updates second.
- Split by agent responsibility when one agent needs a much larger prompt than the others.
- Split broad acceptance criteria into separate stories with their own not-in-scope boundaries.
- Move exploratory cleanup or unrelated module changes into a later story.
"""
    path.write_text(content, encoding="utf-8")


def format_agent_estimate_sections(estimates: list[AgentMicroEstimate]) -> str:
    if not estimates:
        return "- No agent estimates were produced.\n"

    sections: list[str] = []
    for estimate in estimates:
        fit = "yes" if estimate.fits_target else "no"
        sections.extend(
            [
                f"### {estimate.agent_id}",
                "",
                f"- Estimated characters: {estimate.estimated_characters}",
                f"- Target characters: {estimate.target_characters}",
                f"- Fits target: {fit}",
                f"- Expected output: {estimate.expected_output}",
                f"- Responsibility: {estimate.responsibility}",
                f"- Source files: {', '.join(estimate.source_files) or 'None'}",
                "",
            ]
        )
    return "\n".join(sections)


def format_terminal_summary(result: MicroReadinessResult) -> str:
    fitting_agents = sum(1 for estimate in result.agent_estimates if estimate.fits_target)
    total_agents = len(result.agent_estimates)
    lines = [
        f"Micro readiness checked for: {result.story}",
        f"Status: {result.status}",
        f"Target characters per agent: {result.target_characters}",
        f"Agent prompts fitting target: {fitting_agents}/{total_agents}",
        f"Warnings: {len(result.warnings)}",
        f"Failed checks: {len(result.failed_checks)}",
        f"Result: {result.result_path}",
        f"Report: {result.report_path}",
        f"Recommended action: {result.recommended_action}",
        (
            "Safety: no local models, cloud models, agents, model output application, GitHub "
            "actions, commits, merges, or deploys were run."
        ),
    ]
    return "\n".join(lines)


def parse_story_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_heading = ""

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_heading = stripped[3:].strip()
            sections[current_heading] = []
            continue
        if current_heading:
            sections[current_heading].append(line)

    return {heading: "\n".join(lines).strip() for heading, lines in sections.items()}


def markdown_section(markdown: str, heading: str) -> str:
    target = heading.casefold()
    for section_heading, content in parse_story_sections(markdown).items():
        if section_heading.casefold() == target:
            return content
    return ""


def markdown_bullets(markdown: str) -> list[str]:
    bullets: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullet = stripped[2:].strip()
            if bullet and bullet != "TODO":
                bullets.append(bullet)
    return bullets


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and stripped != "TODO":
            return stripped
    return ""


def looks_vague(text: str) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in VAGUE_GOAL_TERMS)


def count_module_signals(text: str) -> int:
    found = matching_terms(text, MODULE_SIGNAL_TERMS)
    path_like_terms = set(
        re.findall(r"\b(?:src|tests|docs|stories|blueprints)/[A-Za-z0-9_./-]+", text)
    )
    found.update(path_like_terms)
    return len(found)


def matching_terms(text: str, terms: set[str]) -> set[str]:
    lowered = text.casefold()
    found: set[str] = set()
    for term in terms:
        if term.casefold() in lowered:
            found.add(term)
    return found


def one_line(text: str, limit: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def text_value(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key)
    if value is None:
        return default
    return str(value)


def relative_path(story_path: Path, path: Path) -> str:
    try:
        return path.relative_to(story_path).as_posix()
    except ValueError:
        return str(path)


def format_check_list(checks: list[str]) -> str:
    if not checks:
        return "- None\n"
    return "\n".join(f"- {check}" for check in checks) + "\n"


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
