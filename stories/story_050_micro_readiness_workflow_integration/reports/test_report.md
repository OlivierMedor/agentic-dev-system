# Test Report

## Story

story_050_micro_readiness_workflow_integration

## Tests Added Or Updated

- Updated workflow-run tests for prepare dry-run planning, execute sequencing,
  and micro-readiness step result recording.
- Added project-status tests for present, missing, and malformed
  `micro_readiness_result.yaml`.
- Added next-step tests for missing micro-readiness, `READY_FOR_MICRO`,
  `MICRO_READY_WITH_WARNINGS`, and `TOO_LARGE_FOR_MICRO`.

## Targeted Test Run

Command:

```powershell
docker compose run --rm dev pytest tests/test_workflow_run.py tests/test_project_status.py tests/test_next_step.py
```

Result:

```text
71 passed
```

## Full Test Run

Command:

```powershell
docker compose run --rm dev pytest
```

Result:

```text
447 passed
```

## Story 050 Validation

```text
docker compose run --rm dev agentic generate-stories
Passed.

docker compose run --rm dev agentic workflow-run --story story_050_micro_readiness_workflow_integration --phase prepare --execute
Passed.

docker compose run --rm dev agentic micro-readiness --story story_050_micro_readiness_workflow_integration
MICRO_READY_WITH_WARNINGS, 2 warnings, 0 failed checks.

docker compose run --rm dev agentic workflow-run --story story_050_micro_readiness_workflow_integration --phase local-finalize --execute
Passed with extended timeout because Docker git diff was slow on the mounted checkout.

docker compose run --rm dev agentic workflow-run --story story_050_micro_readiness_workflow_integration --phase cloud-review-prep --execute
Passed.

docker compose run --rm dev agentic review-bundle --story story_050_micro_readiness_workflow_integration
Passed; pytest passed and ruff passed in the generated handoff.
```

## Model Safety

The tests use deterministic local files and fake workflow step runners. They do
not require real local models or cloud models.
