# Test Report

Validation completed for Story 063 and the adjacent workflow regressions.

Results:

- Full pytest: `692 passed, 5 skipped`
- Focused cloud queue suite: `105 passed`
- Workflow preview/run suites: `37 passed`
- Feature scan regression: `1 passed`
- Docker-backed Ruff: `All checks passed`
- Read-only CLI checks:
  - `artifact-policy`
  - `runtime-config validate`
  - `public-readiness`
  - all passed
- Story generator idempotency: run twice, both completed without changing the intended workspace state

Relevant focused coverage includes:

- queue state-machine transitions
- archive security and traversal rejection
- redaction coverage
- approval checksum locking
- batch export and import isolation
- CLI end-to-end behavior
- provider-neutral contract tests
- hidden-Unicode hygiene

