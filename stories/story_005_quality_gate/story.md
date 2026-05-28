# STORY-005: Add Quality Gate Command

## Goal

Create a command that checks whether a story is ready for human/cloud review.

## Why This Matters

A story should not move forward just because code was written.

Before a human or strong cloud model reviews a story, the system should check that the basic evidence exists:

- the story exists
- agent assignment exists
- required reports exist
- review bundle exists
- tests passed
- Ruff passed
- local reviewer approved or requested changes

The quality gate becomes the system's first formal approval checkpoint.

## Acceptance Criteria

- Add a command named `agentic quality-gate`.
- The command accepts `--story`.
- The command accepts optional `--project`, defaulting to the current working directory.
- The common command works:

  `agentic quality-gate --story story_005_quality_gate`

- The command validates that the story folder exists.
- The command checks for required story files:
  - story.md
  - status.yaml
  - test_plan.yaml
  - monitoring_plan.yaml
- The command checks for:
  - agent_plan.yaml
  - reports/developer_report.md
  - reports/test_report.md
  - reports/local_review_report.md
  - review_bundle/handoff.md
  - review_bundle/pytest_output.txt
  - review_bundle/ruff_output.txt
- The command detects whether pytest passed.
- The command detects whether Ruff passed.
- The command detects whether the local review says READY_FOR_REVIEW.
- The command writes:
  - reports/quality_gate_result.yaml
  - reports/quality_gate_report.md
- The result should be one of:
  - READY_FOR_REVIEW
  - REQUEST_CHANGES
- The command should explain every failed check clearly.
- Add tests for the quality gate logic.
- Update README with usage instructions.

## Not In Scope

- No actual agent execution yet.
- No LangGraph yet.
- No Postgres yet.
- No remote dev validation bundle yet.
- No production release bundle yet.
- No Maintenance Monitor Agent yet.
- No automatic GitHub PR creation yet.

## Definition of Done

- `pytest` passes.
- `ruff check .` passes.
- `docker compose run --rm dev agentic quality-gate --story story_005_quality_gate` creates the quality gate result files.
- The quality gate explains why a story is READY_FOR_REVIEW or REQUEST_CHANGES.
- `docker compose run --rm dev agentic review-bundle --story story_005_quality_gate` creates a review bundle.
