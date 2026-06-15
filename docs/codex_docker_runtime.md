# Codex Docker Runtime

The Docker `dev` image installs the Codex CLI during `docker compose build` so
the normal container workflow can detect and run Codex:

```powershell
docker compose build
docker compose run --rm dev which codex
docker compose run --rm dev codex --version
docker compose run --rm dev codex exec --help
```

This installs the CLI binary only. It does not bake API keys, access tokens,
ChatGPT sessions, or `auth.json` into the image.

## Authentication

`compose.yml` sets `CODEX_HOME=/codex-home` and mounts a Docker-managed named
volume at that path. If you authenticate Codex inside the container, cached
Codex auth and config state stays in the `codex-home` Docker volume, outside
the repository and outside the built image.

Interactive or device-code login:

```powershell
docker compose run --rm dev codex login --device-auth
docker compose run --rm dev codex doctor --summary
```

Programmatic one-off execution can use `CODEX_API_KEY`, but pass it only to the
single container invocation that needs it:

```powershell
docker compose run --rm -e CODEX_API_KEY dev codex exec --json "summarize this repository"
```

Do not put `CODEX_API_KEY`, `CODEX_ACCESS_TOKEN`, `auth.json`, `.codex/`,
`codex-home/`, or `codex-auth/` in the repository. The artifact policy and
public-readiness checks block those local Codex state paths if they are ever
tracked.

## Enable The Adapter

Codex automatic story execution remains disabled by default. Enable it only
after the smoke checks and authentication are working inside Docker:

```yaml
codex_runtime:
  enabled: true
  command: codex
  args:
    - exec
    - "-"
  stdin_from_task_file: true
  timeout_seconds: 1800
```

Then run:

```powershell
docker compose run --rm dev agentic run-story --story STORY_SLUG --execute
```

The adapter still runs one generated task file at a time, uses the allowlisted
`codex exec -` command template, feeds the generated task file through stdin,
records runtime output under the story reports folder, requires expected
reports, and stops before merge, push, deploy, PR creation, or GitHub API calls.
Use this stdin shape unless `codex exec --help` in the installed CLI confirms a
different supported file-input flag.

If Codex is missing or unavailable, `run-story --execute` blocks safely with
`BLOCKED_CODEX_COMMAND_NOT_FOUND`.
