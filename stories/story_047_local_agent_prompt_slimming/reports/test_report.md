# Test Report

## Story

story_047_local_agent_prompt_slimming

## Tests Added Or Updated

- Updated `tests/test_local_model_runtime.py` for slim default prompt mode,
  explicit full mode, custom prompt-file mode, context packet creation, context
  content and exclusions, metadata fields, raw response saving, truncation
  warning status, empty length failure status, CLI prompt-mode wiring, docs
  links, and safety boundaries.
- Updated `tests/test_artifact_policy.py` to block local-agent context packets
  and raw response artifacts while allowing `.gitkeep`.
- Updated `tests/test_public_readiness.py` to block local-agent context packets
  while allowing `.gitkeep`.

## Results

- Focused Docker test run passed: 69 tests.
- Full Docker test run passed: 421 tests.
- Ruff passed.
- Artifact policy passed.
- Public readiness passed.
- Runtime config validation passed.
- Story 047 test-layer validation passed.

## Notes

Tests use fake local model HTTP clients. No live local model server, cloud model,
GitHub API, source-file application, command execution from model output,
commit, push, merge, or deploy was used.
