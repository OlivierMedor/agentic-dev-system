# STORY-050: Micro-Readiness Workflow Integration

## Goal

Integrate micro-readiness into the normal workflow so story sizing guidance is visible in project-status, next-step, and workflow-run prepare.

## Why This Matters

Story 049 added the deterministic micro-readiness checker. The normal workflow should now surface that checker at the points where operators decide whether a story should be split, use micro or slim local prompts, or use a stronger configured agent runtime.

## Acceptance Criteria

- Add Story 050 to blueprints/blueprint.yaml.
- Update workflow-run prepare so dry-run planned steps include prepare-story, micro-readiness, and workflow-preview.
- Update workflow-run prepare execute mode so it runs prepare-story, micro-readiness, and workflow-preview.
- workflow_run_result.yaml records the micro-readiness step result.
- workflow-run safety flags remain false for agent execution, cloud models, GitHub APIs, commits, merges, deployment, destructive commands, and arbitrary commands.
- project-status reads reports/micro_readiness_result.yaml, displays micro_readiness_status and warning count, shows not recorded when missing, and handles malformed YAML gracefully.
- next-step recommends micro-readiness when agent_plan.yaml and prompt_pack exist but reports/micro_readiness_result.yaml is missing.
- next-step continues normal workflow for READY_FOR_MICRO and explains MICRO_READY_WITH_WARNINGS as guidance rather than automatic failure.
- next-step recommends splitting the story or using a stronger configured agent runtime for TOO_LARGE_FOR_MICRO.
- next-step does not recommend automatic merge or deployment and uses configured agent runtime wording rather than Codex-only wording.
- Update README.md and docs/micro_readiness.md for the integrated workflow.
- Add or update tests for workflow-run prepare, project-status, and next-step behavior.

## Not In Scope

- No local model calls.
- No cloud model calls.
- No generated prompt execution.
- No autonomous merge behavior.
- No deployment behavior.
- No GitHub API calls except manual PR creation tooling after local validation.
- No committing generated review_bundle, cloud_review_packet, remote_dev_validation, local_agent_context, or local_agent_drafts artifacts.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 050 generate-stories passes.
- Story 050 workflow-run prepare execute passes.
- Story 050 micro-readiness command passes.
- Story 050 workflow-run local-finalize execute passes.
- Story 050 workflow-run cloud-review-prep execute passes.
- Review bundle is generated for Story 050 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
