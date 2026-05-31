# STORY-015: Add mock E2E workflow test

## Goal

Create a project-level mock end-to-end test that verifies the core agentic workflow from project initialization through story finalization.

## Why This Matters

The system should prove that the full local workflow works, not only individual commands. A mock E2E test gives us confidence that init, blueprint story generation, story preparation, test-layer validation, and finalization work together safely without live services.

## Acceptance Criteria

- Add tests/e2e/test_agentic_workflow.py.
- The E2E test uses a temporary project folder.
- The E2E test initializes the project.
- The E2E test creates a blueprint with a sample story.
- The E2E test generates story workspaces.
- The E2E test prepares the generated story.
- The E2E test creates simulated required reports and review evidence.
- The E2E test runs test layer validation.
- The E2E test finalizes the story.
- The E2E test confirms status.yaml is ready_for_review true.
- The E2E test does not use live APIs.
- The E2E test does not call cloud models.
- The E2E test does not require a real Git repo.
- Docs explain the difference between unit, integration, mock E2E, live checks, and smoke tests.

## Not In Scope

- No Playwright, Cypress, Selenium, or browser testing.
- No live API calls.
- No remote dev deployment.
- No production smoke tests.
- No LangGraph yet.
- No automatic Codex execution.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- mock E2E test passes.
- finalize-story marks this story ready for review.
