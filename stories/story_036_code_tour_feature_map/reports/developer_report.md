# Developer Report

Story: `story_036_code_tour_feature_map`

## Summary

Implemented the documentation-only scope for Story 036.

Changed files:

- Added `docs/code_tour.md` with a beginner-friendly repository tour, required
  analogies, and the requested ASCII command-to-tests flow.
- Added `docs/command_map.md` with command mappings to `src/agentic_dev/cli.py`,
  core modules, tests, and best-known related story workspaces.
- Updated `README.md` with a concise "Learn The Codebase" section and public
  docs links.
- Updated `docs/system_map.md` with a short pointer to the new docs.
- Added Story 036 to `blueprints/blueprint.yaml`.

## Scope Notes

- No CLI behavior was added or changed.
- No private operator guidance, private prompts, secrets, or generated runtime
  artifacts were copied into docs.
- `blueprints/agentic-architecture.md` remains local-only and untracked.

## Pre-Finalize Validation Evidence

- `docker compose build`: passed.
- `docker compose run --rm dev pytest`: passed, 328 tests.
- `docker compose run --rm dev ruff check .`: passed.
- `docker compose run --rm dev agentic artifact-policy`: passed.
- `docker compose run --rm dev agentic public-readiness`: passed.
- `docker compose run --rm dev agentic runtime-config validate`: passed.
- `docker compose run --rm dev agentic project-status`: passed and reported 36
  stories.
