# Test Report

## Story

story_049_micro_readiness_story_sizing

## Tests Added Or Updated

- Added `tests/test_micro_readiness.py`.

## Coverage

The tests cover:

- missing story folder errors
- focused story readiness returning `READY_FOR_MICRO`
- acceptance criteria warning and too-large behavior
- missing not-in-scope warning
- missing `agent_plan.yaml` warning
- per-agent estimate output
- result YAML creation
- Markdown report creation
- `--target-chars` override behavior
- CLI safety that does not call local model or cloud review functions
- operation in a temporary project with no real Git repository

## Validation Results

- `docker compose run --rm dev pytest tests/test_micro_readiness.py`: 12 passed.
- `docker compose run --rm dev pytest`: 439 passed.
- `docker compose run --rm dev ruff check .`: passed.
- `docker compose run --rm dev agentic test-layers --story story_049_micro_readiness_story_sizing`: PASSED.

## Model Safety

Tests use local temporary files and monkeypatched CLI functions. No local models,
cloud models, agents, GitHub calls, commits, merges, or deploys are required.
