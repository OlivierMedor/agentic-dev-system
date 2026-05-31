# E2E Testing

This project separates test layers by the amount of workflow they exercise and whether they touch
external systems.

## Test layers

- Unit tests test small functions, classes, validation rules, or modules in isolation.
- Integration tests test multiple internal pieces together, such as command functions, generated
  files, CLI paths, and validation behavior.
- Mock E2E tests test the full local workflow using fake data, temporary folders, mocks, or local
  doubles. They should not use live APIs, cloud models, browser automation, deployed environments,
  or a real Git repository.
- Live read-only checks test whether outside services still respond. They only read from live
  systems and must not mutate external state.
- Remote dev smoke tests check whether a deployed or remote development environment starts and
  whether basic flows work after deployment.

## Where tests live

Actual project-level tests live under `tests/`. Mock E2E workflow tests live in `tests/e2e/`.
Story-level `test_plan.yaml` files do not contain the tests; they declare whether each test layer
is required, what action was taken or planned, how often the layer runs, and the evidence or reason
for that decision.

Stories that use `test_layers_version: 1` must address:

- `unit_tests`
- `integration_tests`
- `mock_e2e_tests`
- `live_read_only_checks`
- `remote_dev_smoke_tests`

Run test-layer validation with:

```powershell
docker compose run --rm dev agentic test-layers --story <story_folder>
```

## Mock E2E workflow pattern

A mock E2E test should create an isolated project with `tmp_path`, then exercise the local workflow:

1. Initialize the project with `init_project(tmp_path)` or `agentic init --project <tmp_path>`.
2. Write a small `blueprints/blueprint.yaml` with one sample story.
3. Generate story workspaces with `generate_stories(tmp_path)`.
4. Prepare the generated story with `prepare_story(tmp_path, story_slug)`.
5. Create simulated agent reports and local review evidence required by the quality gate.
6. Run `run_test_layers(tmp_path, story_slug)`.
7. Finalize with `finalize_story(tmp_path, story_slug, command_runner=<fake_runner>)`.
8. Assert `stories/<story_slug>/status.yaml` has `ready_for_review: true`.

The fake review-bundle command runner should return passing outputs for `pytest` and
`ruff check .`, and safe local outputs for Git commands. This keeps the test independent from a
real Git repo, live APIs, cloud models, or installed browser tooling while still exercising the
project initialization, blueprint generation, story preparation, test-layer validation, quality
gate, review-bundle generation, and finalization code paths.

The CLI remains the normal operator interface. Direct Python APIs are the safest choice for mock E2E
tests because they can use `tmp_path` and inject deterministic command output without shelling out
to live services.
