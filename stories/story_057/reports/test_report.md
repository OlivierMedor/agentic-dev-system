# Test Report

Targeted Docker validation:

- `docker compose run --rm dev pytest tests/test_codex_runtime.py -q`: 18 passed.
- `docker compose run --rm dev pytest tests/test_story_runner.py -q`: 14 passed.

Full Docker validation:

- `docker compose run --rm dev pytest`: 511 passed.
- `docker compose run --rm dev ruff check .`: All checks passed.

Docker Codex smoke checks:

- `docker compose run --rm dev which codex`: `/usr/local/bin/codex`.
- `docker compose run --rm dev codex --version`: `codex-cli 0.139.0`.

Workflow validation:

- `docker compose run --rm dev agentic workflow-run --story story_057 --phase local-finalize --execute`:
  completed; finalize status `ready_for_review`; quality gate status `READY_FOR_REVIEW`.
- `docker compose run --rm dev agentic merge-readiness --story story_057`:
  `REQUEST_CHANGES` because `reports/cloud_review_result.yaml` is intentionally
  absent. Cloud review was not recorded by this story.
- `docker compose run --rm dev agentic artifact-policy`: passed.
- `docker compose run --rm dev agentic public-readiness`: passed.

Coverage added or updated:

- Dockerfile installs the Codex CLI without embedded secrets.
- Compose mounts `CODEX_HOME` as a Docker-managed volume, not a repo path.
- Docs explain no committed credentials and the supported Docker auth setup.
- Runtime config remains disabled by default.
- Artifact policy blocks Codex auth/config state.
- Public readiness blocks Codex auth/config state.
- Existing missing-command behavior remains covered by Story 056 tests.
