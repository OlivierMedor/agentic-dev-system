# STORY-004: Add automatic agent assignment

## Goal

Create a command that assigns the correct core agents to a story workspace.

## Why This Matters

Agent assignment should be consistent and based on the story instructions and project rules.

## Acceptance Criteria

- Add an agent assignment command.
- Create an agent_plan.yaml file inside the story folder.
- Include all core agents by default.
- Add specialist agents later based on story content.

## Not In Scope

- No LangGraph execution yet.
- No model-based agent selection yet.

## Definition of Done

- pytest passes.
- ruff passes.
- agent_plan.yaml is created for the target story.
