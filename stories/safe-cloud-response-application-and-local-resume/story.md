# STORY-064: Story 064 - Safe Cloud Response Application and Local Execution Resume

## Goal

Allow a validated or explicitly approved cloud response from Story 063 to be applied safely to the runtime execution plan and unblock local execution.

## Why This Matters

Story 063 safely imports and classifies cloud responses, but the repository still needs a transactional, revision-bound application layer that can convert an eligible response into an immutable runtime-plan update without rewriting the canonical blueprint.

## Acceptance Criteria

- Only eligible responses can produce application plans.
- validated_safe responses may be planned without approval.
- approval_required responses need valid approval.
- Approval checksum must match.
- Request checksum must match.
- Stale responses cannot be applied.
- Already-applied responses cannot be applied twice.
- Application plans are versioned.
- Application plans are immutable.
- Dry run performs complete validation.
- Dry run makes no runtime-plan changes.
- Canonical blueprint is never modified.
- Source tasks are superseded, not deleted.
- Source-task history is preserved.
- Child tasks preserve requirement coverage.
- Child tasks fit local context limits.
- Child tasks have valid dependencies.
- Dependency cycles are rejected.
- Missing dependencies are rejected.
- Unsafe writable-path changes are rejected.
- Approved writable-path changes must match approval.
- Architecture overlays are versioned.
- Runtime revisions are immutable.
- Every revision has a parent.
- Revision checksums are verified.
- Active revision changes atomically.
- Failed application leaves prior revision active.
- Partial revisions are not activated.
- Application is idempotent.
- Concurrent stale applications are rejected.
- Resume eligibility is calculated after application.
- Resume preserves unaffected completed tasks.
- Resume skips superseded tasks.
- Resume uses only the active revision.
- Resume uses the existing local execution pipeline.
- Resume performs no cloud call.
- Old-revision task results are rejected.
- Execution leases are revision-bound.
- Automatic resume is disabled by default.
- Automatic apply is disabled by default.
- Explicit apply works.
- Explicit resume works.
- Rollback restores the prior active revision.
- Rollback preserves history.
- Rollback does not silently revert Git changes.
- Incomplete transactions are detected.
- Corrupt active pointers are reported safely.
- Every application action is audited.
- Audit logs contain checksums and state transitions.
- Audit logs contain no secrets.
- Runtime application artifacts are not committed.
- Artifact policy detects tracked runtime artifacts.
- Public readiness excludes runtime artifacts.
- Windows and Linux behavior are equivalent.
- Story 061 behavior remains intact.
- Story 062 behavior remains intact.
- Story 063 behavior remains intact.
- Generation remains idempotent.
- CI is deterministic and offline.
- No paid provider integration is introduced.

## Implementation Review Scope

- Eligibility checks for validated_safe and approval_required responses
- Immutable application plans with graph diffs and rollback metadata
- Runtime-plan revision persistence and active pointer management
- Transactional application and stale-plan rejection
- Task replacement, dependency recalculation, and resume eligibility
- Revision-bound execution leases and stale lease rejection
- Explicit rollback, recovery, and audit trails
- agentic cloud-queue plan-apply, apply, apply --dry-run, resume, rollback, application-status, and application-show
- Canonical blueprint protection and runtime overlay storage
- Offline deterministic tests with no paid provider calls

## Historical Blueprint Notes

- Paid cloud API integrations.
- Automatic provider selection at runtime.
- Silent canonical blueprint rewrites.
- Automatic merging, deployment, publishing, or live execution.
- Automatic application or resume by default.
- Automatic Git reverts after local execution changes.
- Secret-bearing runtime artifacts or hidden fallback paths.

## Definition of Done

- The blueprint defines the safe application, resume, rollback, recovery, and audit flow.
- Acceptance criteria cover eligibility, planning, dry run, transactional application, resume, rollback, and regression safety.
- The generated Story 064 workspace is created by agentic generate-stories and generation is idempotent across two runs.
- docker compose run --rm dev pytest passes.
- docker compose run --rm dev ruff check . passes.
- artifact-policy validation passes.
- runtime-config validation passes.
- hidden-Unicode hygiene validation passes.
- Public-readiness validation passes when applicable to the repository state.
- No paid cloud API calls are implemented.
- No provider network access is added.
- Manual application and manual resume remain explicit.

