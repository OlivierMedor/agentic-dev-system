# Developer Report

## Story

story_028_langgraph_safe_workflow_runner

## Files changed

- `src/agentic_dev/workflow_run.py`
- `src/agentic_dev/cli.py`
- `README.md`
- `docs/langgraph_workflow.md`
- `stories/story_028_langgraph_safe_workflow_runner/reports/workflow_run_result.yaml`
- `stories/story_028_langgraph_safe_workflow_runner/reports/workflow_run_report.md`
- `stories/story_028_langgraph_safe_workflow_runner/reports/developer_report.md`

## What I did

- Added a LangGraph `workflow-run` implementation with these graph nodes:
  `collect_story_state`, `plan_safe_steps`, `run_or_skip_safe_steps`, and
  `write_workflow_run_report`.
- Added `agentic workflow-run --story <story>` with optional `--project`, optional
  `--phase local-finalize`, and explicit `--execute`.
- Made dry-run the default. Dry-run writes the plan and safety flags without running safe steps.
- Implemented the `local-finalize` safe step sequence:
  `test-layers`, `finalize-story`, `review-bundle`, and `workflow-preview`.
- Kept execution allowlisted and hardcoded through existing local Python functions.
- Recorded graph nodes visited, planned steps, executed steps, step results, execution mode, status,
  next action, and explicit safety flags in YAML and Markdown reports.
- Documented the runner in README and clarified `workflow-preview` versus `workflow-run` in
  `docs/langgraph_workflow.md`.

## Validation performed

- `docker compose run --rm dev ruff check .` passed.
- `docker compose run --rm dev pytest` passed: 269 tests.
- `docker compose run --rm dev agentic artifact-policy` passed.
- `docker compose run --rm dev agentic runtime-config validate` passed.
- `docker compose run --rm dev agentic workflow-run --story story_028_langgraph_safe_workflow_runner`
  passed and wrote dry-run workflow reports.
- Programmatic execute-mode validation with an injected fake step runner passed and confirmed the
  safe sequence:
  `test-layers`, `finalize-story`, `review-bundle`, `workflow-preview`.

## Assumptions

- The Test Agent will add or update tests for dry-run behavior, execute behavior, safe command
  sequence, and safety flags.
- The safe runner should call existing local Python command functions rather than executing
  subprocess commands from user input.
- A failed local gate should be recorded as a failed step result while still producing the workflow
  run report.

## Warnings or uncertainty

- I did not write tests because the story explicitly says the Developer Agent must not write tests.
- I did not run real `workflow-run --execute` against this story because that would invoke the full
  local finalization path before independent Test Agent and Local Reviewer reports exist. That would
  likely mark the story `request_changes` instead of ready for review.
- `blueprints/blueprint.yaml` was already modified before this work and was not changed by this
  implementation.
