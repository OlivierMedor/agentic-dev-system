# Story 056 - Automatic Codex Runtime Adapter

## Goal

Add an automatic Codex runtime adapter so `agentic run-story --execute` can run
generated Codex task files when a safe Codex runtime is configured.

## Problem

Story 055 added one-command story execution, but execute mode stops with
`BLOCKED_MISSING_RUNTIME` unless a local model runtime is enabled or all reports
already exist. Codex is the primary configured agent runtime, so the one-command
runner should be able to execute generated Codex task files automatically when
the operator explicitly enables that runtime.

## Scope

- Add a disabled-by-default `codex_runtime` config section.
- Validate the Codex command template against a narrow allowlist.
- Run generated Codex task files one role at a time from `run-story --execute`.
- Capture stdout, stderr, exit code, and aggregate runtime evidence.
- Require each role's expected report after execution.
- Preserve the Story 055 existing-report shortcut.

## Non-Goals

- Do not merge automatically.
- Do not push or force-push.
- Do not deploy.
- Do not open PRs.
- Do not call GitHub APIs from `run-story`.
- Do not run arbitrary commands from story files.
- Do not record cloud review automatically.

## Acceptance Criteria

- `run-story --execute` uses the Codex runtime when `codex_runtime.enabled: true`.
- `run-story --execute` still blocks clearly when no automatic runtime is configured.
- Codex task execution is safe, allowlisted, sequential, and bounded by timeout.
- Runtime output is recorded in story reports.
- Required reports are verified before finalize.
- Existing required reports still skip runtime and finalize.
- Tests cover disabled runtime, enabled runtime invocation, nonzero Codex exit,
  missing expected report, existing-report shortcut, safety flags, and unsafe
  command template rejection.
