# Developer Report

Implemented Story 057 by installing the Codex CLI in the Docker `dev` image via
the official non-interactive standalone installer and exposing it at
`/usr/local/bin/codex`.

Docker setup chosen:

- `Dockerfile` installs `ca-certificates`, `curl`, `git`, then runs the Codex
  installer with `CODEX_NON_INTERACTIVE=1` and `CODEX_INSTALL_DIR=/usr/local/bin`.
- `compose.yml` sets `CODEX_HOME=/codex-home` and mounts a Docker-managed named
  volume at `/codex-home`.
- `.agentic/agent_runtime.yaml` now includes `codex_runtime` disabled by
  default with the Story 056 allowlisted `codex exec --file {task_file}`
  template.

Credential handling:

- No API key, access token, `auth.json`, or Codex config is committed.
- No credential is baked into the image.
- Optional Codex login state lives in the Docker-managed `codex-home` volume.
- `.gitignore`, artifact policy, and public readiness block `.codex/`,
  `codex-home/`, and `codex-auth/` state if it appears in the repo.

Docs updated:

- `README.md`
- `docs/codex_docker_runtime.md`
- `docs/codex_runtime.md`
- `docs/runtime_config.md`
- `docs/code_tour.md`

Safety preserved:

- `codex_runtime.enabled` remains false by default.
- The Story 056 command allowlist remains unchanged.
- `run-story` still stops before merge, push, deploy, force-push, PR creation,
  and GitHub API calls.
