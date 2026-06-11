# Test Report

## Story

story_051_role_specific_context_builder

## Tests Added Or Updated

- Added `tests/test_role_context.py`.
- Updated artifact-policy tests for `reports/role_context`.
- Updated public-readiness tests for `reports/role_context`.

## Coverage

- Developer context creation.
- All assigned agent context creation.
- Missing story folder error.
- Missing `agent_plan.yaml` error.
- `--force` overwrite behavior.
- No overwrite without `--force`.
- Developer role boundary text.
- Test role boundary text.
- Reviewer evidence inclusion.
- Exclusion of review bundle and cloud review packet content from developer context.
- Result YAML creation.
- False safety flags.
- CLI command defaulting to all agents.
- Artifact-policy blocking generated role context packet files.

## Validation

- Focused Docker pytest passed for role-context, artifact-policy, and public-readiness tests.
- Focused Docker Ruff check passed for touched Python files.

## Safety

The tests use temporary local story folders and do not call models or GitHub APIs.
