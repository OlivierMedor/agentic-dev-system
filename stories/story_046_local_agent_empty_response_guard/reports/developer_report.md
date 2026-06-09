# Developer Report

## Story

story_046_local_agent_empty_response_guard

## Files Changed

- `.gitignore`
- `blueprints/blueprint.yaml`
- `docs/local_agent_drafts.md`
- `docs/local_models.md`
- `docs/public_readiness.md`
- `src/agentic_dev/local_model_runtime.py`
- `src/agentic_dev/cli.py`
- `src/agentic_dev/artifact_policy.py`
- `src/agentic_dev/public_readiness.py`
- `tests/test_local_model_runtime.py`
- `tests/test_artifact_policy.py`
- `tests/test_public_readiness.py`

## What Changed

Local-agent `draft` and `run-prompt` now save raw response JSON and reject empty
or whitespace-only final content. Draft failures write metadata with
`status: empty_model_response`, debug counts, finish reason, raw response path,
and unchanged safety flags.

Response extraction now supports:

- `choices[0].message.content` as a string.
- `choices[0].message.content` as a list of text parts.
- `choices[0].text`.
- Top-level `output_text`.

Hidden/internal reasoning-only responses are not treated as final output and
therefore fail as empty local-agent responses.

## Safety

- Model output is still saved only.
- No source files are edited from model output.
- No model output is executed.
- No cloud models or GitHub APIs are called.
- No commit, push, merge, or deploy actions are performed by the local-agent
  commands.
- Raw response JSON files are ignored and blocked from tracking.

## Validation Performed

- `docker compose build`: passed.
- `docker compose run --rm dev pytest`: 414 passed.
- `docker compose run --rm dev ruff check .`: passed.
- `docker compose run --rm dev agentic artifact-policy`: passed.
- `docker compose run --rm dev agentic public-readiness`: passed.
- `docker compose run --rm dev agentic runtime-config validate`: passed.
- `docker compose run --rm dev agentic project-status`: ran successfully.

## Assumptions

- Live LM Studio/Ollama behavior is covered by saved raw response artifacts and
  manual inspection, not live automated tests.

## Warnings

- The local model configured in `.agentic/agent_runtime.yaml` is user-local and
  was not changed or committed.
