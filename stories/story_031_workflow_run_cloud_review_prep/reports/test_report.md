# Test Report

## Story

story_031_workflow_run_cloud_review_prep

## Files changed

- `tests/test_workflow_run.py`
- `tests/test_next_step.py`
- `tests/test_workflow_preview.py`
- `stories/story_031_workflow_run_cloud_review_prep/reports/test_report.md`
- `stories/story_031_workflow_run_cloud_review_prep/reports/test_layer_result.yaml`
- `stories/story_031_workflow_run_cloud_review_prep/reports/test_layer_report.md`

## What I did

- Added workflow-run tests for the `cloud-review-prep` phase.
- Verified dry-run behavior writes `workflow_run_result.yaml` and `workflow_run_report.md` without running safe steps.
- Verified execute mode refuses to run `cloud-review-packet` when `finalize_story_result.yaml` is missing.
- Verified execute mode refuses to run `cloud-review-packet` when `ready_for_review` is not true.
- Verified execute mode runs only `cloud-review-packet` and `workflow-preview` when finalize evidence is ready.
- Verified graph nodes, planned steps, executed steps, and safety flags are recorded.
- Verified cloud-review-prep does not run arbitrary commands or generated prompt files.
- Updated next-step tests to recommend `workflow-run --phase cloud-review-prep --execute` when finalize evidence is ready and the cloud review export is missing.
- Updated the workflow-preview expectation to match the same safe next-step route.

## Test layer coverage

- Unit tests: added and updated for workflow-run cloud-review-prep and next-step integration.
- Integration tests: confirmed through CLI-adjacent command tests and full pytest suite.
- Mock E2E tests: confirmed existing mock E2E workflow test still passes in the full suite.
- Live read-only checks: not applicable because this story must not call live external APIs.
- Remote dev smoke tests: not applicable because this story does not deploy or validate a remote dev environment.

## Validation performed

- `docker compose build` passed.
- `docker compose run --rm dev pytest` passed: 296 tests.
- `docker compose run --rm dev ruff check .` passed.
- `docker compose run --rm dev agentic artifact-policy` passed.
- `docker compose run --rm dev agentic runtime-config validate` passed.
- `docker compose run --rm dev agentic test-layers --story story_031_workflow_run_cloud_review_prep` passed.

## Assumptions

- `ready_for_review: true` in `reports/finalize_story_result.yaml` is the required execution readiness signal for cloud-review-prep.
- The normal safe path after local finalization is now `workflow-run --phase cloud-review-prep --execute`, not direct `cloud-review-packet`.
- Workflow-preview should mirror next-step's safe recommendation for the cloud review prep route.

## Warnings or uncertainty

- I did not modify implementation code.
- I did not call cloud models, GitHub APIs, merge, push, deploy, or commit.
- The story directory was already untracked in this workspace.
