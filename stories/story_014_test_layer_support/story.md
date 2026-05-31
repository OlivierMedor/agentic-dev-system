# STORY-014: Add test layer support

## Goal

Create structured support for unit, integration, mock E2E, live read-only, and remote dev smoke test layers in story test plans and quality gates.

## Why This Matters

Every story should address the full testing picture. A story may add new tests, update existing tests, confirm existing coverage, or explain why a layer is not applicable. The quality gate should be able to verify that the required testing layers were addressed before human/cloud review.

## Acceptance Criteria

- Add a standard test layer schema for story test plans.
- Add an agentic test-layers command.
- test-layers validates that each testing layer is addressed.
- test-layers writes reports/test_layer_result.yaml.
- test-layers writes reports/test_layer_report.md.
- Story test plans support unit_tests, integration_tests, mock_e2e_tests, live_read_only_checks, and remote_dev_smoke_tests.
- Each layer must have required, action, frequency, and evidence_or_reason fields.
- Valid actions include add_or_update, update_existing, confirm_existing, not_applicable_with_reason, scheduled_later_with_reason.
- Update story generation so new stories get the full test layer template.
- Update prompt pack generation so Test Agent prompts explain the test layer requirements.
- Update quality gate so it checks test layer results when a story uses the new test layer schema.
- Update finalize-story so it runs test-layers before quality-gate when applicable.
- Add docs/test_layers.md explaining the testing layers.
- Add tests for the test layer validation logic.
- README is updated with usage instructions.

## Not In Scope

- No Playwright/Cypress/Selenium setup.
- No real live API calls.
- No remote dev environment yet.
- No actual deployment smoke tests yet.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- test-layers passes for story_014_test_layer_support.
- finalize-story marks this story ready for review.
