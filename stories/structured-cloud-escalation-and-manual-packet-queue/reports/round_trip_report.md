# Deterministic Round Trip

Offline end-to-end evidence is covered by the cloud queue service tests.

Round trip path:

1. local blocker
2. queue request creation
3. ready state
4. packet export
5. deterministic fake cloud response
6. response import
7. independent validation
8. `validated_safe`
9. status/list/show verification

Additional cases covered:

- approval-required classification
- validation-failed classification
- batch import with valid and invalid siblings
- dependency-blocked request excluded from the first batch and eligible after prerequisite resolution

Evidence:

- `tests/test_cloud_queue_service.py`
- `tests/test_cloud_queue_cli.py`
- `tests/test_cloud_queue_contract.py`

