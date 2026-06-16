# Codex Runtime Connector

Codex is the primary configured runtime for code-changing work in this project.
Role context packets keep each agent handoff focused, and Codex task files turn
those packets into runtime-ready instructions.

For the manual operator flow that runs those files safely one role at a time,
see `docs/codex_task_execution.md`.
For the runtime tier policy, see `docs/runtime_config.md`.
For Docker CLI installation and authentication, see
`docs/codex_docker_runtime.md`.

## Command

```powershell
docker compose run --rm dev agentic codex-task create --story STORY_SLUG
```

Useful options:

- `--agent AGENT_ID` creates one task file.
- `--all` creates a task file for every role context packet.
- Omitting both `--agent` and `--all` defaults to all packets.
- `--project PATH` points at another project folder.
- `--force` overwrites existing task files.
- `--model MODEL_NAME` writes a task-level model recommendation.

Without `--model`, recommendations come from `.agentic/agent_runtime.yaml`.
Blueprints define story scope; they are not the source of truth for provider or
model assignment.

The command reads role context packets from:

```text
stories/STORY_SLUG/reports/role_context/AGENT_ID_context.md
```

It writes Codex task files to:

```text
stories/STORY_SLUG/reports/codex_tasks/AGENT_ID_codex_task.md
```

It also writes:

```text
stories/STORY_SLUG/reports/codex_task_result.yaml
stories/STORY_SLUG/reports/codex_task_report.md
```

If role context is missing, build it first:

```powershell
docker compose run --rm dev agentic build-context --story STORY_SLUG --all --force
```

## What The Task File Contains

Each task file includes:

- Agent identity.
- Story slug.
- Model recommendation from `.agentic/agent_runtime.yaml`, or the `--model`
  override.
- Recommended execution order context, including this agent's position and
  neighboring roles.
- Safety rules.
- Full role context packet content.
- Exact role objective.
- Required output report path.
- Validation commands.
- A do-not-do list.

The model recommendation is only written into the task file. The command does
not switch the active Codex model.

Default model tiers are:

```text
research_agent           gpt-5.4-mini (codex)
planner_agent            gpt-5.4 (codex)
developer_agent          gpt-5.4 (codex)
test_agent               gpt-5.4 (codex)
docs_agent               gpt-5.4-mini (codex)
security_quality_agent   gpt-5.5 (codex)
local_reviewer_agent     gpt-5.5 (codex)
cloud_reviewer           main_cloud_model (manual_cloud_model)
local_model_helper       gemma-4-26b (local_model_optional), prompt_mode micro
```

`gpt-5.4` is the normal worker tier for planning, implementation, and tests.
`gpt-5.4-mini` is used for lighter research, documentation, reporting, and
summarization. `gpt-5.5` is reserved for high-risk security, final local review,
DeFi, risk-sensitive work, and final judgment. Gemma remains optional for
micro-mode local draft help only.

Recommended execution order comes from `agent_plan.yaml` when `execution_order`
is present. If it is missing, the command uses the standard order:

```text
research_agent
planner_agent
developer_agent
test_agent
docs_agent
security_quality_agent
local_reviewer_agent
```

## Safety Boundary

`agentic codex-task create` is a local file-generation command. It does not:

- Invoke Codex automatically.
- Call cloud models.
- Execute agents.
- Call GitHub APIs.
- Commit, push, merge, or deploy.

Generated files under `reports/codex_tasks/` are runtime artifacts. They are
ignored by Git and blocked by artifact-policy except for `.gitkeep`.

`agentic run-story --execute` can invoke Codex only when the safe automatic
runtime adapter is explicitly enabled:

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

The adapter runs one generated task file at a time with `shell=False`, feeds the
task file content to `codex exec --sandbox workspace-write -` through stdin,
records stdout, stderr, and exit code under
`stories/STORY_SLUG/reports/codex_runtime/`, requires each role's expected
report after Codex exits, and stops before merge. The command template is
allowlisted; story files cannot provide arbitrary commands.

Default safe runtime:
`codex exec --sandbox workspace-write -`

`codex exec` accepts `-` to read task file content from stdin and is read-only
by default. Agentic prefers `workspace-write` when it works so Codex can create
required story report files under the mounted workspace while keeping the inner
Codex sandbox active.

Inside some Docker environments, Codex's inner Linux sandbox can fail with
`bwrap: No permissions to create a new namespace`. If that happens, the only
supported fallback is an explicit Docker-isolated shape:

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

This is a tradeoff. Docker remains the outer isolation boundary, but Codex no
longer has its inner `workspace-write` sandbox. In that mode it can read and
write the mounted workspace and may access Codex auth or config state inside
the container. It remains disabled by default and is rejected unless
`docker_isolation_acknowledged: true`. Use it only for trusted repos and
controlled local automation. The runner still does not merge, push,
force-push, deploy, open PRs, or call GitHub APIs.

The Docker `dev` image installs the Codex CLI. Check from inside Docker with:

```powershell
docker compose run --rm dev which codex
docker compose run --rm dev codex --version
docker compose run --rm dev codex exec --help
```

Use stdin with `codex exec --sandbox workspace-write -` unless the installed CLI
help confirms a different supported file-input flag. The current Docker smoke
check verifies command compatibility without starting a model run.

Installation does not include credentials. `compose.yml` sets
`CODEX_HOME=/codex-home` and mounts a Docker-managed `codex-home` named volume
so optional `codex login --device-auth` state stays outside the repo and outside
the image. Operators may also pass `CODEX_API_KEY` only to the single
`docker compose run` invocation that needs it.

Do not commit API keys, access tokens, `.codex/`, `codex-home/`, `codex-auth/`,
or `auth.json`. If Codex is unavailable, automatic Codex execution blocks safely
with `BLOCKED_CODEX_COMMAND_NOT_FOUND`.

## Human Review

The human owner still reviews pull requests and merges manually. Codex task
files are an operator handoff, not an approval or merge decision.

Controlled Codex execution is limited to the run-story adapter and remains
disabled by default.
