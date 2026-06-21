# Test Report

## Focused Story 064 Tests

- `tests/test_cloud_application_models.py`
- `tests/test_cloud_application_state_machine.py`
- `tests/test_cloud_application_validation.py`
- `tests/test_cloud_application_service.py`
- `tests/test_cloud_application_cli.py`

Result:

- `25 passed in 3.15s`

## Cloud Queue Regression

- `tests/test_cloud_queue_state_machine.py`
- `tests/test_cloud_queue_service.py`
- `tests/test_cloud_queue_security.py`
- `tests/test_cloud_queue_docs.py`
- `tests/test_cloud_queue_contract.py`
- `tests/test_cloud_queue_cli.py`
- `tests/test_demo_subtasks.py`

Result:

- `207 passed, 1 skipped in 5.97s`

## Cross-Feature Regression

- `tests/test_cloud_review_packet.py`
- `tests/test_cloud_review_result.py`
- `tests/test_review_bundle.py`
- `tests/test_runtime_config.py`
- `tests/test_public_readiness.py`
- `tests/test_artifact_policy.py`

Result:

- `34 passed in 1.51s`

## Full Suite

- `pytest -q -p no:cacheprovider`

Result:

- `749 passed in 13.94s`

## Lint

- `ruff check .`

Result:

- passed

## Repo Checks

- `docker compose run --rm dev agentic generate-stories` - passed twice and was idempotent
- `python -m agentic_dev.cli artifact-policy` - passed
- `python -m agentic_dev.cli runtime-config validate` - passed
- `python -m agentic_dev.cli public-readiness` - passed
