# Monitoring and Audit Review

Story 063 keeps runtime monitoring simple and deterministic:

- queue runtime state is isolated under `.agentic/cloud_queue/`
- audit events are recorded as append-only JSONL
- each state transition writes its own event with request ID, batch ID, prior state, new state, packet checksum, request count, and timestamp
- batch exports emit one event per request, not a single aggregate event
- approval records are stored separately from audit events and bind to the normalized response checksum
- runtime queue artifacts are blocked by artifact policy and public-readiness checks

Evidence:

- `tests/test_cloud_queue_service.py`
- `tests/test_cloud_queue_cli.py`
- `src/agentic_dev/cloud_queue/audit.py`
- `src/agentic_dev/cloud_queue/persistence.py`
- `src/agentic_dev/artifact_policy.py`
- `src/agentic_dev/public_readiness.py`

