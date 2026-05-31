# Test Layers

Story test plans use test layers to make the testing picture explicit before review. The actual
tests live in project-level test folders such as `tests/`; the story `test_plan.yaml` declares
which coverage is required, what action was taken or planned, and what evidence or reason supports
that decision.

Not every story needs a new test in every layer. Every story that uses `test_layers_version: 1`
must still address every layer.

## Layers

- `unit_tests`: Small tests for focused functions, classes, validation rules, or pure logic.
- `integration_tests`: Tests that exercise connected modules, CLI paths, file outputs, or workflow
  behavior together.
- `mock_e2e_tests`: End-to-end style tests that use mocks, fixtures, or local doubles instead of
  real browsers, deployments, or external systems.
- `live_read_only_checks`: Safe checks against live systems that only read data and do not mutate
  external state.
- `remote_dev_smoke_tests`: Basic checks after deploying or running the change in a remote dev
  environment.

## Schema

```yaml
test_layers_version: 1

unit_tests:
  required: true
  action: add_or_update
  frequency: every_commit
  evidence_or_reason: Explain unit test coverage.

integration_tests:
  required: true
  action: confirm_existing
  frequency: every_pull_request
  evidence_or_reason: Explain integration coverage.

mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Explain mock E2E coverage.

live_read_only_checks:
  required: false
  action: not_applicable_with_reason
  frequency: scheduled_or_before_release
  evidence_or_reason: Explain why live checks are not applicable or how they will be scheduled.

remote_dev_smoke_tests:
  required: false
  action: not_applicable_with_reason
  frequency: after_remote_dev_deploy
  evidence_or_reason: Explain why remote smoke tests are not applicable or how they will be scheduled.
```

## Actions

- `add_or_update`: Add new tests or update tests as part of the story.
- `update_existing`: Update existing coverage without adding a new test area.
- `confirm_existing`: Confirm existing tests already cover the story risk.
- `not_applicable_with_reason`: Explain why the layer does not apply.
- `scheduled_later_with_reason`: Explain why the layer is deferred and when it should happen.

## Validation

Run:

```powershell
docker compose run --rm dev agentic test-layers --story story_014_test_layer_support
```

The command writes `stories/<story>/reports/test_layer_result.yaml` and
`stories/<story>/reports/test_layer_report.md`. The quality gate requires
`reports/test_layer_result.yaml` to have `status: PASSED` whenever the file exists, and requires it
when `test_plan.yaml` uses `test_layers_version: 1`.

Each layer must include `required`, `action`, `frequency`, and `evidence_or_reason`. The
`frequency` value must be non-empty text.
