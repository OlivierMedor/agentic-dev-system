# Story 057 - Codex Docker Runtime

## Goal

Make the Docker `dev` runtime able to validate and run the Codex CLI safely for
the existing disabled-by-default Codex runtime adapter.

## Problem

The normal operator workflow runs through Docker:

```powershell
docker compose run --rm dev agentic run-story --story STORY_SLUG --execute
```

Story 056 added a safe adapter that can invoke generated Codex task files only
when `codex_runtime.enabled: true`, but the Docker development image did not
provide the `codex` command. Operators could enable the adapter and then block
on `BLOCKED_CODEX_COMMAND_NOT_FOUND`.

## Scope

- Install the Codex CLI in the Docker `dev` image.
- Provide Docker smoke checks for `which codex` and `codex --version`.
- Keep Codex authentication and configuration outside the repository and image.
- Document the supported Docker authentication/configuration path.
- Preserve the Story 056 disabled-by-default runtime and command allowlist.
- Extend policy checks so Codex auth/config state is not tracked.

## Non-Goals

- Do not commit API keys, access tokens, `auth.json`, or Codex local state.
- Do not bake secrets into the Docker image.
- Do not make `run-story` merge, push, deploy, open PRs, force-push, or call
  GitHub APIs.
- Do not weaken the `codex_runtime` command template allowlist.
- Do not record cloud review automatically.

## Acceptance Criteria

- `docker compose run --rm dev which codex` succeeds.
- `docker compose run --rm dev codex --version` succeeds, or an equivalent safe
  Codex health check is documented if `--version` is unavailable.
- `.agentic/agent_runtime.yaml` includes a safe disabled-by-default
  `codex_runtime` section that operators can enable explicitly.
- Documentation explains Docker Codex authentication and credential handling.
- No secrets are committed or baked into the image.
- If Codex is unavailable, the existing
  `BLOCKED_CODEX_COMMAND_NOT_FOUND` behavior remains clear and safe.
- Existing Story 056 safety constraints remain intact.
- `run-story` still stops before merge, push, deploy, force-push, PR creation,
  and GitHub API calls.
