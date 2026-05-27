# STORY-004: Add Automatic Agent Assignment

## Goal

Create a command that assigns the correct core agents to a story workspace and writes an `agent_plan.yaml` file.

## Why This Matters

Each user story needs a clear team of agents before work begins.

The system should not rely on memory or a chat conversation to know who is responsible for:

- research
- planning
- development
- testing
- documentation
- security and quality review
- local review

The `agent_plan.yaml` file becomes the story's execution map.

## Acceptance Criteria

- Add a command named `agentic assign-agents`.
- The command accepts `--story`.
- The command accepts optional `--project`, defaulting to the current working directory.
- The command accepts optional `--force`, defaulting to false.
- The common command works:

  `agentic assign-agents --story story_004_agent_assignment`

- The command validates that the story folder exists.
- The command creates:

  `stories/<story>/agent_plan.yaml`

- Every story gets the core agent team:
  - Research Agent
  - Planner Agent
  - Developer Agent
  - Test Agent
  - Docs Agent
  - Security/Quality Agent
  - Local Reviewer Agent

- The generated `agent_plan.yaml` includes:
  - story folder name
  - assigned agents
  - execution order
  - each agent's responsibility
  - each agent's instruction file
  - each agent's expected report output
  - status: pending_execution

- The command should not overwrite an existing `agent_plan.yaml` unless `--force` is used.
- If required core instruction files are missing, the command should create them using the standard core agent instructions.
- Add tests for the agent assignment logic.
- Update README with usage instructions.

## Not In Scope

- No actual agent execution yet.
- No LangGraph yet.
- No model-based agent selection yet.
- No specialist-agent keyword routing yet.
- No cloud review integration yet.

## Definition of Done

- `pytest` passes.
- `ruff check .` passes.
- `docker compose run --rm dev agentic assign-agents --story story_004_agent_assignment` creates `agent_plan.yaml`.
- The generated `agent_plan.yaml` clearly explains which agents are assigned and what each one does.
- `docker compose run --rm dev agentic review-bundle --story story_004_agent_assignment` creates a review bundle.
