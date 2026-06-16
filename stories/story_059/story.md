# Story 059 - Docker-Compatible Codex Execution Mode

## Goal

Make automatic Codex execution work inside the Docker dev runtime in a safe,
explicit, documented way.

## Problem

Story 058 switched the runtime to:

`codex exec --sandbox workspace-write -`

That works when Codex can start its inner Linux sandbox. Inside the Docker dev
container, funding-sniper hit:

`bwrap: No permissions to create a new namespace`

Codex launched and exited `0`, but every shell or `apply_patch` operation that
needed the inner sandbox failed, so the required report was never written.

## Decision

Choose Option B and make it explicit.

Docker remains the outer isolation boundary. Agentic now allows one additional
Codex runtime shape for Docker-only local automation:

`codex exec --sandbox danger-full-access -`

This mode is disabled by default and is rejected unless
`docker_isolation_acknowledged: true` is set.

## Scope

- Keep `codex_runtime.enabled: false` by default.
- Keep `workspace-write` as the default safe command shape.
- Allow `danger-full-access` only for the exact Docker-compatible stdin shape
  and only with explicit acknowledgement.
- Keep `shell=False`, stdin task-file delivery, and required-report blocking.
- Preserve the no-merge, no-push, no-force-push, no-deploy, no-PR, and
  no-GitHub-API safety boundaries.
- Keep artifact-policy and public-readiness blocking Codex auth and state
  paths.
- Update docs, tests, and story evidence.

## Non-Goals

- Do not enable `danger-full-access` silently.
- Do not make Docker mode the default.
- Do not weaken artifact-policy or public-readiness protections.
- Do not merge, push, deploy, open PRs, record cloud review, or call GitHub
  APIs automatically.

## Acceptance Criteria

- Default runtime config remains disabled with the workspace-write shape.
- Runtime validation rejects `danger-full-access` without
  `docker_isolation_acknowledged: true`.
- Runtime validation accepts the exact Docker-compatible danger-full-access
  shape only with explicit acknowledgement.
- Rendered runtime commands match the accepted shapes exactly.
- `stdin_from_task_file: true` still passes task content through stdin.
- Missing required reports still block.
- Nonzero Codex exits still block.
- Safety behavior still forbids merge, push, force-push, deploy, PR creation,
  and GitHub API calls.
- Docs explain the `bwrap` failure mode, the Docker tradeoff, how to enable the
  mode, how to verify it, and why it must not be used for untrusted repos.
