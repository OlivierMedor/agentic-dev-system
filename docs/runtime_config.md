# Runtime Config

`.agentic/agent_runtime.yaml` is the project-level runtime policy. It decides
which provider and model each agent role should use, and which commands are safe
to run without repeated approval.

Blueprint files describe what to build and why. They should not be the source of
truth for provider or model assignment. Keeping model choices in
`.agentic/agent_runtime.yaml` lets operators change runtime tiers without
rewriting story scope or acceptance criteria.

## Codex-First Defaults

Codex is the primary runtime for assigned agent roles because this project is a
codebase workflow. Most role outputs require repository context, file edits,
tests, linting, and careful adherence to local safety rules. Codex task files
remain inert when created; automatic execution only happens through
`run-story --execute` when `codex_runtime.enabled` is true.

The default tiers are:

```text
research_agent           codex / gpt-5.4-mini
planner_agent            codex / gpt-5.4
developer_agent          codex / gpt-5.4
test_agent               codex / gpt-5.4
docs_agent               codex / gpt-5.4-mini
security_quality_agent   codex / gpt-5.5
local_reviewer_agent     codex / gpt-5.5
cloud_reviewer           manual_cloud_model / main_cloud_model
local_model_helper       local_model_optional / gemma-4-26b / micro
```

`gpt-5.4` is the default worker tier for planner, developer, and test work
because those roles make normal correctness-sensitive code and validation
changes. They need stronger reasoning than a summarization tier but should not
spend the highest-risk review budget by default.

`gpt-5.4-mini` is used for lighter research and documentation roles. Those
roles summarize, organize, and explain known project context more often than
they make final correctness judgments.

`gpt-5.5` is reserved for high-risk security, quality, and final local review.
Those roles decide whether a story is ready for review, look for unsafe
behavior, and should be used for DeFi, risk-sensitive, security-sensitive, or
final judgment work.

`cloud_reviewer` remains `manual_cloud_model / main_cloud_model`. The local CLI
can prepare cloud review packets, but a human decides whether to send them to a
cloud model and records the result manually.

`local_model_helper` keeps Gemma support available as an optional micro-mode
draft helper. It is not the default docs runtime, not a final reviewer, and not
required for normal workflow validation. Its `prompt_mode: micro` setting keeps
local draft prompts intentionally small.

## Codex Runtime Adapter

The automatic Codex adapter is disabled by default:

```yaml
codex_runtime:
  enabled: false
  command: codex
  args:
    - exec
    - --file
    - "{task_file}"
  timeout_seconds: 1800
```

When enabled, `agentic run-story --story STORY_SLUG --execute` runs generated
Codex task files one role at a time and requires each role's expected report
before finalization. The command and args are validated against a narrow
allowlist so story content cannot provide arbitrary commands.

The Docker `dev` image installs the Codex CLI. If you run agentic through
Docker, confirm Codex is available inside the `dev` container before enabling
the adapter:

```powershell
docker compose run --rm dev which codex
docker compose run --rm dev codex --version
```

If `which codex` fails inside Docker, `run-story --execute` will stop safely
with `BLOCKED_CODEX_COMMAND_NOT_FOUND`. Keep `codex_runtime.enabled: false` and
use manual task execution until the container includes the Codex CLI or a
supported mounted/configured runtime.

Authentication is operator-owned. `compose.yml` sets `CODEX_HOME=/codex-home`
and mounts a Docker-managed named volume for optional login state, so credentials
are not stored in the repo or baked into the image. See
`docs/codex_docker_runtime.md`.

## Command Policy

Safe Docker, test, lint, and deterministic workflow commands can be listed under
`command_policy.allowed_without_approval`. Merge, deploy, secret, credential,
wallet, irreversible Git, and destructive file actions belong under
`command_policy.requires_human_approval`.

Validate the policy with:

```powershell
docker compose run --rm dev agentic runtime-config validate
```
