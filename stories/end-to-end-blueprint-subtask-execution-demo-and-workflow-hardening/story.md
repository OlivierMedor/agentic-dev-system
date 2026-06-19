# STORY-062: Story 062 - End-to-End Blueprint Subtask Execution Demo and Workflow Hardening

## Goal

Define a complete blueprint for a safe end-to-end demo that proves Story 061 sub-task execution works in practice with the same dependency-aware pipeline in deterministic fake mode and real local-model mode, while also fixing post-merge quality-gate verification so clean checkouts do not require committed runtime review artifacts.

## Why This Matters

Story 061 defines dependency-aware local sub-task execution, but the repository still needs a practical, operator-friendly proof that the workflow works end to end in CI-safe fake mode and manual local-runtime mode. The same story also needs to harden the quality-gate evidence lifecycle so merged-code verification regenerates ephemeral evidence instead of incorrectly failing on clean checkouts.

## Acceptance Criteria

- AC-001: `agentic demo-subtasks` exists.
- AC-002: Fake mode works without network or local model availability.
- AC-003: Local mode uses the existing supported local runtime.
- AC-004: Both modes share the same execution pipeline.
- AC-005: The demo creates a temporary sandbox.
- AC-006: The demo never writes outside the sandbox.
- AC-007: Symlink escape is blocked.
- AC-008: Unsafe multi-file output produces no partial writes.
- AC-009: The fake adapter is deterministic.
- AC-010: The fake adapter can simulate success.
- AC-011: The fake adapter can simulate failure.
- AC-012: The fake adapter can simulate oversized-task behavior.
- AC-013: The demo executes sub-tasks in deterministic dependency order.
- AC-014: Completed tasks persist handoff summaries.
- AC-015: Resume skips completed tasks.
- AC-016: Failed dependencies block downstream tasks.
- AC-017: Oversized tasks are blocked before model invocation.
- AC-018: Oversized tasks persist cloud-redecomposition-required state.
- AC-019: Required context is not silently trimmed.
- AC-020: Final story validation checks original requirements.
- AC-021: The calculator fixture produces real files.
- AC-022: Generated fixture tests pass in the success scenario.
- AC-023: The CLI output is concise and operator-readable.
- AC-024: The workspace is cleaned automatically by default.
- AC-025: `--keep-workspace` preserves it for inspection.
- AC-026: Local mode fails clearly when no local runtime is configured.
- AC-027: No cloud or Codex fallback is used.
- AC-028: Post-merge quality verification works on a fresh clean checkout.
- AC-029: Post-merge verification regenerates pytest and Ruff evidence.
- AC-030: Post-merge verification does not require committed runtime artifacts.
- AC-031: Post-merge verification leaves Git clean and does not rewrite tracked story reports unexpectedly.
- AC-032: Pre-merge quality-gate behavior remains intact.
- AC-033: Failed regenerated evidence causes verification failure.
- AC-034: Story 060 remains backward compatible.
- AC-035: Story 061 remains backward compatible.
- AC-036: Existing CI behavior remains stable.
- AC-037: The demo is safe for GitHub Actions in fake mode.
- AC-038: Documentation explains fake and local modes.
- AC-039: Documentation explains sandbox safety.
- AC-040: Documentation explains pre-merge versus post-merge verification.

## Implementation Review Scope

- `agentic demo-subtasks`
- deterministic fake-model mode
- real local-model mode using the existing runtime adapter
- safe temporary sandbox execution
- success, oversized, resume, and dependency-failure scenarios
- real file changes inside the sandbox
- post-merge story verification that regenerates evidence
- no requirement to commit runtime review artifacts
- no cloud or Codex fallback
- full backward compatibility with Stories 060 and 061

## Historical Blueprint Notes

- Runtime-generated demo workspaces, runtime review bundles, caches, or machine-specific artifacts committed to Git.
- Arbitrary writes to the main repository tree, user home directories, or any path outside the disposable sandbox.
- Deployment, publishing, release tagging, direct pushes to main, local merges to main, or force-pushes.

## Definition of Done

- The blueprint defines the end-to-end demo, sandbox model, scenario matrix, and post-merge quality-gate design with explicit dependency-aware sub-tasks.
- Acceptance criteria cover fake mode, local mode, shared execution path, sandbox safety, resume, dependency blocking, oversized-task handling, and post-merge verification behavior.
- The generated Story 062 workspace is created by agentic generate-stories and generation is idempotent across two runs.
- docker compose run --rm dev pytest passes.
- docker compose run --rm dev ruff check . passes.
- artifact-policy validation passes.
- runtime-config validation passes.
- hidden-Unicode hygiene validation passes.
- Public-readiness validation passes when applicable to the repository state.
- agentic demo-subtasks is implemented.
- Fake and local modes are implemented.
- All four scenarios are validated.
- Sandbox safety is implemented.
- A real local-model demonstration passes.
- Post-merge verification is implemented.
- Tests and documentation are completed.
- Backward compatibility is preserved for Stories 060 and 061.
