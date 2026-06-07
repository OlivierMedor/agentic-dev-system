# Developer Report

## Story

story_042_local_model_runtime_adapter

## Summary

Implemented local OpenAI-compatible runtime support for optional local model
servers such as LM Studio and Ollama. The implementation validates local runtime
config, supports a bounded dry run, and supports saving a local model response
from a prompt file without applying code changes.

## Changes

- Added `src/agentic_dev/local_model_runtime.py`.
- Added `agentic local-model validate`.
- Added `agentic local-model dry-run`.
- Added `agentic local-agent run-prompt`.
- Updated `.agentic/agent_runtime.yaml` and the scaffolded default runtime
  config with local model runtime examples and LM Studio/Ollama profiles.
- Updated `.gitignore` for the generated local model dry-run report.
- Added `docs/local_models.md`.
- Updated `README.md` to link local model docs and list the new commands.
- Added Story 042 to `blueprints/blueprint.yaml`.
- Generated the Story 042 workspace from the blueprint.

## Safety Controls

- Local runtime config only accepts `provider: local_openai_compatible`.
- Local model calls use the configured local `base_url` and never call cloud
  models.
- `local-agent run-prompt` writes only the requested output file.
- Model output is not executed.
- Model output is not applied to source files automatically.
- The commands do not commit, push, merge, deploy, call GitHub APIs, or expose
  secret values.
- Local runtime remains opt-in with `enabled: false` in the repository example.
