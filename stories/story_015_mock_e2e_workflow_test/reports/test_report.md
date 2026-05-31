# Test Report

## Story

story_015_mock_e2e_workflow_test

## Test work completed

- Added `tests/e2e/test_agentic_workflow.py`.
- The test uses `tmp_path` to create a temporary project folder.
- The test initializes the temporary project with the existing scaffolding logic.
- The test writes a sample `blueprints/blueprint.yaml`.
- The test generates a story workspace from the blueprint.
- The test prepares the generated story and verifies `agent_plan.yaml` and prompt pack files.
- The test creates simulated developer, test, local review, and review bundle evidence.
- The test runs test layer validation for the generated story.
- The test finalizes the generated story with a fake review bundle command runner.
- The test verifies both `status.yaml` and `finalize_story_result.yaml` have
  `ready_for_review: true`.

## External dependency checks

- No real Git repository is required.
- No live APIs are called.
- No cloud models are called.
- No browser automation is used.
- No Docker command is run inside the test.

## Validation

- `docker compose run --rm dev pytest`
  - Passed: 112 tests passed.
- `docker compose run --rm dev ruff check .`
  - Passed: All checks passed.
- `docker compose run --rm dev agentic test-layers --story story_015_mock_e2e_workflow_test`
  - Passed: Test layer status PASSED.
