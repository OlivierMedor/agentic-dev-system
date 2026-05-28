# STORY-006: Generate agent prompt packs for each story

## Goal

Create a command that generates Codex-ready prompt files for each assigned agent in a story.

## Why This Matters

The system should reduce manual prompt writing by creating role-specific prompts from the story, agent plan, project rules, test plan, and monitoring plan.

## Acceptance Criteria

- Add a generate-prompts command.
- The command requires --story.
- The command defaults --project to the current working directory.
- The command creates a prompt_pack folder inside the story folder.
- The command creates one prompt file per assigned agent.
- Each prompt includes the story goal, acceptance criteria, agent responsibility, safety rules, test plan, monitoring plan, and expected output.
- The Test Agent prompt clearly says it should not modify implementation code unless a small fix is required and explained.
- The Developer Agent prompt clearly says it should not write tests.
- The Local Reviewer prompt clearly says it must not approve unless pytest and Ruff pass.

## Not In Scope

- No automatic execution of Codex yet.
- No LangGraph yet.
- No model API calls yet.

## Definition of Done

- pytest passes.
- ruff passes.
- prompt_pack files are generated for all assigned agents.
