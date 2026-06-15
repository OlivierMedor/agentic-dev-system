# Story 055 — One-command story runner

## Goal

Add a one-command story runner so a user can run a complete local story workflow without manually opening prompt files or pasting agent prompts.

Desired commands:

agentic run-story --story <story-folder-or-slug> --execute

agentic run-next-story --execute

## Problem

The current workflow has useful pieces, but the user has to manually connect them.

Current pieces include:

- generate-stories
- workflow-run prepare
- build-context
- codex-task
- manual prompt execution
- workflow-run local-finalize
- cloud review
- merge readiness

The blueprint should feel like the first domino in an automated chain.

## Scope

Implement the first version of one-command story execution.

This story should run one story only.

It should not merge automatically.
It should not deploy.
It should not run stories in parallel.

## Required behavior

The command should:

1. Resolve the target project folder.
2. Resolve the story by folder name or slug.
3. Run or reuse story preparation.
4. Assign agents if needed.
5. Generate prompts if needed.
6. Build context if needed.
7. Create Codex/local-agent task files if needed.
8. Run the configured automatic agent runtime if available.
9. Fail clearly if no automatic runtime is configured.
10. Detect missing required agent reports.
11. Run local finalize.
12. Run quality gate.
13. Update story status.
14. Stop before merge.
15. Print the next action for the human owner.

## Safety rules

The command must not:

- merge branches
- push to git
- deploy
- open PRs automatically
- modify unrelated story folders
- pick stories alphabetically
- run future stories unless explicitly requested
- continue after quality gate failure
- continue after missing required reports

## Acceptance criteria

- CLI exposes agentic run-story --story <story>.
- CLI exposes agentic run-next-story if feasible.
- run-story can resolve a story by exact folder name.
- run-story can resolve a story by slug if metadata supports it.
- run-story without --execute prints or writes a plan only.
- run-story --execute performs safe local workflow steps in order.
- If no automatic runtime is configured, the command stops with a clear error.
- The command does not merge, push, deploy, or open PRs.
- Tests cover story resolution, dry-run planning, missing runtime behavior, and no-auto-merge safety.
- Existing tests continue to pass.
