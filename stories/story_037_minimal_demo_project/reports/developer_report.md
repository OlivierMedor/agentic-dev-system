# Developer Report

Story: `story_037_minimal_demo_project`

## Summary

Implemented the minimal public demo project and walkthrough.

Changed files:

- Added `docs/demo_walkthrough.md` with the requested demo flow, safe commands,
  workflow mapping, and guidance not to fake completed agent reports.
- Added `examples/minimal_project/` with a tiny task tracker CLI blueprint,
  public-safe `.agentic` config, README, and demo-local ignore rules.
- Updated `README.md` with a concise "Try The Minimal Demo" section linking to
  the walkthrough.
- Added Story 037 to `blueprints/blueprint.yaml`.

## Scope Notes

- No CLI behavior was added or changed.
- No cloud models, real APIs, databases, wallets, deployment, secrets, `.env`
  files, or private strategy logic were added.
- The demo project is intentionally limited to blueprint/config/docs files. It
  does not include a fake completed generated story workspace.
- Generated review bundles, cloud review packets, remote dev validation files,
  support queue runtime tickets, and feature scan runtime files remain excluded
  from the intended commit.

## Validation Evidence

- `docker compose build`: passed.
- `docker compose run --rm dev pytest`: passed, 333 tests.
- `docker compose run --rm dev ruff check .`: passed.
- `docker compose run --rm dev agentic artifact-policy`: passed.
- `docker compose run --rm dev agentic public-readiness`: passed.
- `docker compose run --rm dev agentic runtime-config validate`: passed.
- `docker compose run --rm dev agentic project-status`: passed before Story 037
  workspace generation and reported 36 stories.
