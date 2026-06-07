# Test Report

## Story

story_042_local_model_runtime_adapter

## Automated Tests

- `docker compose run --rm dev pytest tests/test_local_model_runtime.py`
  - Result: PASSED
  - Summary: 12 passed in 1.06s.
- `docker compose run --rm dev pytest`
  - Result: PASSED
  - Summary: 365 passed in 8.80s.
- `docker compose run --rm dev ruff check .`
  - Result: PASSED
  - Summary: All checks passed.

## Validation Checks

- `docker compose build`
  - Result: PASSED
- `docker compose run --rm dev agentic artifact-policy`
  - Result: PASSED
- `docker compose run --rm dev agentic public-readiness`
  - Result: PASSED
- `docker compose run --rm dev agentic runtime-config validate`
  - Result: PASSED
- `docker compose run --rm dev agentic local-model validate`
  - Result: PASSED
- `docker compose run --rm dev agentic project-status`
  - Result: PASSED
  - Summary: Project status ran for 42 stories; Story 042 was still in progress
    before finalization because final reports and review evidence were not yet
    complete.
- `docker compose run --rm dev agentic workflow-run --story story_042_local_model_runtime_adapter --phase prepare --execute`
  - Result: PASSED
- `docker compose run --rm dev agentic generate-stories`
  - Result: PASSED
  - Summary: No new files created after Story 042 workspace generation.
- `docker compose run --rm dev agentic workflow-run --story story_042_local_model_runtime_adapter --phase local-finalize --execute`
  - Result: PASSED
  - Summary: Status completed; safety summary confirmed no agents, cloud
    models, GitHub APIs, merge, or deployment ran.
- `docker compose run --rm dev agentic workflow-run --story story_042_local_model_runtime_adapter --phase cloud-review-prep --execute`
  - Result: PASSED
  - Summary: Status completed; safety summary confirmed no agents, cloud
    models, GitHub APIs, merge, or deployment ran.
- `docker compose run --rm dev agentic review-bundle --story story_042_local_model_runtime_adapter`
  - Result: PASSED
  - Summary: Review bundle generated with pytest passed: True and ruff passed:
    True.
- Final `docker compose run --rm dev agentic project-status`
  - Result: PASSED
  - Summary: Story 042 is `READY_FOR_REVIEW`, status `ready_for_review`,
    ready `yes`; workflow-run phase is `cloud-review-prep`, executed `yes`.

## Coverage Added

`tests/test_local_model_runtime.py` verifies:

- Local model config validation passes for a valid config.
- Validation fails for missing `base_url`.
- Validation fails for invalid provider.
- Validation fails for missing `model`.
- Validation fails for non-boolean `enabled`.
- Dry-run behavior uses a fake HTTP client and writes a report.
- `run-prompt` saves the model response to the output file.
- `run-prompt` does not apply code changes.
- CLI `local-model validate` prints a pass result.
- API key headers use the configured environment variable without recording the
  variable name as the secret value.
- README links to `docs/local_models.md`.
- `docs/local_models.md` mentions LM Studio, Ollama, Qwen3-Coder, Devstral,
  Gemma, Docker host access, and safety boundaries.

## Live Model Testing

No live LM Studio or Ollama server was required or called. Unit tests use a fake
HTTP client.
