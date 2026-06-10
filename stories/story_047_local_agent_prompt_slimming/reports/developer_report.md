# Developer Report

## Story

story_047_local_agent_prompt_slimming

## Summary

Implemented slim local-agent draft prompts and truncation guard behavior for
local models.

## Changes

- Added `--prompt-mode full|slim` to `agentic local-agent draft`, defaulting to
  `slim`.
- Preserved full prompt-pack behavior with `--prompt-mode full`.
- Added custom prompt metadata behavior when `--prompt-file` is provided.
- Added slim context packet generation under
  `stories/<story>/reports/local_agent_context/`.
- Added metadata fields for prompt mode, context packet path/size, source files,
  warnings, finish reason, and safety flags.
- Added `finish_reason: length` handling so non-empty drafts are saved with a
  truncation warning and empty visible content still fails as
  `empty_model_response`.
- Updated artifact-policy, public-readiness, `.gitignore`, README, and local
  model docs for context packets and raw response artifacts.

## Safety

The implementation keeps local model output save-only. It does not apply local
model output to source files, execute model output, call cloud models, call
GitHub APIs, commit, push, merge, or deploy.

## Validation

- `docker compose build` passed.
- `docker compose run --rm dev pytest` passed with 421 tests.
- `docker compose run --rm dev ruff check .` passed.
- `docker compose run --rm dev agentic artifact-policy` passed.
- `docker compose run --rm dev agentic public-readiness` passed.
- `docker compose run --rm dev agentic runtime-config validate` passed.
- `docker compose run --rm dev agentic project-status` ran successfully.
- Story 047 `workflow-run --phase prepare --execute` passed.
- Story 047 `test-layers` passed during local-finalize.
