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
    - --sandbox
    - workspace-write
    - "-"
  stdin_from_task_file: true
  timeout_seconds: 1800
  docker_isolation_acknowledged: false
```

Then run:

```powershell
docker compose run --rm dev agentic run-story --story STORY_SLUG --execute
```

The adapter still runs one generated task file at a time, uses the allowlisted
`codex exec --sandbox workspace-write -` command template, feeds the generated
task file through stdin, records runtime output under the story reports folder,
requires expected reports, and stops before merge, push, deploy, PR creation, or
GitHub API calls.

Default safe runtime:
`codex exec --sandbox workspace-write -`

`codex exec` accepts `-` to read task file content from stdin and is read-only by default.
Agentic prefers `workspace-write` when it works so Codex can create
the required story report files inside the mounted workspace while keeping the
inner Codex sandbox active.

## Why Docker Mode Exists

Some Docker runtimes do not allow the inner Linux sandbox that Codex uses for
`workspace-write`. A typical failure looks like:

```text
bwrap: No permissions to create a new namespace
```

That means Codex launched, but its inner sandbox could not start inside the
container. In that case the supported fallback is to use Docker as the
isolation boundary and explicitly acknowledge the less-restricted Codex mode:

Docker-compatible fallback:
`codex exec --sandbox danger-full-access -`

Requires:
`docker_isolation_acknowledged: true`

```yaml
codex_runtime:
  enabled: true
  command: codex
  args:
    - exec
    - --sandbox
    - danger-full-access
    - "-"
  stdin_from_task_file: true
  timeout_seconds: 1800
  docker_isolation_acknowledged: true
```

This mode is disabled by default and validation rejects it unless the
acknowledgement flag is present.

## Security Tradeoff

`workspace-write` keeps the inner Codex sandbox active and is the preferred
mode whenever it works.

`danger-full-access` inside Docker is a tradeoff:

- Codex can read and write the mounted workspace.
- Codex may access auth or config state available inside the container,
  including the `CODEX_HOME` volume.
- Docker is the isolation boundary, not Codex's inner Linux sandbox.

Use this only for trusted repos and controlled local automation. Do not use it
for untrusted repositories.

The runner safety policy is unchanged. It still does not merge, push,
force-push, deploy, open PRs, or call GitHub APIs.

## Verify With A Small Story

Use a disposable or controlled story that requires a single report such as
`reports/research_report.md`.

1. Build context and task files.
2. Enable the acknowledged Docker-compatible config above.
3. Run `docker compose run --rm dev agentic run-story --story STORY_SLUG --execute`.
4. Confirm the required report is created under `/workspace/stories/.../reports/`.
5. Confirm the run moves past `automatic-agent-runtime` and only stops later if
   normal story evidence is missing.

Use this stdin shape unless `codex exec --help` in the installed CLI confirms a
different supported file-input flag.

If Codex is missing or unavailable, `run-story --execute` blocks safely with
`BLOCKED_CODEX_COMMAND_NOT_FOUND`.
