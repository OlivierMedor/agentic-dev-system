# STORY-034: Public Launch Prep

## Goal

Prepare the repository for a future public launch with beginner-friendly public docs, launch checklist, architecture explanation, and repository hygiene tests.

## Why This Matters

The project is close to being public-ready, but new visitors need a clear README, system map, launch checklist, and explicit reminders about local-only artifacts before repository visibility changes.

## Acceptance Criteria

- Add Story 034 to blueprints/blueprint.yaml.
- Add docs/system_map.md with simple ASCII diagrams for the blueprint-to-story flow, story workspace structure, agent prompt pack flow, review bundle and quality gate flow, cloud review and merge readiness flow, queue loops, and LangGraph workflow-run phases.
- Add docs/public_launch_checklist.md with required local checks, repository hygiene checks, license reminder, CI check, and manual repository visibility step.
- Update README.md so public visitors quickly understand what the system is, why it exists, how the workflow works, core commands, current status, safety model, and docs links.
- Update docs/golden_path.md if needed.
- Update docs/public_readiness.md if needed.
- Add or update tests verifying the new public docs exist, README links to public docs, the sanitized architecture example exists, and private architecture guidance remains ignored and blocked by policy.
- Do not expose private strategy logic, private prompts, secrets, or local-only operator guidance.
- Do not commit blueprints/agentic-architecture.md.

## Not In Scope

- No new CLI commands.
- No workflow behavior changes.
- No automatic license selection.
- No cloud model calls.
- No GitHub API automation beyond opening the PR if available.
- No automatic merge, deployment, repository visibility change, or approval.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- docker compose build passes.
- Story reports are written for development, testing, and local review.
- Review bundle is generated for Story 034 but generated bundle files are not committed.
