from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentic_dev.scaffolding import CORE_AGENT_INSTRUCTIONS, write_if_missing
from agentic_dev.story_blueprint import load_blueprint_story


class IndentedYamlDumper(yaml.SafeDumper):
    """Keep YAML lists indented under their keys for easier reading."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


CORE_AGENT_TEAM = [
    {
        "id": "research_agent",
        "display_name": "Research Agent",
        "responsibility": "Research story scope, risks, best practices, and useful references.",
        "instruction_file": "instructions/research_agent.md",
        "expected_output": "reports/research_report.md",
    },
    {
        "id": "planner_agent",
        "display_name": "Planner Agent",
        "responsibility": "Create a practical implementation plan for this story.",
        "instruction_file": "instructions/planner_agent.md",
        "expected_output": "reports/planner_report.md",
    },
    {
        "id": "developer_agent",
        "display_name": "Developer Agent",
        "responsibility": "Implement only the approved story scope. Do not write tests.",
        "instruction_file": "instructions/developer_agent.md",
        "expected_output": "reports/developer_report.md",
    },
    {
        "id": "test_agent",
        "display_name": "Test Agent",
        "responsibility": "Write independent tests based on the story acceptance criteria.",
        "instruction_file": "instructions/test_agent.md",
        "expected_output": "reports/test_report.md",
    },
    {
        "id": "docs_agent",
        "display_name": "Docs Agent",
        "responsibility": "Update documentation related to this story.",
        "instruction_file": "instructions/docs_agent.md",
        "expected_output": "reports/docs_report.md",
    },
    {
        "id": "security_quality_agent",
        "display_name": "Security/Quality Agent",
        "responsibility": "Check for secrets, unsafe behavior, bad patterns, and quality risks.",
        "instruction_file": "instructions/security_quality_agent.md",
        "expected_output": "reports/security_quality_report.md",
    },
    {
        "id": "local_reviewer_agent",
        "display_name": "Local Reviewer Agent",
        "responsibility": "Review all work and decide whether it is ready for cloud/human review.",
        "instruction_file": "instructions/local_reviewer_agent.md",
        "expected_output": "reports/local_review_report.md",
    },
]

ROLE_TO_AGENT_ID = {
    "research": "research_agent",
    "planner": "planner_agent",
    "developer": "developer_agent",
    "test": "test_agent",
    "documentation": "docs_agent",
    "docs": "docs_agent",
    "security_quality": "security_quality_agent",
    "local_reviewer": "local_reviewer_agent",
}

AGENT_ID_TO_ROLE = {
    "research_agent": "research",
    "planner_agent": "planner",
    "developer_agent": "developer",
    "test_agent": "test",
    "docs_agent": "documentation",
    "security_quality_agent": "security_quality",
    "local_reviewer_agent": "local_reviewer",
}

CORE_AGENT_BY_ID = {agent["id"]: agent for agent in CORE_AGENT_TEAM}


def assign_agents(project_path: Path, story: str, force: bool = False) -> Path:
    """Create an agent execution plan for a story workspace."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists() or not story_path.is_dir():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    agent_plan_path = story_path / "agent_plan.yaml"

    if agent_plan_path.exists() and not force:
        raise ValueError(
            f"Agent plan already exists: {agent_plan_path}. "
            "Use --force to regenerate it.",
        )

    ensure_instruction_files(story_path)

    blueprint_story = load_blueprint_story(project_path, story_path)
    assigned_agents = ordered_blueprint_assigned_agents(blueprint_story) or CORE_AGENT_TEAM
    plan = {
        "story": story,
        "status": "pending_execution",
        "execution_order": [agent["id"] for agent in assigned_agents],
        "assigned_agents": assigned_agents,
    }

    agent_plan_path.write_text(format_agent_plan(plan), encoding="utf-8")

    return agent_plan_path


def ensure_instruction_files(story_path: Path) -> None:
    """Create missing core instruction files for a story."""
    instruction_dir = story_path / "instructions"

    for filename, instruction in CORE_AGENT_INSTRUCTIONS.items():
        write_if_missing(instruction_dir / filename, format_instruction_file(filename, instruction))


def format_instruction_file(filename: str, instruction: str) -> str:
    title = filename.replace("_", " ").replace(".md", "").title()

    return f"""# {title}

## Role

{instruction}

## Story

Read `../story.md` before doing any work.

## Output

Write your results into the story `reports/` folder.
"""


def format_agent_plan(plan: dict[str, Any]) -> str:
    return yaml.dump(plan, Dumper=IndentedYamlDumper, sort_keys=False, width=1000)


def ordered_blueprint_assigned_agents(blueprint_story: dict[str, Any] | None) -> list[dict[str, Any]]:
    assigned_agents = blueprint_assigned_agents(blueprint_story)
    if not assigned_agents or blueprint_story is None:
        return assigned_agents

    execution_order = blueprint_story.get("execution_order")
    if not isinstance(execution_order, list):
        return assigned_agents

    by_role = {str(agent.get("role", "")): agent for agent in assigned_agents}
    ordered: list[dict[str, Any]] = []
    for role_name in execution_order:
        if not isinstance(role_name, str):
            continue
        agent = by_role.get(role_name.strip())
        if agent is not None:
            ordered.append(agent)

    ordered_ids = {agent["id"] for agent in ordered}
    ordered.extend(agent for agent in assigned_agents if agent["id"] not in ordered_ids)
    return ordered


def blueprint_assigned_agents(blueprint_story: dict[str, Any] | None) -> list[dict[str, Any]]:
    if blueprint_story is None:
        return []

    agents = blueprint_story.get("agents")
    if not isinstance(agents, dict) or not agents:
        return []

    assigned_agents: list[dict[str, Any]] = []
    for role_name, details in agents.items():
        if not isinstance(role_name, str) or not role_name.strip():
            continue

        agent_id = ROLE_TO_AGENT_ID.get(role_name.strip())
        if agent_id is None:
            continue

        base_agent = CORE_AGENT_BY_ID[agent_id]
        assigned_agent = dict(base_agent)
        assigned_agent["role"] = AGENT_ID_TO_ROLE[agent_id]

        if isinstance(details, dict):
            model = details.get("model")
            if isinstance(model, str) and model.strip():
                assigned_agent["model"] = model.strip()

            writable_paths = details.get("writable_paths")
            if isinstance(writable_paths, list):
                assigned_agent["writable_paths"] = [
                    path.strip()
                    for path in writable_paths
                    if isinstance(path, str) and path.strip()
                ]

            responsibility = details.get("responsibility")
            if isinstance(responsibility, str) and responsibility.strip():
                assigned_agent["responsibility"] = responsibility.strip()

            expected_output = details.get("expected_output")
            if isinstance(expected_output, str) and expected_output.strip():
                assigned_agent["expected_output"] = expected_output.strip()

        assigned_agents.append(assigned_agent)

    return assigned_agents
