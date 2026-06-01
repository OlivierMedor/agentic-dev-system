# Local Review Report

## Status

READY_FOR_REVIEW

## Files Changed

- `src/agentic_dev/queue_management.py`
- `src/agentic_dev/cli.py`
- `tests/test_queue_management.py`
- `README.md`
- `blueprints/blueprint.yaml`
- `stories/story_020_promote_queue_item_to_story/reports/local_review_report.md`

## What I Did

- Reviewed the queue promotion implementation, CLI wiring, tests, README workflow documentation, blueprint story entry, and Story 020 reports.
- Confirmed `queue promote-to-story` requires `--item`, defaults `--project` to the current working directory, searches improvement, maintenance, and feature queues, blocks pending items by default, and supports `--allow-pending`.
- Confirmed promotion appends a story entry to `blueprints/blueprint.yaml`, chooses the next available `STORY-###`, creates a safe slug, creates a story workspace through existing story generation logic, and writes promotion reports.
- Confirmed the generated story includes acceptance criteria, not-in-scope, definition of done, test plan, and monitoring plan.
- Confirmed promotion records `promoted_story_id` and `promoted_story_slug` back into the queue item and supports post-promotion movement to `closed` or `parked`.
- Confirmed the command is local filesystem work and does not execute the generated story, call cloud models, commit, push, merge, or deploy.

## Validation Performed

- `docker compose run --rm dev pytest` passed: 167 tests.
- `docker compose run --rm dev ruff check .` passed.
- `docker compose run --rm dev agentic artifact-policy` passed.
- `docker compose run --rm dev agentic runtime-config validate` passed.
- `docker compose run --rm dev agentic test-layers --story story_020_promote_queue_item_to_story` passed.
- Created a disposable approved feature queue item in `/app/.tmp/story020_local_review_sample`, promoted it with `queue promote-to-story --close-after-promotion`, and confirmed:
  - `STORY-021` and slug `story_021_local_review_sample_feature` were generated.
  - The blueprint entry was appended.
  - The story workspace and promotion reports were created.
  - The queue item moved from `approved` to `closed`.
  - `promoted_story_id: STORY-021` and `promoted_story_slug: story_021_local_review_sample_feature` were recorded.
- Created a disposable pending feature queue item and confirmed promotion without `--allow-pending` failed with the expected error.
- Removed the disposable `.tmp/story020_local_review_sample` smoke-test project.

## Assumptions

- The existing quality gate definition is the source of truth for required review evidence; it requires developer, test, local review, review bundle, pytest, Ruff, and test-layer evidence.
- Missing docs/security/research/planner reports are not treated as blockers by the current quality gate for this repository.
- The post-promotion project-level `reports/queue_promotion_report.md` being overwritten by the latest promotion is acceptable because the story only requires that a promotion report is written.

## Warnings Or Uncertainty

- I did not commit anything.
- I did not observe internet or cloud API usage in the promotion path.
- The local smoke check used a copied blueprint in a disposable workspace-local sample project and was not retained.
