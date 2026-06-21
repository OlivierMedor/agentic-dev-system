# Monitoring Report

Runtime application activity is tracked through append-only audit events and revision-bound records.

Primary runtime locations:

- `.agentic/cloud_applications/`
- `.agentic/runtime_plans/`
- `.agentic/execution_leases/`
- `.agentic/cloud_applications/transactions/`
- `.agentic/cloud_queue/`

Operational signals:

- application state transitions
- plan checksum mismatches
- stale-plan rejections
- transaction failures
- transaction journal transitions
- pointer update failures
- stale lease rejections
- stale result publication rejections
- rollback activity
- recovery inspection and reconciliation

Observed validation signals:

- dry-run validation is deterministic
- apply remains explicit
- resume remains explicit
- rollback does not revert Git automatically
- runtime artifacts are ignored by Git
