# Developer Report

Implemented Story 058 by changing the automatic Codex runtime contract from the
read-only default `codex exec -` shape to the explicit allowlisted command:

`codex exec --sandbox workspace-write -`

Code changes:

- Updated the default runtime config and checked-in `.agentic/agent_runtime.yaml`
  to include `--sandbox workspace-write` while keeping `enabled: false`.
- Kept `shell=False`, `stdin_from_task_file: true`, and the fixed command
  allowlist model.
- Preserved the existing blocking behavior for missing reports and nonzero Codex
  exits.
- Added validation coverage for unsafe sandbox values such as
  `danger-full-access`.
- Updated docs to explain that `codex exec` is read-only by default, why
  agentic opts into workspace-write, and why unrestricted sandbox modes are not
  allowed by default.

Safety preserved:

- No shell redirection.
- No danger-full-access.
- No network enablement by default.
- No merge, push, deploy, force-push, PR creation, or GitHub API behavior.
