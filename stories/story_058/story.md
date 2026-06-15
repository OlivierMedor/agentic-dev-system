# Story 058 - Codex Workspace-Write Runtime Mode

## Goal

Allow the automatic Codex runtime adapter to run generated task files in
workspace-write mode so Codex can create the required story report files.

## Problem

The current automatic runtime reaches Codex successfully, but the default
`codex exec` behavior is read-only. Generated task files therefore complete
without creating the expected report artifacts, and `run-story` blocks with
`BLOCKED_MISSING_CODEX_REPORT`.

## Scope

- Change the default `codex_runtime` command shape to use
  `codex exec --sandbox workspace-write -`.
- Keep the runtime adapter disabled by default.
- Keep the runtime validator narrow and reject any unsafe sandbox or arg shape.
- Preserve `shell=False`, stdin task-file delivery, and the current merge/push/
  deploy/PR/GitHub API safety boundaries.
- Update tests and docs for the workspace-write behavior.

## Non-Goals

- Do not enable `danger-full-access`.
- Do not enable network access by default.
- Do not add shell redirection or shell command execution.
- Do not make `run-story` merge, push, deploy, force-push, open PRs, or call
  GitHub APIs.
- Do not record cloud review automatically.

## Acceptance Criteria

- `.agentic/agent_runtime.yaml` defaults to the disabled runtime config:
  `codex exec --sandbox workspace-write -`.
- Runtime validation only accepts that exact safe Codex command shape.
- Generated task files are still passed through stdin with `shell=False`.
- Unsafe sandbox values such as `danger-full-access` are rejected.
- Missing expected reports still block safely.
- Nonzero Codex exits still block safely.
- Existing no-merge/no-push/no-deploy/no-PR/no-GitHub-API safety behavior
  remains intact.
- Documentation explains the read-only default, why agentic uses
  `workspace-write`, and why `danger-full-access` is not allowed by default.
