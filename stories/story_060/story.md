# Story 060 - Blueprint-Driven Local Model Execution

## Goal

Allow each blueprint-defined agent role to execute using a local model.

## Why This Matters

The system already prepares role-specific work, but Story 060 makes local-model
execution the first-class local automation path for blueprint-selected roles.

## Acceptance Criteria

- Blueprint agents remain the authoritative list of roles to execute.
- A blueprint can assign a local model to each agent.
- Missing blueprint assignments use runtime role defaults.
- Missing role defaults use the global local-model default.
- No Codex or cloud code-generation fallback occurs.
- Role execution follows blueprint-defined order.
- Each role receives its role-specific context packet.
- Each role output is stored separately.
- Each call writes audit metadata.
- Writable-path restrictions are enforced.
- Execution failures are classified and recorded.
- Execution state survives interruption.
- Resume skips successfully completed roles.
- Dry-run shows the resolved model and source of resolution.
- Existing workflows remain backward compatible.

## Not In Scope

- Cloud code review.
- Local repair based on cloud feedback.
- Automatic story approval.
- Token-aware context reduction.
- Automatic Git commits, merges, or deployment.

## Definition of Done

- Unit tests pass.
- Ruff passes.
- Existing tests remain green.
- Documentation explains blueprint overrides and runtime defaults.
