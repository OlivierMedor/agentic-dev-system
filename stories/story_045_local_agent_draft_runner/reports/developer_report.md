# Developer Report

## Story

story_045_local_agent_draft_runner

## Files Changed

- `blueprints/blueprint.yaml`
- `.gitignore`
- `README.md`
- `docs/local_models.md`
- `docs/local_agent_drafts.md`
- `docs/public_readiness.md`
- `src/agentic_dev/local_model_runtime.py`
- `src/agentic_dev/cli.py`
- `src/agentic_dev/prompt_pack.py`
- `src/agentic_dev/artifact_policy.py`
- `src/agentic_dev/public_readiness.py`
- `tests/test_local_model_runtime.py`
- `tests/test_prompt_pack.py`
- `tests/test_artifact_policy.py`
- `tests/test_public_readiness.py`

## What Changed

Added `agentic local-agent draft`, which resolves a story prompt-pack file for a
supported local-agent role, calls the configured local OpenAI-compatible model
only when `local_model_runtime.enabled` is true, and saves the response as a
draft Markdown file plus metadata YAML.

The command is save-only. It does not apply model output to source files,
execute model output, call cloud models, call GitHub APIs, commit, merge, push,
or deploy.

## Safety

- Draft outputs are written under `stories/<story>/reports/local_agent_drafts/`.
- Draft outputs and metadata are ignored by Git.
- Artifact policy and public-readiness block tracked draft outputs except
  `.gitkeep`.
- Prompt guidance now asks for plain ASCII, no emoji/checkmark symbols, no
  unnecessary nested Markdown fences, and exact requested headings.

## Validation Performed

- `docker compose build`: passed.
- `docker compose run --rm dev pytest`: 405 passed.
- `docker compose run --rm dev ruff check .`: passed.
- `docker compose run --rm dev agentic artifact-policy`: passed.
- `docker compose run --rm dev agentic public-readiness`: passed.
- `docker compose run --rm dev agentic runtime-config validate`: passed.
- `docker compose run --rm dev agentic project-status`: ran successfully.
- `docker compose run --rm dev agentic test-layers --story story_045_local_agent_draft_runner`: passed.

## Assumptions

- `maintenance_agent` uses the local reviewer prompt by default because no
  dedicated maintenance story prompt exists in the current prompt-pack layout.
- `--model-label` is sanitized for filenames; when omitted, the configured model
  name is used.

## Warnings

- Live local model calls were not run. Tests use fake HTTP clients by design.
