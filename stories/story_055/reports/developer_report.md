# Developer Report

## Summary

Implemented the one-command story runner:

- Added `agentic run-story --story <story-folder-or-slug> [--project <path>] [--execute]`.
- Added `agentic run-next-story [--project <path>] [--execute]`.
- Added `src/agentic_dev/story_runner.py` for story resolution, dry-run planning, safe execute orchestration, required report checks, runtime blockage handling, and run-next selection.
- Dry-run terminal output now visibly includes selected story, resolved project path, execute mode, planned safe steps, safety reminders, output paths, and next action.
- `run-next-story` uses blueprint order/status/dependencies when available and fails clearly instead of falling back to unordered story folders.
- Added regression tests in `tests/test_story_runner.py`.

## Smoke Tests

`docker compose run --rm dev agentic run-story --story story_055`

```text
Story runner for story_055:
Project: /app
Mode: dry-run
Execute mode: off
Status: planned
Planned safe workflow steps:
  - prepare-story: Prepare story, assigning agents and generating prompts only when needed.
  - build-context: Build role-specific context packets only when needed.
  - codex-task-create: Create Codex/local-agent task files only when needed.
  - automatic-agent-runtime: Attempt the configured automatic local runtime if available.
  - verify-required-agent-reports: Stop clearly if required agent reports are missing.
  - local-finalize: Run local finalize after required reports exist.
  - quality-gate: Run the quality gate and stop before merge.
Safety: stopped before merge; no merge, push, force-push, deploy, PR, GitHub API, or cloud model call.
Next action: Review the planned story workflow. Rerun with --execute to run it.
Result written to: /app/stories/story_055/reports/story_runner_result.yaml
Report written to: /app/stories/story_055/reports/story_runner_report.md
```

`docker compose run --rm dev agentic run-story --help`

```text
usage: agentic run-story [-h] [--project PROJECT] --story STORY [--execute]
```

`docker compose run --rm dev agentic run-next-story --help`

```text
usage: agentic run-next-story [-h] [--project PROJECT] [--execute]
```

`docker compose run --rm dev agentic run-next-story`

```text
Error: No runnable story with blueprint order and satisfied dependencies was found. Run a specific story with run-story --story <story-folder-or-slug>.
```

`docker compose run --rm dev agentic run-story --story story_055 --execute`

```text
Status: BLOCKED_MISSING_RUNTIME
Next action: No automatic agent runtime is configured. Enable local_model_runtime.enabled in .agentic/agent_runtime.yaml, or run the generated Codex task files manually and rerun run-story after required reports exist.
```

## Test Results

Targeted:

```text
docker compose run --rm dev pytest tests/test_story_runner.py -q
9 passed in 0.75s
```

Full suite:

```text
docker compose run --rm dev pytest
495 passed in 4.77s
```

Ruff:

```text
docker compose run --rm dev ruff check .
All checks passed!
```

## Known Limitations

- Automatic Codex execution is not implemented; Codex task files are generated for manual Codex handoff.
- Execute mode only attempts automatic agent execution through the configured local model runtime when `local_model_runtime.enabled: true`.
- If no automatic runtime is configured, execute mode stops before finalization with an actionable error.
- `run-next-story` refuses unordered fallback when blueprint ordering exists and no ordered runnable story is eligible.

## Safety Confirmation

The runner does not merge, push, force-push, deploy, open PRs, call GitHub APIs, or call cloud models automatically. It stops before merge and records false safety flags for those actions in `story_runner_result.yaml`.

## Workflow Evidence Cleanup

- Added `test_plan.yaml` using `test_layers_version: 1` and documenting unit,
  integration, mock E2E, live read-only, and remote dev layers for Story 055.
- Added `monitoring_plan.yaml` focused on one-command runner safety and missing
  runtime/report failure modes.
- Added `reports/test_report.md` with the targeted, full-suite, lint, and CLI
  smoke evidence from the implementation validation.
- Added `reports/local_review_report.md` with `READY_FOR_REVIEW` for local
  evidence only. No cloud review decision was recorded or fabricated.

## Final Workflow Command Results

- `docker compose run --rm dev agentic test-layers --story story_055`:
  `Test layer status: PASSED`.
- `docker compose run --rm dev pytest tests/test_story_runner.py -q`:
  `9 passed in 0.75s`.
- `docker compose run --rm dev pytest`: `495 passed in 5.35s`.
- `docker compose run --rm dev ruff check .`: `All checks passed!`.
- `docker compose run --rm dev agentic workflow-run --story story_055 --phase local-finalize --execute`:
  the local command client timed out while the Docker container continued
  running; waiting for the container returned exit code 0. The refreshed
  `workflow_run_result.yaml` has `status: completed`, and all safe steps
  (`test-layers`, `finalize-story`, `review-bundle`, `workflow-preview`) passed.
- `docker compose run --rm dev agentic merge-readiness --story story_055`:
  `Status: REQUEST_CHANGES`, `Ready for human merge decision: False`, and
  `Cloud review decision: None`.
- `docker compose run --rm dev agentic cloud-review-packet --story story_055`:
  packet files created under `stories/story_055/cloud_review_packet`.

## Final Local Gate Status

Local finalization passed. `quality_gate_result.yaml` is `READY_FOR_REVIEW`,
`finalize_story_result.yaml` has `ready_for_review: true`, and
`test_layer_result.yaml` is `PASSED`.

Merge-readiness is blocked only by missing `reports/cloud_review_result.yaml`.
No cloud review decision was recorded during this evidence cleanup.
