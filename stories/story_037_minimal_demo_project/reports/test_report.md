# Test Report

Story: `story_037_minimal_demo_project`

## Tests Added

Added `tests/test_demo_walkthrough.py`.

The new tests verify:

- `docs/demo_walkthrough.md` exists.
- `README.md` links to `docs/demo_walkthrough.md`.
- `examples/minimal_project/README.md` exists.
- `examples/minimal_project/blueprints/blueprint.yaml` exists.
- The demo blueprint contains a non-empty `stories` list.
- The demo blueprint describes building a simple task tracker CLI using mock
  data.
- `examples/minimal_project/` contains no `.env` or `.env.*` files.
- The walkthrough states that cloud models, secrets, and deployment are not
  required.

## Test Results

- First `docker compose run --rm dev pytest`: failed because the new test looked
  for one exact wording variant while the walkthrough used equivalent wording.
- Updated the walkthrough to state explicitly: "The demo does not require cloud
  models, secrets, or deployment."
- Final `docker compose run --rm dev pytest`: passed, 333 tests.
- `docker compose run --rm dev ruff check .`: passed.

## Coverage Notes

This story adds documentation and a sample project only. Existing CLI and
workflow tests continue to cover command behavior; the new tests cover the
requested demo files, README link, blueprint structure, and safety language.
