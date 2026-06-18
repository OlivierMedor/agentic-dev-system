# STORY-061: Blueprint-Defined Context-Safe Sub-Task Execution

## Goal

Define blueprint-driven, dependency-aware sub-task execution that only runs local tasks whose complete required context fits the assigned model's usable input budget.

## Why This Matters

Story 060 made blueprint-selected local role execution possible. Story 061 makes cloud-planned decomposition explicit and enforceable so local agents execute bounded, context-safe tasks without silently trimming required instructions or falling back to cloud or Codex implementation.

## Acceptance Criteria

- AC-001: A blueprint can define multiple ordered sub-tasks for a story.
- AC-002: Each sub-task has a stable unique ID.
- AC-003: Each sub-task has a role assignment.
- AC-004: Each sub-task can declare dependencies.
- AC-005: Cycles and missing dependencies are rejected before execution.
- AC-006: Only dependency-ready tasks may run.
- AC-007: Each sub-task declares its required context.
- AC-008: Each sub-task declares writable paths.
- AC-009: Each sub-task declares expected outputs.
- AC-010: Each sub-task declares validation requirements.
- AC-011: Each local model has a context window and reserved output budget.
- AC-012: The system computes a usable input budget.
- AC-013: The system independently estimates the final assembled sub-task input size.
- AC-014: All mandatory instructions remain present in the assembled prompt.
- AC-015: Required context is never silently removed or truncated.
- AC-016: A task that does not fit is blocked before model invocation.
- AC-017: An oversized task receives a structured status indicating cloud redecomposition is required.
- AC-018: No local agent is allowed to improvise a decomposition of an oversized cloud task unless explicitly permitted by a future blueprint feature.
- AC-019: Successful task execution persists state.
- AC-020: Failed task execution persists failure details.
- AC-021: Each completed task persists a concise structured handoff summary.
- AC-022: Later tasks may consume declared outputs and decisions from completed dependencies.
- AC-023: Resume skips completed tasks.
- AC-024: Resume retries blocked or failed tasks only when their blocking condition has been resolved.
- AC-025: Writable-path restrictions remain enforced for every sub-task.
- AC-026: Symlink and resolved-path protections from Story 060 remain intact.
- AC-027: No cloud-model, Codex, or hidden implementation fallback is introduced into local execution.
- AC-028: Final story validation checks all original requirements, not merely individual sub-task success.
- AC-029: Audit output clearly shows task ordering, context estimates, execution decisions, and final status.
- AC-030: Existing Story 060 behavior remains backward compatible for blueprints without sub-tasks.

## Not In Scope

- Live external model calls in tests.
- Cloud or Codex implementation fallback during local task execution.
- Automatic local decomposition of oversized cloud-authored tasks.
- Silent trimming of required instructions or required context.
- Deployment, publishing, release tagging, or production rollout.
- Automatic commits, merges, pushes, or pull request creation from local execution.

## Definition of Done

- Unit tests cover sub-task schema, dependency validation, context budget resolution, context assembly, fit gating, state persistence, handoffs, resume, CLI reporting, final validation, and Story 060 backward compatibility.
- Integration tests cover dependency-aware local execution and final story validation.
- Failure tests prove oversized tasks stop before model invocation and produce cloud_redecomposition_required status.
- Regression tests prove Story 060 local role execution, writable-path restrictions, and symlink protections remain intact.
- Documentation explains blueprint decomposition, maximum task-size contract, context-fit rejection, redecomposition, resume, and audit behavior.
- docker compose run --rm dev agentic generate-stories is idempotent.
- docker compose run --rm dev pytest passes.
- docker compose run --rm dev ruff check . passes.
- artifact-policy validation passes.
- runtime-config validation passes.
