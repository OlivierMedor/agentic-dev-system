from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentic_dev.scaffolding import CORE_AGENT_INSTRUCTIONS, write_if_missing


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

    plan = {
        "story": story,
        "status": "pending_execution",
        "execution_order": [agent["id"] for agent in CORE_AGENT_TEAM],
        "assigned_agents": CORE_AGENT_TEAM,
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
