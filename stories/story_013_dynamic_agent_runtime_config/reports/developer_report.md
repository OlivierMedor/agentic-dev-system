# Developer Report

## Files changed

- `.agentic/agent_runtime.yaml`
- `README.md`
- `src/agentic_dev/cli.py`
- `src/agentic_dev/prompt_pack.py`
- `src/agentic_dev/runtime_config.py`
- `src/agentic_dev/scaffolding.py`

## What you did

- Added `src/agentic_dev/runtime_config.py` with the default runtime config content, YAML loading, readable show output, and validation for required agents, provider types, approval modes, fallback providers, and risky command approval coverage.
- Added `agentic runtime-config show` and `agentic runtime-config validate` to the CLI.
- Updated project scaffolding so initialized projects get `.agentic/agent_runtime.yaml` by default and the starter README mentions runtime config.
- Updated prompt-pack generation to include the runtime config content when present and a per-agent runtime expectation summary for provider, model, approval mode, and fallback provider.
- Added the repo-level `.agentic/agent_runtime.yaml` using the requested default structure.
- Updated `README.md` to document how runtime config works and how to inspect and validate it.

## Validation performed

- `python -m pytest` with `PYTHONPATH=src`: passed, `82 passed`.
- `docker compose run --rm dev ruff check .`: passed.
- `python` entrypoint invocation of `agentic artifact-policy --project .`: passed.
- `python` entrypoint invocation of `agentic runtime-config validate --project .`: passed.
- `python` entrypoint invocation of `agentic runtime-config show --project .`: printed the runtime config as expected.
- Ran a temporary prompt-pack smoke test and confirmed generated prompts include:
  - `## Runtime Config`
  - provider expectation
  - model expectation
  - approval mode expectation
  - fallback provider expectation

## Assumptions

- `fallback_provider` may be either another known provider type or `human_owner`, because the requested default config uses `human_owner` for `cloud_reviewer`.
- Validation is intended to enforce the required risky-command coverage and the current `cloud_reviewer` provider constraint, not to implement actual command-policy enforcement yet.

## Warnings or uncertainty

- `ruff` was not available as a local Python module or shell binary in this environment, so lint validation was completed through the documented Docker Compose path instead.
- There was a pre-existing modification in `blueprints/blueprint.yaml`; it was left untouched.
