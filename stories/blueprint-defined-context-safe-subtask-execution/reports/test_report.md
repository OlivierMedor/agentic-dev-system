# Test Report

## Coverage Added

- Valid sub-task blueprint parsing.
- Legacy blueprint compatibility.
- Duplicate ID, missing dependency, self-dependency, and cycle rejection.
- Deterministic topological ordering and readiness calculation.
- Invalid context budget rejection and output-token reservation.
- Complete required-context assembly and mandatory-section preservation.
- Oversized task rejection before model invocation.
- Structured `cloud_redecomposition_required` state.
- Dependency-aware execution, downstream blocking, handoff persistence, and
  declared dependency input consumption.
- Resume skipping completed tasks and retrying incomplete work.
- Per-task writable-path enforcement and symlink escape regression.
- Story-wide requirement validation.
- CLI/operator dry-run output through `LocalExecutionResult.terminal_summary`.
- Story 060 backward compatibility through the existing local execution tests.

## Validation Performed

- `docker compose run --rm dev pytest` passed with 567 tests.
- `docker compose run --rm dev ruff check .` passed.
- Targeted sub-task and local execution tests passed.
