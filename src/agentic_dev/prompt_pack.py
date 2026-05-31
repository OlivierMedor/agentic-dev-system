from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.runtime_config import load_runtime_config, runtime_config_path


PROMPT_FILENAMES = {
    "research_agent": "01_research_agent_prompt.md",
    "planner_agent": "02_planner_agent_prompt.md",
    "developer_agent": "03_developer_agent_prompt.md",
    "test_agent": "04_test_agent_prompt.md",
    "docs_agent": "05_docs_agent_prompt.md",
    "security_quality_agent": "06_security_quality_agent_prompt.md",
    "local_reviewer_agent": "07_local_reviewer_agent_prompt.md",
}

AGENT_SPECIFIC_RULES = {
    "developer_agent": "Do not write tests. Implementation only.",
    "test_agent": (
        "Do not modify implementation code unless a tiny fix is required to make tests "
        "runnable, and explain any such fix."
    ),
    "local_reviewer_agent": "Do not approve unless pytest and Ruff pass.",
    "security_quality_agent": (
        "Check for secrets, unsafe behavior, excessive permissions, and risky file access."
    ),
}


@dataclass(frozen=True)
class PromptPackResult:
    prompt_pack_path: Path
    created_files: list[Path]
    skipped_files: list[Path]


def generate_prompt_pack(project_path: Path, story: str, force: bool = False) -> PromptPackResult:
    """Generate Codex-ready prompt files for each assigned story agent."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists() or not story_path.is_dir():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    agent_plan_path = story_path / "agent_plan.yaml"
    if not agent_plan_path.exists():
        raise FileNotFoundError(f"Required agent plan does not exist: {agent_plan_path}")

    agent_plan = load_agent_plan(agent_plan_path)
    assigned_agents = ordered_assigned_agents(agent_plan)

    prompt_pack_path = story_path / "prompt_pack"
    prompt_pack_path.mkdir(parents=True, exist_ok=True)

    context = {
        "story": read_required_text(story_path / "story.md"),
        "agent_plan": read_required_text(agent_plan_path),
        "test_plan": read_optional_text(story_path / "test_plan.yaml"),
        "monitoring_plan": read_optional_text(story_path / "monitoring_plan.yaml"),
        "project_rules": read_optional_text(project_path / ".agentic" / "rules.yaml"),
        "quality_gates": read_optional_text(project_path / ".agentic" / "quality_gates.yaml"),
        "runtime_config": read_runtime_config_text(project_path),
        "runtime_agents": load_runtime_agents(project_path),
    }

    created_files: list[Path] = []
    skipped_files: list[Path] = []

    for index, agent in enumerate(assigned_agents, start=1):
        agent_id = text_value(agent, "id", f"agent_{index}")
        prompt_path = prompt_pack_path / prompt_filename(agent_id, index)

        if prompt_path.exists() and not force:
            skipped_files.append(prompt_path)
            continue

        prompt_path.write_text(
            format_agent_prompt(story, agent, context),
            encoding="utf-8",
        )
        created_files.append(prompt_path)

    return PromptPackResult(
        prompt_pack_path=prompt_pack_path,
        created_files=created_files,
        skipped_files=skipped_files,
    )


def load_agent_plan(agent_plan_path: Path) -> dict[str, Any]:
    with agent_plan_path.open("r", encoding="utf-8") as agent_plan_file:
        loaded = yaml.safe_load(agent_plan_file)

    if not isinstance(loaded, dict):
        raise ValueError("agent_plan.yaml must be a YAML mapping.")

    return loaded


def ordered_assigned_agents(agent_plan: dict[str, Any]) -> list[dict[str, Any]]:
    assigned_agents = agent_plan.get("assigned_agents")

    if not isinstance(assigned_agents, list) or not assigned_agents:
        raise ValueError("agent_plan.yaml must include a non-empty 'assigned_agents' list.")

    agents: list[dict[str, Any]] = []
    for agent in assigned_agents:
        if not isinstance(agent, dict):
            raise ValueError("Each assigned agent in agent_plan.yaml must be a mapping.")
        agents.append(agent)

    execution_order = agent_plan.get("execution_order")
    if not isinstance(execution_order, list):
        return agents

    agents_by_id = {text_value(agent, "id", ""): agent for agent in agents}
    ordered_agents: list[dict[str, Any]] = []

    for agent_id in execution_order:
        if isinstance(agent_id, str) and agent_id in agents_by_id:
            ordered_agents.append(agents_by_id[agent_id])

    ordered_ids = {text_value(agent, "id", "") for agent in ordered_agents}
    ordered_agents.extend(
        agent for agent in agents if text_value(agent, "id", "") not in ordered_ids
    )

    return ordered_agents


def prompt_filename(agent_id: str, index: int) -> str:
    if agent_id in PROMPT_FILENAMES:
        return PROMPT_FILENAMES[agent_id]

    safe_agent_id = re.sub(r"[^a-z0-9_]+", "_", agent_id.lower()).strip("_")
    if not safe_agent_id:
        safe_agent_id = "agent"

    return f"{index:02d}_{safe_agent_id}_prompt.md"


def format_agent_prompt(story: str, agent: dict[str, Any], context: dict[str, Any]) -> str:
    agent_id = text_value(agent, "id", "unknown_agent")
    display_name = text_value(agent, "display_name", agent_id.replace("_", " ").title())
    responsibility = text_value(agent, "responsibility", "Use the story and plans to do your role.")
    expected_output = text_value(agent, "expected_output", "Write a report in the story reports folder.")
    agent_rule = AGENT_SPECIFIC_RULES.get(agent_id, "Follow only the responsibilities assigned to you.")
    runtime_expectation = format_runtime_expectation(agent_id, context["runtime_agents"])

    return f"""# {display_name} Prompt

## Agent Identity

You are the {display_name} for `{story}`.

## Story Name

`{story}`

## Story File Content

```markdown
{context["story"].rstrip()}
```

## Agent Responsibility

{responsibility}

## Expected Output

{expected_output}

## Project Rules

```yaml
{context["project_rules"].rstrip()}
```

## Quality Gates

```yaml
{context["quality_gates"].rstrip()}
```

## Test Plan

```yaml
{context["test_plan"].rstrip()}
```

## Monitoring Plan

```yaml
{context["monitoring_plan"].rstrip()}
```

## Runtime Config

```yaml
{context["runtime_config"].rstrip()}
```

## Runtime Expectation

{runtime_expectation}

## Agent-Specific Rule

{agent_rule}

## Do-Not-Do Rules

- Do not commit anything.
- Do not create zip files.
- Do not make unrelated changes.
- Do not overwrite another agent's report unless explicitly instructed.
- Do not ignore project rules, quality gates, test plan, or monitoring plan.

## Final Reporting Requirement

Before finishing, write the expected output file and include:
- Files changed
- What you did
- Validation performed
- Assumptions
- Warnings or uncertainty
"""


def read_required_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Required file does not exist: {path}")

    return path.read_text(encoding="utf-8")


def read_optional_text(path: Path) -> str:
    if not path.exists():
        return f"# Not found: {path.name}\n"

    return path.read_text(encoding="utf-8")


def read_runtime_config_text(project_path: Path) -> str:
    config_path = runtime_config_path(project_path)

    if not config_path.exists():
        return f"# Not found: {config_path.name}\n"

    return read_required_text(config_path)


def load_runtime_agents(project_path: Path) -> dict[str, Any]:
    config_path = runtime_config_path(project_path)

    if not config_path.exists():
        return {}

    _, runtime_config = load_runtime_config(project_path)
    agents = runtime_config.get("agents")

    if not isinstance(agents, dict):
        raise ValueError(f"Runtime config agents section must be a mapping: {config_path}")

    return agents


def format_runtime_expectation(agent_id: str, runtime_agents: dict[str, Any]) -> str:
    runtime_agent = runtime_agents.get(agent_id)

    if not isinstance(runtime_agent, dict):
        return "No runtime config entry found for this agent."

    provider = text_value(runtime_agent, "provider", "not configured")
    model = text_value(runtime_agent, "model", "not configured")
    approval_mode = text_value(runtime_agent, "approval_mode", "not configured")
    fallback_provider = text_value(runtime_agent, "fallback_provider", "not configured")

    return "\n".join(
        [
            f"- Provider: `{provider}`",
            f"- Model: `{model}`",
            f"- Approval mode: `{approval_mode}`",
            f"- Fallback provider: `{fallback_provider}`",
        ]
    )


def text_value(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key)

    if value is None:
        return default

    return str(value)
