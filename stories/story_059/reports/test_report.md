# Test Report

## Targeted Docker Pytest

- `docker compose run --rm dev pytest tests/test_codex_runtime.py -q`
  - Passed: `21 passed`
- `docker compose run --rm dev pytest tests/test_runtime_config.py -q`
  - Passed: `20 passed`
- `docker compose run --rm dev pytest tests/test_story_runner.py -q`
  - Passed: `15 passed`

## Full Validation

- `docker compose run --rm dev pytest`
  - Passed: `519 passed`
- `docker compose run --rm dev ruff check .`
  - Passed: `All checks passed!`

## Added Coverage

- Default config stays disabled and keeps the workspace-write runtime shape.
- `danger-full-access` is rejected without
  `docker_isolation_acknowledged: true`.
- `danger-full-access` is accepted only with explicit acknowledgement.
- Acknowledgement is rejected when the runtime is still using
  `workspace-write`.
- Rendered runtime command matches the exact Docker-compatible accepted shape.
- Task file content still flows through stdin with `shell=False`.
- Missing reports still block.
- Nonzero exit still blocks.
- Existing no-merge/no-push/no-deploy/no-PR/no-GitHub-API behavior remains
  covered.

## Docker Write Smoke

- Verified the Codex CLI inside Docker and then ran a disposable smoke project
  using the acknowledged Docker-compatible mode.
- Confirmed `codex_runtime_execution_result.yaml` reached `status: PASSED` and
  the required story report file was created at the expected story path.
- Confirmed `run-story --execute` moved past automatic agent runtime after the
  report existed and only stopped later at normal quality-gate evidence checks.

## Story 059 Finalization Checks

- `docker compose run --rm dev agentic workflow-run --story story_059 --phase local-finalize --execute`
  - Passed overall with `status: completed`
  - `test-layers`: `PASSED`
  - `finalize-story`: `ready_for_review`
  - `review-bundle`: `pytest passed: True`, `ruff passed: True`
- `docker compose run --rm dev agentic merge-readiness --story story_059`
  - Returned `REQUEST_CHANGES`
  - Missing evidence was only `reports/cloud_review_result.yaml`
