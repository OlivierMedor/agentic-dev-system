# Test Report

Story: `story_036_code_tour_feature_map`

## Tests Added

Added `tests/test_code_tour_docs.py`.

The new tests verify:

- `docs/code_tour.md` exists.
- `docs/command_map.md` exists.
- `README.md` links to `docs/code_tour.md`.
- `README.md` links to `docs/command_map.md`.
- `docs/command_map.md` mentions key commands:
  `generate-stories`, `workflow-run`, `review-bundle`, `quality-gate`,
  `project-status`, `next-step`, and `public-readiness`.
- `docs/code_tour.md` mentions `src/agentic_dev`, `stories`, `tests`, `docs`,
  `blueprints`, and `.agentic`.

## Test Results

- `docker compose run --rm dev pytest`: passed, 328 tests.
- `docker compose run --rm dev ruff check .`: passed.

## Coverage Notes

This story changes documentation only. Existing CLI and workflow tests continue
to cover command behavior; the new tests cover the requested documentation
existence, README links, and required command/repository references.
