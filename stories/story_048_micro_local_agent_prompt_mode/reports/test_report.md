# Test Report

## Story

story_048_micro_local_agent_prompt_mode

## Tests Added Or Updated

- Updated `tests/test_local_model_runtime.py` to cover `--prompt-mode micro`
  CLI acceptance.
- Added micro context packet tests for required content, metadata fields,
  excluded runtime/review artifacts, and short prompt size.
- Added a comparison test proving micro context is smaller than slim context for
  the same story fixture.
- Added a micro empty visible response test where `reasoning_content` is
  populated but `message.content` is empty.
- Kept existing coverage for full mode, slim mode, custom prompt-file mode,
  empty response failure, and non-empty `finish_reason: length` warning saves.
- Updated docs wording tests for micro mode.

## Results

- Focused Docker test run passed:
  `docker compose run --rm dev pytest tests/test_local_model_runtime.py`
  reported 45 passed.
- Focused Ruff run passed:
  `docker compose run --rm dev ruff check src/agentic_dev/local_model_runtime.py tests/test_local_model_runtime.py`.
- Full Docker test run passed:
  `docker compose run --rm dev pytest` reported 427 passed.
- Full Ruff run passed:
  `docker compose run --rm dev ruff check .`.
- Artifact policy, public readiness, runtime config validation, and project
  status checks passed or completed.
- Story 048 local-finalize passed with `ready_for_review: true`.

## Notes

Tests use fake local model HTTP clients. No live local model server, cloud model,
GitHub API, source-file application, command execution from model output,
commit, push, merge, or deploy was used.
