# STORY-026: Add story next-step advisor

## Goal

Create a command that inspects a story workspace and recommends the next workflow action.

## Why This Matters

The agentic development system now has many commands and review gates. The user needs a simple way to ask "what should I do next for this story?" without manually checking every file. The advisor should inspect story state and recommend the next safe step.

## Acceptance Criteria

- Add a next-step command.
- next-step requires --story.
- next-step defaults --project to the current working directory.
- next-step validates that the story folder exists.
- next-step reads story status, agent plan, prompt pack, reports, review bundle, quality gate result, finalize result, cloud review result, merge readiness result, and remote dev validation result when present.
- next-step recommends prepare-story when agent_plan or prompt_pack is missing.
- next-step recommends running configured agent prompts when prompts exist but required agent reports are missing.
- next-step recommends finalize-story when required reports exist but finalize result is missing or stale.
- next-step recommends cloud-review-packet when finalize-story is ready and no cloud review packet exists.
- next-step recommends record-cloud-review when cloud review packet exists but cloud review result is missing.
- next-step recommends merge-readiness when cloud review result exists but merge readiness result is missing.
- next-step recommends remote-dev-packet when merge readiness exists and remote dev validation is not recorded.
- next-step recommends human PR/CI review when merge readiness and/or remote dev validation indicate readiness.
- next-step explains blocked/request-changes states clearly.
- next-step writes reports/next_step_report.md.
- next-step prints a beginner-friendly recommendation to the terminal.
- Tests verify next-step recommendations for common workflow states.
- README documents the next-step workflow.

## Not In Scope

- No automatic execution of recommended commands.
- No cloud API calls.
- No GitHub API calls.
- No automatic merge.
- No LangGraph yet.
- No web dashboard.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- next-step gives useful recommendations.
- finalize-story marks this story ready for review.
