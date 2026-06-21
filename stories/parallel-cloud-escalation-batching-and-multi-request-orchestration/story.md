# STORY-065: Story 065 - Parallel Cloud Escalation Batching and Multi-Request Orchestration

## Goal

Extend Stories 063 and 064 so the system can orchestrate multiple independent cloud escalations and their resulting runtime applications as one dependency-aware batch.

## Why This Matters

Story 063 safely imports and classifies cloud responses, and Story 064 safely applies one response at a time. Story 065 adds a batch orchestration layer so multiple request, response, application, resume, rollback, and recovery operations stay independently traceable while still being scheduled in deterministic dependency-aware waves.

## Acceptance Criteria

- A batch can group multiple independent cloud requests.
- Dependent requests are not exported prematurely.
- Batch membership is immutable after export.
- Each request retains its own checksum.
- The batch manifest has its own checksum.
- A multi-response bundle can be imported.
- Malformed responses are isolated from valid siblings.
- Missing responses remain pending.
- Later import of missing responses works.
- Duplicate responses are rejected.
- Unknown responses are rejected.
- Batch status is derived from item states.
- Partial success is represented accurately.
- Complete failure is represented accurately.
- The dependency DAG is validated.
- Cycles are rejected.
- Deterministic scheduling order is used.
- Independent validation may run in parallel.
- Application conflicts are detected.
- Conflicting applications are serialized or blocked.
- Application plans remain individual.
- Application checksums remain individual.
- Approvals remain individual.
- Runtime pointer updates remain serialized.
- One active runtime revision exists.
- Dry run makes no mutation.
- Dry run reports execution waves.
- Batch apply uses Story 064 transactions.
- One application failure blocks only dependents.
- Independent applications may continue.
- Per-item application results are preserved.
- Resume uses Story 064 leases.
- Conflicting writable-path groups do not run together.
- Blocked resume groups do not run.
- Independent resume groups may run concurrently.
- Stale workers cannot publish.
- Retry creates a new attempt.
- Retry preserves prior evidence.
- Stale retry is rejected.
- Malformed responses are not retried automatically.
- Cancellation prevents new work.
- Cancellation preserves completed work.
- Running leases are handled safely.
- Batch rollback uses reverse order.
- Unsafe rollback is rejected.
- Partial rollback is represented.
- Git changes are never automatically reverted.
- Batch records are versioned.
- Batch records are immutable where required.
- Batch audit is append-only.
- Item audit remains intact.
- Runtime artifacts are not committed.
- Artifact policy detects tracked batch artifacts.
- Public readiness excludes batch artifacts.
- Windows behavior is supported.
- Linux behavior is supported.
- Story 063 behavior remains intact.
- Story 064 behavior remains intact.
- Generation remains idempotent.
- No paid provider integration is introduced.

## Implementation Review Scope

- Canonical batch records, items, attempts, and dependency graph semantics
- Cloud request export batches for ready independent requests
- Cloud response import batches with isolated validation results
- Application batches, execution waves, and revision-chain planning
- Resume batches, retry handling, cancellation, and rollback coordination
- Deterministic state transitions, audit trails, and progress derivation
- Repository-consistent `agentic cloud-queue batch ...` commands
- Runtime batch artifact layout and artifact-policy guardrails
- Offline-only tests and no paid provider calls
- Backward compatibility for Stories 063 and 064

## Historical Blueprint Notes

- Paid cloud API integrations.
- Provider network access or automatic provider selection.
- Automatic live cloud-provider execution.
- Silent canonical blueprint rewrites from imported cloud data.
- Automatic merging, deployment, publishing, or live execution.
- Automatic commits or merges from cloud responses.
- Runtime batch records, locks, attempts, response bundles, and audits committed to Git.

## Definition of Done

- The blueprint defines the batch record schema, lifecycle, dependency graph, and item-level traceability rules.
- Acceptance criteria cover batch export, multi-response import, dry run, apply, resume, retry, cancellation, rollback, recovery, and regression safety.
- The generated Story 065 workspace is created by agentic generate-stories and generation is idempotent across two runs.
- docker compose run --rm dev pytest passes.
- docker compose run --rm dev ruff check . passes.
- artifact-policy validation passes.
- runtime-config validation passes.
- hidden-Unicode hygiene validation passes.
- Public-readiness validation passes when applicable to the repository state.
- No paid cloud API calls are implemented.
- No provider network access is added.
- Manual cloud mode remains the default.
- Automatic batch apply and automatic batch resume remain disabled by default.

