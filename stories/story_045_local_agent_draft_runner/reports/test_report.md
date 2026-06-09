# Test Report

## Story

story_045_local_agent_draft_runner

## Tests Added Or Updated

- Added local-agent draft unit coverage in `tests/test_local_model_runtime.py`.
- Updated prompt-pack tests in `tests/test_prompt_pack.py` for local-agent
  formatting safety guidance.
- Updated artifact-policy tests in `tests/test_artifact_policy.py` to block
  tracked local-agent draft runtime files.
- Updated public-readiness tests in `tests/test_public_readiness.py` to block
  tracked local-agent draft runtime files.

## Coverage

The tests verify:

- Supported agents map to the expected default prompt files.
- Missing story folders produce clear errors.
- Missing prompt files produce clear errors.
- Disabled `local_model_runtime.enabled` refuses model calls.
- Fake HTTP clients can exercise the draft runner without a live model.
- Draft Markdown output is saved.
- Metadata YAML is saved with required safety flags.
- Source files are not edited from model output.
- Model output is not executed.
- Existing draft output is not overwritten without `--force`.
- Artifact policy and public-readiness block tracked local-agent draft outputs.
- README/docs link to `docs/local_agent_drafts.md`.
- `docs/local_agent_drafts.md` mentions Gemma, Devstral, Qwen, LM Studio,
  save-only drafts, and human/cloud review for high-risk logic.

## Validation Results

- Focused test run: 61 passed.
- Full pytest: 405 passed.
- Ruff: passed.
- Story test layers: PASSED.

## Assumptions

- Live LM Studio/Ollama calls are manual-only and not required for automated
  validation.

## Warnings

- The fake HTTP tests prove request/response handling and save-only behavior,
  not model quality.
