from __future__ import annotations

from pathlib import Path


CORE_AGENT_INSTRUCTIONS = {
    "research_agent.md": "Research the story scope, risks, best practices, and useful references.",
    "planner_agent.md": "Create a practical implementation plan for this story.",
    "developer_agent.md": "Implement only the approved story scope. Do not write tests.",
    "test_agent.md": "Write independent tests based on the story acceptance criteria.",
    "docs_agent.md": "Update documentation related to this story.",
    "security_quality_agent.md": "Check for secrets, unsafe behavior, bad patterns, and quality risks.",
    "local_reviewer_agent.md": "Review all work and decide whether it is ready for cloud/human review.",
}


def write_if_missing(path: Path, content: str) -> None:
    """Create a file only if it does not already exist."""
    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def init_project(project_path: Path) -> list[Path]:
    """Prepare a project folder for the agentic development workflow."""
    project_path = project_path.resolve()
    project_name = project_path.name
    created_paths: list[Path] = []

    directories = [
        project_path / ".agentic",
        project_path / ".agentic" / "improvement_queue" / "pending",
        project_path / ".agentic" / "improvement_queue" / "approved",
        project_path / ".agentic" / "improvement_queue" / "rejected",
        project_path / ".agentic" / "maintenance_queue" / "pending",
        project_path / ".agentic" / "maintenance_queue" / "approved",
        project_path / ".agentic" / "maintenance_queue" / "resolved",
        project_path / ".agentic" / "feature_queue" / "pending",
        project_path / ".agentic" / "feature_queue" / "approved",
        project_path / ".agentic" / "feature_queue" / "rejected",
        project_path / "blueprints",
        project_path / "stories",
        project_path / "stories" / "story_001_project_setup",
        project_path / "stories" / "story_001_project_setup" / "instructions",
        project_path / "stories" / "story_001_project_setup" / "reports",
        project_path / "stories" / "story_001_project_setup" / "review_bundle",
        project_path / "stories" / "story_001_project_setup" / "docs",
        project_path / "stories" / "story_001_project_setup" / "improvements",
        project_path / "src",
        project_path / "tests",
        project_path / "docs",
    ]

    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created_paths.append(directory)

    files = {
        project_path / ".agentic" / "project.yaml": f"""project_name: {project_name}
project_type: unknown
description: Project prepared for agentic development.
""",
        project_path / ".agentic" / "rules.yaml": """rules:
  - Developer agent must not write tests.
  - Test agent must write tests independently.
  - Human approval is required before merge.
  - Do not commit secrets, API keys, private keys, or .env files.
""",
        project_path / ".agentic" / "quality_gates.yaml": """quality_gates:
  - tests_required
  - docs_required
  - review_bundle_required
  - local_review_required
""",
        project_path / "blueprints" / "blueprint.md": """# Project Blueprint

## Vision

Describe what this project is supposed to become.

## Users

Describe who uses it.

## Requirements

List must-have requirements.

## Non-goals

List what is intentionally not being built yet.

## Risks

List technical, security, and product risks.
""",
        project_path / "stories" / "story_001_project_setup" / "story.md": """# STORY-001: Project Setup

## Goal

Prepare this project for the reusable agentic development workflow.

## Acceptance Criteria

- `.agentic/` folder exists.
- `blueprints/` folder exists.
- `stories/` folder exists.
- This story has instructions, reports, review_bundle, docs, and improvements folders.
- Project has standard `src/`, `tests/`, and `docs/` folders.

## Not In Scope

- No real feature implementation yet.
- No production deployment.
- No autonomous merge.

## Definition of Done

- The project has a clean agentic workspace structure.
- A human can understand what each folder is for.
""",
        project_path / "stories" / "story_001_project_setup" / "status.yaml": """story_id: STORY-001
status: initialized
ready_for_review: false
""",
        project_path / "README.md": """# Sandbox Product

This project was initialized with the reusable agentic development system.

## Key folders

- `.agentic/` stores project rules, quality gates, and queues.
- `blueprints/` stores the high-level project blueprint.
- `stories/` stores story workspaces.
- `src/` stores product code.
- `tests/` stores actual tests.
- `docs/` stores permanent project documentation.
""",
    }

    for file_path, content in files.items():
        existed = file_path.exists()
        write_if_missing(file_path, content)
        if not existed:
            created_paths.append(file_path)

    instruction_dir = project_path / "stories" / "story_001_project_setup" / "instructions"

    for filename, instruction in CORE_AGENT_INSTRUCTIONS.items():
        file_path = instruction_dir / filename
        existed = file_path.exists()
        write_if_missing(
            file_path,
            f"""# {filename.replace("_", " ").replace(".md", "").title()}

## Role

{instruction}

## Story

Read `../story.md` before doing any work.

## Output

Write your results into the story `reports/` folder.
""",
        )
        if not existed:
            created_paths.append(file_path)

    return created_paths
