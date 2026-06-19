from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentic_dev.scaffolding import CORE_AGENT_INSTRUCTIONS, write_if_missing
from agentic_dev.test_layers import DEFAULT_TEST_LAYER_PLAN, TEST_LAYER_NAMES


DEFAULT_BLUEPRINT_RELATIVE_PATH = Path("blueprints") / "blueprint.yaml"


def generate_stories(project_path: Path, blueprint_path: Path | None = None) -> list[Path]:
    """Create story workspaces from a YAML blueprint."""
    project_path = project_path.resolve()

    if blueprint_path is None:
        blueprint_path = project_path / DEFAULT_BLUEPRINT_RELATIVE_PATH
        if not blueprint_path.exists():
            raise FileNotFoundError(
                "Default blueprint not found. Expected blueprints/blueprint.yaml. "
                "Pass --blueprint to use another file.",
            )
    else:
        blueprint_path = blueprint_path.resolve()

    blueprint = load_blueprint(blueprint_path)
    stories = blueprint.get("stories")

    if not isinstance(stories, list):
        raise ValueError("Blueprint must include a top-level 'stories' list.")

    created_paths: list[Path] = []

    for story in stories:
        if not isinstance(story, dict):
            raise ValueError("Each story in the blueprint must be a mapping.")

        created_paths.extend(create_story_workspace(project_path, story))

    return created_paths


def load_blueprint(blueprint_path: Path) -> dict[str, Any]:
    """Read and validate a YAML blueprint file."""
    if not blueprint_path.exists():
        raise FileNotFoundError(f"Blueprint file does not exist: {blueprint_path}")

    with blueprint_path.open("r", encoding="utf-8") as blueprint_file:
        loaded = yaml.safe_load(blueprint_file)

    if not isinstance(loaded, dict):
        raise ValueError("Blueprint must be a YAML mapping.")

    return loaded


def create_story_workspace(project_path: Path, story: dict[str, Any]) -> list[Path]:
    """Create one story workspace without overwriting existing files."""
    slug = story.get("slug")

    if not isinstance(slug, str) or not slug.strip():
        raise ValueError("Each story must include a non-empty 'slug' field.")

    story_path = project_path / "stories" / slug
    created_paths: list[Path] = []

    directories = [
        story_path,
        story_path / "instructions",
        story_path / "reports",
        story_path / "review_bundle",
        story_path / "docs",
        story_path / "improvements",
    ]

    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created_paths.append(directory)

    files = {
        story_path / "story.md": format_story_markdown(story),
        story_path / "status.yaml": format_status_yaml(story),
        story_path / "test_plan.yaml": format_test_plan_yaml(story),
        story_path / "monitoring_plan.yaml": format_monitoring_plan_yaml(story),
    }

    for file_path, content in files.items():
        existed = file_path.exists()
        write_if_missing(file_path, content)
        if not existed:
            created_paths.append(file_path)

    instruction_dir = story_path / "instructions"

    for filename, instruction in CORE_AGENT_INSTRUCTIONS.items():
        file_path = instruction_dir / filename
        existed = file_path.exists()
        write_if_missing(file_path, format_instruction_file(filename, instruction))
        if not existed:
            created_paths.append(file_path)

    return created_paths


def format_story_markdown(story: dict[str, Any]) -> str:
    story_id = text_value(story, "id", "UNKNOWN")
    title = text_value(story, "title", "Untitled Story")
    goal = text_value(story, "goal", "TODO")
    why_it_matters = text_value(story, "why_it_matters", text_value(story, "why", "TODO"))
    implementation_scope = story.get("implementation_scope")

    sections = [
        f"# {story_id}: {title}",
        "",
        "## Goal",
        "",
        goal,
        "",
        "## Why This Matters",
        "",
        why_it_matters,
        "",
        "## Acceptance Criteria",
        "",
        format_markdown_list(story.get("acceptance_criteria")),
        "",
    ]

    if isinstance(implementation_scope, list) and implementation_scope:
        sections.extend(
            [
                "## Implementation Review Scope",
                "",
                format_markdown_list(implementation_scope),
                "",
            ],
        )

        if story.get("not_in_scope") is not None:
            sections.extend(
                [
                    "## Historical Blueprint Notes",
                    "",
                    format_markdown_list(story.get("not_in_scope")),
                    "",
                ],
            )
    else:
        sections.extend(
            [
                "## Not In Scope",
                "",
                format_markdown_list(story.get("not_in_scope")),
                "",
            ],
        )

    sections.extend(
        [
            "## Definition of Done",
            "",
            format_markdown_list(story.get("definition_of_done")),
            "",
        ],
    )

    return "\n".join(sections) + "\n"


def format_status_yaml(story: dict[str, Any]) -> str:
    story_id = text_value(story, "story_id", text_value(story, "id", "UNKNOWN"))
    slug = text_value(story, "slug", "")

    lines = [f"story_id: {story_id}"]
    if slug:
        lines.append(f"slug: {slug}")
    lines.extend(["status: pending", "ready_for_review: false"])
    return "\n".join(lines) + "\n"


def format_test_plan_yaml(story: dict[str, Any]) -> str:
    test_plan = story.get("test_plan")

    if not isinstance(test_plan, dict):
        test_plan = {}

    return yaml.safe_dump(build_test_layer_plan(test_plan), sort_keys=False)


def build_test_layer_plan(test_plan: dict[str, Any]) -> dict[str, Any]:
    generated_plan: dict[str, Any] = {
        "test_layers_version": DEFAULT_TEST_LAYER_PLAN["test_layers_version"],
    }

    for layer_name in TEST_LAYER_NAMES:
        generated_plan[layer_name] = normalize_test_layer(layer_name, test_plan)

    return generated_plan


def normalize_test_layer(layer_name: str, test_plan: dict[str, Any]) -> dict[str, Any]:
    defaults = DEFAULT_TEST_LAYER_PLAN[layer_name]
    layer = test_plan.get(layer_name)

    if isinstance(layer, dict):
        evidence = layer.get("evidence_or_reason", defaults["evidence_or_reason"])
        return {
            "required": layer.get("required", defaults["required"]),
            "action": layer.get("action", defaults["action"]),
            "frequency": layer.get("frequency", defaults["frequency"]),
            "evidence_or_reason": evidence_or_default(evidence, defaults["evidence_or_reason"]),
        }

    if layer is not None:
        return {
            "required": defaults["required"],
            "action": defaults["action"],
            "frequency": defaults["frequency"],
            "evidence_or_reason": evidence_or_default(layer, defaults["evidence_or_reason"]),
        }

    return {
        "required": defaults["required"],
        "action": defaults["action"],
        "frequency": defaults["frequency"],
        "evidence_or_reason": defaults["evidence_or_reason"],
    }


def evidence_or_default(value: Any, default: str) -> str:
    if isinstance(value, list):
        evidence = "; ".join(str(item) for item in value if str(item).strip())
        return evidence or default

    if value is None:
        return default

    evidence = str(value).strip()
    return evidence or default


def format_monitoring_plan_yaml(story: dict[str, Any]) -> str:
    monitoring_plan = story.get("monitoring_plan")

    if not isinstance(monitoring_plan, dict):
        monitoring_plan = {}

    return yaml.safe_dump(
        {
            "logs_required": monitoring_plan.get("logs_required", []),
            "watch_for": monitoring_plan.get("watch_for", []),
        },
        sort_keys=False,
    )


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


def format_markdown_list(value: Any) -> str:
    if isinstance(value, list):
        items = [str(item) for item in value]
    elif value:
        items = [str(value)]
    else:
        items = ["TODO"]

    return "\n".join(f"- {item}" for item in items)


def text_value(story: dict[str, Any], key: str, default: str) -> str:
    value = story.get(key)

    if value is None:
        return default

    return str(value)
