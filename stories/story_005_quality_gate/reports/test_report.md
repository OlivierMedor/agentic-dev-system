# Test Report

## Tests added

- Added `tests/test_quality_gate.py`.
- Verified `quality-gate` creates `quality_gate_result.yaml`.
- Verified `quality-gate` creates `quality_gate_report.md`.
- Verified a complete story with passing pytest output, passing Ruff output, `agent_plan.yaml`, required reports, and `READY_FOR_REVIEW` local review returns `READY_FOR_REVIEW`.
- Verified a missing story folder raises a clear `FileNotFoundError`.
- Verified missing `agent_plan.yaml` returns `REQUEST_CHANGES`.
- Verified missing required report returns `REQUEST_CHANGES`.
- Verified failing pytest output returns `REQUEST_CHANGES`.
- Verified failing Ruff output returns `REQUEST_CHANGES`.
- Verified local review without `READY_FOR_REVIEW` returns `REQUEST_CHANGES`.
- Verified failed checks are listed in the returned result, YAML result, and Markdown report.

## pytest result

`docker compose run --rm dev pytest`

Result: passed, 30 tests.

## ruff result

`docker compose run --rm dev ruff check .`

Result: passed.

## Fixes made

- No implementation fixes were required.

## Warnings or uncertainty

- The tests exercise the quality gate logic with `tmp_path` fixtures and do not depend on a real Git repository.
