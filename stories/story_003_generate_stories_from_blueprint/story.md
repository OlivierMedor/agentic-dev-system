# STORY-003: Generate Story Workspaces from a Blueprint

## Goal

Create a command that reads a structured blueprint file and generates organized story workspaces automatically.

## Why This Matters

The cloud model should be able to create a blueprint and initial user stories. The agentic system should then take that blueprint and create the folders, story files, instructions, test plans, monitoring plans, reports folders, and review bundle folders needed for each story.

## Acceptance Criteria

- Add a command named `agentic generate-stories`.
- The common command works without long flags: `agentic generate-stories`.
- `--project` is optional and defaults to the current working directory.
- `--blueprint` is optional and defaults to `blueprints/blueprint.yaml` inside the project folder.
- If the default blueprint does not exist, the command shows a clear error.
- The command reads a structured YAML blueprint file.
- The command looks for a top-level `stories` list.
- The command creates one story folder per story in the blueprint.
- Each generated story folder includes:
  - `story.md`
  - `status.yaml`
  - `test_plan.yaml`
  - `monitoring_plan.yaml`
  - `instructions/`
  - `reports/`
  - `review_bundle/`
  - `docs/`
  - `improvements/`
- Each story gets standard core agent instruction files:
  - Research Agent
  - Planner Agent
  - Developer Agent
  - Test Agent
  - Docs Agent
  - Security/Quality Agent
  - Local Reviewer Agent
- The generator does not overwrite existing story files.
- Add story sizing guidance:
  - Stories should be narrow enough to be specific.
  - Stories should be large enough to justify the full agent workflow.
- Rename the Docker Compose service from `agentic` to `dev`.
- Update README so Docker commands use `dev`, for example: `docker compose run --rm dev agentic generate-stories`.
- Make `agentic review-bundle` also default to the current folder for `--project`, so normal usage becomes: `agentic review-bundle --story story_003_generate_stories_from_blueprint`.
- Add tests for the story generation logic.
- Update README with usage instructions.

## Not In Scope

- No LLM calls yet.
- No LangGraph yet.
- No Postgres yet.
- No automatic agent execution yet.
- No cloud review integration yet.
- No automatic GitHub PR creation yet.

## Definition of Done

- `pytest` passes.
- `ruff check .` passes.
- `docker compose run --rm dev agentic generate-stories` creates the expected story folders.
- `docker compose run --rm dev agentic review-bundle --story story_003_generate_stories_from_blueprint` creates a review bundle.
