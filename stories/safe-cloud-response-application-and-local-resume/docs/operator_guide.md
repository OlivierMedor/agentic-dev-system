# Story 064 Operator Guide

## Overview

Story 064 adds a safe application layer for eligible Story 063 cloud responses. It does not rewrite the canonical blueprint. It writes immutable application plans, immutable runtime-plan revisions, execution leases, and audit events under `.agentic/`.

## Architecture

- `cloud_application/eligibility.py` validates whether a Story 063 response is safe to apply.
- `cloud_application/planning.py` builds immutable application plans.
- `cloud_application/graph.py` transforms the runtime task graph.
- `cloud_application/persistence.py` stores records with atomic writes.
- `cloud_application/transactions.py` coordinates apply-time state changes.
- `cloud_application/leases.py` binds local execution to a runtime revision.
- `cloud_application/rollback.py` restores the prior revision when valid.
- `cloud_application/recovery.py` inspects and reconciles interrupted operations.
- `cloud_application/audit.py` records append-only evidence.

## Canonical Blueprint Protection

- The runtime application layer may update runtime execution state only.
- It must not rewrite `blueprints/blueprint.yaml`.
- It must not rewrite canonical story definitions, acceptance criteria, generated instructions, or repository policies.
- Cloud-derived changes are represented as application plans, runtime-plan revisions, overlays, leases, and audits.

## Runtime Paths

- `.agentic/cloud_applications/`
- `.agentic/runtime_plans/`
- `.agentic/execution_leases/`
- `.agentic/cloud_queue/`

These paths are runtime-only. They are ignored by Git and excluded from artifact-policy and public-readiness checks.

## Eligibility

- `validated_safe` responses can be planned and applied when request, response, and source revision checksums match.
- `approval_required` responses additionally require an exact approval checksum match.
- Rejected, cancelled, failed, stale, or already-applied responses are rejected.

## Planning

- `plan-apply` creates an immutable application plan.
- Plans are versioned and checksum-bound.
- A changed source revision or changed response requires replanning.

## Dry Run

- `apply --dry-run` performs the full validation path.
- It creates or displays the immutable plan.
- It does not change the active revision.
- It does not create leases.
- It does not start local execution.

## Apply

- `apply --request <id>` applies an eligible response to a new runtime revision.
- The apply flow is transactional.
- The active revision pointer updates atomically.
- The previous revision remains available for rollback.

## Resume

- `resume --request <id>` is explicit.
- Local execution resumes only from the active runtime revision.
- Old workers cannot publish results for a newer revision.
- Execution attempts are lease-bound and revision-bound.

## Leases

- Leases include task ID, execution attempt ID, runtime revision ID, checksum, and writable paths.
- A stale lease must never publish into the active revision.

## Rollback

- `rollback --application <id>` restores the prior runtime revision when the application lineage is valid.
- Rollback does not automatically revert Git changes.
- It reports work products that need operator review.

## Recovery

- `recover` inspects interrupted transactions, corrupt pointers, missing revisions, stale leases, and stuck application states.
- It recommends safe actions and does not guess when state is ambiguous.

## Cleanup

- Remove only transient runtime artifacts under `.agentic/` when needed.
- Do not delete canonical workspace files to recover from a runtime application issue.
- Review rollback and recovery output before making manual changes.

## Troubleshooting

- If the active pointer is corrupt, stop and run `recover`.
- If an application plan is stale, re-run `plan-apply`.
- If a lease is stale, discard the result and resume from the active revision.
- If rollback reports unrelated later applications, resolve the later application first.

## Limitations

- No paid provider integration exists.
- No cloud provider network call is added.
- Imported responses are never executed automatically.
- Automatic apply is disabled by default.
- Automatic resume is disabled by default.

## PowerShell Examples

```powershell
$env:PYTHONPATH = 'src'
python -m agentic_dev.cli cloud-queue plan-apply --request cloud-req-0001
python -m agentic_dev.cli cloud-queue apply --request cloud-req-0001 --dry-run
python -m agentic_dev.cli cloud-queue apply --request cloud-req-0001
python -m agentic_dev.cli cloud-queue resume --request cloud-req-0001
python -m agentic_dev.cli cloud-queue rollback --application cloud-application-0001
python -m agentic_dev.cli cloud-queue application-status
python -m agentic_dev.cli cloud-queue application-show --application cloud-application-0001
python -m agentic_dev.cli cloud-queue recover
```
