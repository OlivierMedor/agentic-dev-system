# Test Report

## Story

story_046_local_agent_empty_response_guard

## Tests Added Or Updated

- `tests/test_local_model_runtime.py`
- `tests/test_artifact_policy.py`
- `tests/test_public_readiness.py`

## Coverage

The tests verify:

- Empty local-agent responses fail.
- Whitespace-only local-agent responses fail.
- Non-empty responses still succeed.
- `message.content` list text parts are extracted correctly.
- `choices[0].text` is extracted correctly.
- Top-level `output_text` is extracted correctly.
- Hidden reasoning-only content is ignored as final output.
- Raw response JSON is saved for local-agent draft and run-prompt.
- Draft metadata records `response_character_count`, prompt count, raw response
  path, finish reason, and safety flags.
- Draft metadata does not use `draft_saved` when final content is empty.
- `run-prompt` does not silently write an empty successful output.
- Commands still do not edit source files or execute model output.
- Artifact policy and public-readiness block raw response JSON and local-agent
  draft runtime files.
- Docs explain empty-response failures and raw response debugging.

## Validation Results

- Focused pytest: 62 passed.
- Full pytest: 414 passed.
- Ruff: passed.
- Artifact policy: passed.
- Public readiness: passed.
- Runtime config validate: passed.

## Assumptions

- Fake HTTP clients are sufficient for automated response-shape coverage.

## Warnings

- No live local model call was required or run for the test suite.
