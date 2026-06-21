# Developer Report

Story 064 is implemented as a layered, offline, provider-neutral runtime application system under `src/agentic_dev/cloud_application/`.

Implemented modules:

- `models.py` for application records, plans, revisions, transactions, leases, audit events, recovery, and resume models
- `state_machine.py` for deterministic application state transitions
- `planning.py` for immutable plan construction from the active runtime revision
- `graph.py` for runtime graph transforms and revision building
- `validation.py` for requirement, dependency, writable-path, and context validation
- `persistence.py` for atomic runtime writes and reads
- `transactions.py` for apply-time transactional sequencing and journal persistence
- `publication.py` for revision-bound result gating and quarantine paths
- `resume.py` for explicit resume coordination and execution adapter handoff
- `audit.py` for append-only audit evidence
- `formatting.py` for CLI output
- `service.py` for orchestration across planning, apply, resume, rollback, and recovery

CLI integration:

- Added `cloud-queue plan-apply`
- Added `cloud-queue apply`
- Added `cloud-queue resume`
- Added `cloud-queue rollback`
- Added `cloud-queue application-status`
- Added `cloud-queue application-show`
- Added `cloud-queue recover`

Boundary enforcement:

- Canonical blueprint files remain protected.
- Runtime application artifacts are isolated under `.agentic/`.
- Imported cloud responses are never executed automatically.
- Automatic apply and automatic resume remain disabled by default.

Validation summary:

- Full pytest: `749 passed`
- Ruff: passed
- Story 064 focused suite: `25 passed`
- Story 064 state-machine suite: `25 passed`
- Cloud-queue and regression suite: `207 passed, 1 skipped`
- Generate-stories idempotency: passed
- Artifact-policy, runtime-config, and public-readiness checks: passed
