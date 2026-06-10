# STORY-049: Micro-Readiness and Story Sizing Guard

## Goal

Add a deterministic micro-readiness check that helps decide whether each assigned agent's responsibility can be summarized in a clear local-model micro prompt.

## Why This Matters

Micro local-agent prompts are most useful when each agent has a focused task. The workflow needs an explicit sizing guard that warns when a story is too broad, too vague, or too large for agent-specific micro-mode assignments.

## Acceptance Criteria

- Add Story 049 to blueprints/blueprint.yaml.
- Add an agentic micro-readiness command with required --story, optional --project, and optional --target-chars defaulting to 2000.
- Validate the story folder, read story.md, agent_plan.yaml when present, and instructions/ when present.
- Estimate whether each assigned core agent can receive a target-sized micro prompt using the required prompt ingredients.
- Write reports/micro_readiness_result.yaml and reports/micro_readiness_report.md, then print a beginner-friendly summary.
- Result statuses include READY_FOR_MICRO, MICRO_READY_WITH_WARNINGS, TOO_LARGE_FOR_MICRO, and NEEDS_REVIEW.
- Heuristics warn or fail for oversized acceptance criteria, vague goals, missing boundaries, missing or incomplete agent plans, oversized agent estimates, broad module touch, and split signals.
- Update docs/micro_readiness.md, docs/story_sizing.md, and README.md with concise operator guidance.
- Add tests for story-folder validation, focused stories, acceptance-criteria sizing, missing boundaries, missing agent plans, per-agent estimates, report outputs, target override, model-call safety, and no real Git repo requirement.

## Not In Scope

- No local model calls.
- No cloud model calls.
- No agent execution.
- No source changes based on model output.
- No automatic commit, push, merge, deploy, or GitHub API calls from the command.
- No replacement for human story sizing judgment.
- No generated review bundle, cloud review packet, remote dev validation, local_agent_context, or local_agent_drafts artifacts committed.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 049 generate-stories passes.
- Story 049 prepare workflow-run passes.
- Story 049 micro-readiness command passes.
- Story 049 local-finalize workflow-run passes.
- Story 049 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 049 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
