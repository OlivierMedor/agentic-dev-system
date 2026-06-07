# Test Report

Story: story_043_local_model_scorecard

## Coverage Added

- `tests/test_local_model_scorecard.py`
- Updated artifact-policy tests for scorecard result blocking.
- Updated public-readiness tests for scorecard result blocking.

## Focused Validation

Command:

```powershell
docker compose run --rm dev pytest tests/test_local_model_scorecard.py tests/test_artifact_policy.py tests/test_public_readiness.py
```

Result: PASS, 36 tests passed.

Command:

```powershell
docker compose run --rm dev ruff check .
```

Result: PASS.

## Notes

Scorecard model calls are tested with a fake HTTP client. No test requires a live LM Studio or Ollama server.

