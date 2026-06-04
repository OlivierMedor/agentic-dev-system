# Test Report

## Files changed

- `tests/test_workflow_preview.py`
- `stories/story_027_langgraph_workflow_preview/reports/test_report.md`
- `stories/story_027_langgraph_workflow_preview/reports/test_layer_result.yaml`
- `stories/story_027_langgraph_workflow_preview/reports/test_layer_report.md`
- `stories/story_027_langgraph_workflow_preview/reports/workflow_preview_result.yaml`
- `stories/story_027_langgraph_workflow_preview/reports/workflow_preview_report.md`

## What I did

Added independent tests for the LangGraph workflow preview command. The tests cover graph
construction, missing story validation, report generation, recorded graph nodes, preview-only safety
flags, next-route recommendations, CLI defaults, no Git repository requirement, and protection
against accidental shell or network-style execution.

The route tests verify:

- Missing `agent_plan.yaml` recommends `prepare-story`.
- Missing `prompt_pack/` recommends `prepare-story`.
- Existing prompts with missing agent reports recommend the configured agent runtime.
- Ready finalize evidence without a cloud review export recommends `cloud-review-packet`.
- A later ready state does not recommend automatic merge or deployment.

## Validation performed

- `docker compose build` passed.
- `docker compose run --rm dev pytest` passed: 269 tests.
- `docker compose run --rm dev ruff check .` passed.
- `docker compose run --rm dev agentic artifact-policy` passed.
- `docker compose run --rm dev agentic runtime-config validate` passed.
- `docker compose run --rm dev agentic test-layers --story story_027_langgraph_workflow_preview` passed.
- `docker compose run --rm dev agentic workflow-preview --story story_027_langgraph_workflow_preview` passed and wrote the workflow preview result and report files.

## Test layers

- Unit tests: added `tests/test_workflow_preview.py`.
- Integration tests: confirmed through CLI coverage in the new test file and the full pytest suite.
- Mock E2E tests: confirmed existing `tests/e2e/test_agentic_workflow.py` passed in the full suite.
- Live read-only checks: not applicable because this story does not call live external APIs.
- Remote dev smoke tests: not applicable because this story does not deploy to a remote dev environment.

## Assumptions

- The implementation is intentionally preview-only and should not invoke agent runtimes, cloud model
  calls, GitHub APIs, merge, or deployment actions.
- The workflow preview may reuse next-step recommendation wording as long as the preview output
  records its own LangGraph route and safety flags.

## Warnings or uncertainty

- The tests do not inspect LangGraph internals beyond confirming the compiled graph exposes the
  expected named nodes and can be invoked through the public graph API.
- I did not modify implementation code.
