# Runtime Config

`.agentic/agent_runtime.yaml` is the project-level runtime policy. It decides
which provider and model each agent role should use, and which commands are safe
to run without repeated approval.

It can also set `default_base_ref` for review-boundary commands that need to
resolve the project's non-default review base branch. `--base-ref` overrides
the project default when it is passed explicitly. When no explicit `--base-ref`
is provided, `finalize-story`, `review-bundle`, and
`workflow-run --phase local-finalize` use `default_base_ref` before falling
back to `origin/main`. If the selected ref cannot be resolved, the command
fails. There is no silent substitution to another branch.

Blueprint files describe what to build and why. They are not the source of
truth for provider wiring, Codex tiers, or local endpoint settings. Story 060
adds one narrow exception: a blueprint role may optionally override the local
model used by `agentic local-execute`. Runtime defaults still live in
`.agentic/agent_runtime.yaml`, so operators can change normal role defaults
without rewriting story scope or acceptance criteria.

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

`cloud_batch` follows the same manual-first rule for Story 065 orchestration.
It coordinates multiple requests and their downstream applications, but
automatic batch apply and automatic batch resume remain disabled.

`default_base_ref` is optional and should match the branch or ref that review
bundle commands use as their committed-diff base. The default template keeps it
set to `origin/main`, but downstream projects can change it when their review
flow branches from another ref.

`local_model_helper` keeps Gemma support available as an optional micro-mode
draft helper. It is not the default docs runtime, not a final reviewer, and not
required for normal workflow validation. Its `prompt_mode: micro` setting keeps
local draft prompts intentionally small.

## Blueprint-Driven Local Execution

`agentic local-execute --story STORY_SLUG` uses the assigned roles from
`agent_plan.yaml`, which may come from a blueprint-defined `agents:` section.
The blueprint decides which roles participate, their execution order, optional
local model overrides, and writable path boundaries.

Model resolution for each role is:

1. Blueprint role override
2. `local_execution.role_defaults.<role>`
3. `local_execution.global_default_model`
4. blocked if no model resolves

Example defaults:

```yaml
local_execution:
  global_default_model: gemma
  role_defaults:
    research: qwen3
    planner: qwen3
    developer: gemma
    test: qwen3-coder
    documentation: qwen3
    security_quality: gemma
    local_reviewer: gemma
```

`agentic local-execute --dry-run` prints the resolved model and source for each
blueprint-selected role. `--resume` skips completed roles by reading
`stories/STORY_SLUG/reports/local_execution/state.yaml`.

## Context-Safe Sub-Task Execution

When a matching blueprint story declares `subtasks:`, `agentic local-execute`
uses those cloud-authored sub-tasks instead of the legacy role sequence. This
keeps Story 060 behavior backward compatible for blueprints without sub-tasks
while allowing Story 061 stories to execute dependency-aware local work.

Each sub-task must declare:

- `id`, `title`, and `role`
- `depends_on`
- `requirement_ids`
- `required_context.files`, `required_context.summaries`,
  `required_context.prior_task_outputs`, and
  `required_context.architecture_decisions`
- `writable_paths`
- `expected_outputs`
- `validation`
- `context_budget.max_input_tokens`
- `context_budget.reserved_output_tokens`
- `context_budget.required_context_must_fit: true`
- `context_budget.allow_required_context_trimming: false`
- `context_budget.oversized_task_policy: reject_for_cloud_redecomposition`

The complete required prompt is assembled before any model call. It includes
local safety instructions, role instructions, the original story goal,
applicable acceptance criteria, required files, dependency handoffs, writable
path rules, expected outputs, and validation instructions. The implementation
uses a deterministic conservative estimate of one token per four UTF-8 bytes,
rounded up, plus one token per prompt line for Markdown/YAML overhead. This is
not a tokenizer-specific exact count; it is a stable preflight gate designed to
fail closed.

Usable input budget is:

```text
context_budget.max_input_tokens - context_budget.reserved_output_tokens
```

If the assembled prompt estimate exceeds that usable input budget, the task is
not sent to the local model. The state records
`cloud_redecomposition_required`, `context_over_budget`, the estimate, the
usable limit, and `local_agent_may_redecompose: false`. Local agents do not
split oversized cloud-authored tasks themselves.

Sub-task state is written under:

```text
stories/STORY_SLUG/reports/local_execution/state.yaml
stories/STORY_SLUG/reports/local_execution/tasks/TASK_ID/context.md
stories/STORY_SLUG/reports/local_execution/tasks/TASK_ID/output.md
stories/STORY_SLUG/reports/local_execution/tasks/TASK_ID/execution.yaml
```

Those files are runtime artifacts. They are useful for local review and cloud
review packets, but normal artifact policy keeps generated runtime outputs out
of commits unless a story explicitly requires a tracked placeholder.

Resume recalculates dependency readiness deterministically. Completed tasks are
skipped. Failed or blocked tasks retry only when the existing blocking condition
can be resolved by the current blueprint and context. Tasks marked
`cloud_redecomposition_required` do not retry unchanged; the cloud planner must
decompose them further in the blueprint first.

Story 062's `agentic demo-subtasks` command reuses this exact sub-task execution path. Fake and local demo modes share the same blueprint parser, dependency ordering, readiness checks, context assembly, context-fit gate, writable-path validation, state file layout, handoff summaries, resume behavior, and story-wide final validation. Only the model adapter changes between deterministic fake responses and the configured local OpenAI-compatible runtime.

## Codex Runtime Adapter

The automatic Codex adapter is disabled by default:

```yaml
codex_runtime:
  enabled: false
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

When enabled, `agentic run-story --story STORY_SLUG --execute` runs generated
Codex task files one role at a time by passing the task file content to
`codex exec --sandbox workspace-write -` through stdin. `codex exec` accepts
`-` to read task file content from stdin and is read-only by default, so
agentic opts into `workspace-write` so Codex can create the required story
report files inside the mounted workspace only. It requires each role's
expected report before finalization. The command, args, and stdin behavior are
validated against a narrow allowlist so story content cannot provide arbitrary
commands.

The Docker `dev` image installs the Codex CLI. If you run agentic through
Docker, confirm Codex is available inside the `dev` container before enabling
the adapter:

```powershell
docker compose run --rm dev which codex
docker compose run --rm dev codex --version
docker compose run --rm dev codex exec --help
```

Use `codex exec --sandbox workspace-write -` for generated task files unless
the installed CLI help confirms a different supported file-input flag. The help
command checks command compatibility without requiring an authenticated model
run.

The runtime config only accepts two exact shapes with `shell=False` and
`stdin_from_task_file: true`:

- Default safe runtime:
  `codex exec --sandbox workspace-write -`
- Docker-compatible fallback:
  `codex exec --sandbox danger-full-access -`

`workspace-write` is preferred when it works.

`danger-full-access` is disabled by default. The Docker-compatible fallback is
rejected unless `docker_isolation_acknowledged: true` is set explicitly. That
acknowledgement exists because nested Linux sandboxing can fail inside Docker
with errors such as `bwrap: No permissions to create a new namespace`. In that
case Docker becomes the isolation boundary and Codex runs without its inner
Linux sandbox.

Use the Docker-compatible shape only for trusted repos and controlled local
automation. In that mode Codex can read and write the mounted workspace and may
access Codex auth or config state available inside the container, including the
`CODEX_HOME` volume.

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
