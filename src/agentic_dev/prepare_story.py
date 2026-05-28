from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.agent_assignment import assign_agents
from agentic_dev.prompt_pack import generate_prompt_pack, load_agent_plan, ordered_assigned_agents


@dataclass(frozen=True)
class PrepareStoryResult:
    story: str
    story_path: Path
    agent_plan_path: Path
    prompt_pack_path: Path
    runbook_path: Path
    report_path: Path
    status_path: Path
    prompt_files_created: list[Path]
    prompt_files_skipped: list[Path]


def prepare_story(project_path: Path, story: str, force: bool = False) -> PrepareStoryResult:
    """Prepare a story workspace for agent execution without running agents."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    agent_plan_path = story_path / "agent_plan.yaml"
    if force or not agent_plan_path.exists():
        agent_plan_path = assign_agents(project_path, story, force=force)

    prompt_pack_result = generate_prompt_pack(project_path, story, force=force)

    agent_plan = load_agent_plan(agent_plan_path)
    assigned_agents = ordered_assigned_agents(agent_plan)

    runbook_path = story_path / "story_runbook.md"
    runbook_path.write_text(
        format_runbook(story, assigned_agents, prompt_pack_result.prompt_pack_path),
        encoding="utf-8",
    )

    status_path = story_path / "status.yaml"
    update_status(status_path, story)

    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)
    report_path = reports_path / "prepare_story_report.md"

    result = PrepareStoryResult(
        story=story,
        story_path=story_path,
        agent_plan_path=agent_plan_path,
        prompt_pack_path=prompt_pack_result.prompt_pack_path,
        runbook_path=runbook_path,
        report_path=report_path,
        status_path=status_path,
        prompt_files_created=prompt_pack_result.created_files,
        prompt_files_skipped=prompt_pack_result.skipped_files,
    )

    report_path.write_text(format_prepare_report(result), encoding="utf-8")

    return result


def update_status(status_path: Path, story: str) -> None:
    status = load_status(status_path)
    status["story_id"] = status.get("story_id") or story
    status["status"] = "prepared"
    status["ready_for_review"] = False

    status_path.write_text(yaml.safe_dump(status, sort_keys=False), encoding="utf-8")


def load_status(status_path: Path) -> dict[str, Any]:
    if not status_path.exists():
        return {}

    with status_path.open("r", encoding="utf-8") as status_file:
        loaded = yaml.safe_load(status_file)

    if loaded is None:
        return {}

    if not isinstance(loaded, dict):
        raise ValueError(f"status.yaml must be a YAML mapping: {status_path}")

    return loaded


def format_runbook(
    story: str,
    assigned_agents: list[dict[str, Any]],
    prompt_pack_path: Path,
) -> str:
    agents = "\n".join(
        f"- {text_value(agent, 'display_name', text_value(agent, 'id', 'unknown_agent'))} "
        f"(`{text_value(agent, 'id', 'unknown_agent')}`): "
        f"{text_value(agent, 'expected_output', 'No expected output listed.')}"
        for agent in assigned_agents
    )
    execution_order = "\n".join(
        f"{index}. {text_value(agent, 'display_name', text_value(agent, 'id', 'unknown_agent'))}"
        for index, agent in enumerate(assigned_agents, start=1)
    )

    return f"""# Story Runbook

## Story

`{story}` is prepared for agent execution.

## Assigned Agents

{agents}

## Prompt Files

Prompt files are in `{prompt_pack_path}`.

## Recommended Execution Order

{execution_order}

## After Agent Work

Run these commands after the assigned agents finish their work:

```powershell
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic review-bundle --story {story}
docker compose run --rm dev agentic quality-gate --story {story}
```
"""


def format_prepare_report(result: PrepareStoryResult) -> str:
    created = format_path_list(result.prompt_files_created)
    skipped = format_path_list(result.prompt_files_skipped)

    return f"""# Prepare Story Report

## Story

{result.story}

## Generated Files

- Agent plan: `{result.agent_plan_path}`
- Prompt pack: `{result.prompt_pack_path}`
- Runbook: `{result.runbook_path}`
- Status: `{result.status_path}`

## Prompt Files Created Or Updated

{created}

## Prompt Files Skipped

{skipped}

## Notes

- Agents were not executed.
- Cloud models were not run.
- Review bundle was not created.
- Quality gate was not run.
"""


def format_path_list(paths: list[Path]) -> str:
    if not paths:
        return "- None\n"

    return "\n".join(f"- `{path}`" for path in paths) + "\n"


def text_value(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key)

    if value is None:
        return default

    return str(value)
