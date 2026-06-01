# STORY-018: Add project status command

## Goal

Create a command that summarizes all story workspaces and shows each story's current workflow state.

## Why This Matters

As the agentic development system grows, the user needs a simple way to see project progress without opening many files manually. The status command should act like a lightweight command-line dashboard.

## Acceptance Criteria

- Add a project-status command.
- project-status defaults --project to the current working directory.
- project-status can show all stories.
- project-status can filter to one story with optional --story.
- project-status reads each story's status.yaml when present.
- project-status detects whether agent_plan.yaml exists.
- project-status detects whether prompt_pack exists.
- project-status detects whether test_layer_result.yaml exists and whether it passed.
- project-status detects whether quality_gate_result.yaml exists and whether it is ready.
- project-status detects whether finalize_story_result.yaml exists and whether it is ready.
- project-status detects whether cloud_review_result.yaml exists and what decision it contains.
- project-status detects whether merge_readiness_result.yaml exists and what status it contains.
- project-status detects whether a support ticket is blocking a story.
- project-status writes reports/project_status_report.md.
- project-status prints a readable summary to the terminal.
- Add tests for story status collection and summary output.
- README documents the status command.

## Not In Scope

- No web dashboard.
- No FastAPI endpoint yet.
- No Postgres persistence yet.
- No LangGraph yet.
- No automatic GitHub API calls.
- No cloud model calls.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- project-status prints a useful summary.
- project-status writes reports/project_status_report.md.
- finalize-story marks this story ready for review.
