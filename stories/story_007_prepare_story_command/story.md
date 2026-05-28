# STORY-007: Add prepare-story command

## Goal

Create a command that prepares a story for agent execution by assigning agents, generating prompt packs, creating a runbook, and updating story preparation status.

## Why This Matters

The system should reduce manual setup before each story. Instead of manually running assign-agents and generate-prompts, one command should prepare the story workspace for agent work.

## Acceptance Criteria

- Add a prepare-story command.
- The command requires --story.
- The command defaults --project to the current working directory.
- The command accepts optional --force.
- The command validates that the story folder exists.
- The command creates or refreshes agent_plan.yaml.
- The command creates or refreshes prompt_pack files.
- The command creates story_runbook.md.
- The command creates reports/prepare_story_report.md.
- The command updates status.yaml to show the story is prepared.
- The command does not execute the agents.
- The command does not run cloud models.
- The command does not create a review bundle.
- The command does not run quality gate automatically.

## Not In Scope

- No automatic Codex execution yet.
- No LangGraph yet.
- No model API calls yet.
- No GitHub PR automation yet.

## Definition of Done

- pytest passes.
- ruff passes.
- prepare-story creates agent_plan.yaml.
- prepare-story creates prompt_pack files.
- prepare-story creates story_runbook.md.
- prepare-story creates reports/prepare_story_report.md.
- prepare-story updates status.yaml safely.
