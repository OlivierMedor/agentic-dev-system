# Agentic Development System

[![CI](https://github.com/OlivierMedor/agentic-dev-system/actions/workflows/ci.yml/badge.svg)](https://github.com/OlivierMedor/agentic-dev-system/actions/workflows/ci.yml)

`agentic-dev-system` is a local-first agentic development workflow system. It
turns approved blueprints into story workspaces, separates planning,
development, testing, review, cloud review preparation, and human approval, and
keeps every step visible in files a reviewer can inspect.

The system is intentionally conservative: it does not call cloud models automatically
for manual cloud review, does not merge, does not deploy, and does not approve
its own work. Automatic Codex execution is disabled by default and must be
enabled explicitly in local runtime config. Human approval remains required.

It uses Docker, Python, pytest, Ruff, GitHub Actions, and LangGraph-safe
workflow phases. LangGraph is used for deterministic local workflow phases, not
for autonomous agent execution.

## Workflow At A Glance

```text
Blueprint
  |
  v
agentic generate-stories
  |
  v
agentic workflow-run --phase prepare --execute
  |
  v
micro-readiness sizing guidance
  |
  v
configured agent runtime
  |
  v
agentic workflow-run --phase local-finalize --execute
  |
  v
agentic workflow-run --phase cloud-review-prep --execute
  |
  v
human/cloud review
  |
  v
human merge decision
```

For diagrams of the full system, see `docs/system_map.md`. For the
beginner-friendly operator flow, see `docs/golden_path.md`.
For the manual-first cloud escalation queue, see
`docs/cloud_queue_operator_guide.md`. For the local repair-loop orchestrator,
see `docs/local_repair_loop.md`.

## Quick Demo

Run these commands from the repository root:

```powershell
docker compose build
docker compose run --rm dev which codex
docker compose run --rm dev codex --version
docker compose run --rm dev codex exec --help
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic project-status
docker compose run --rm dev agentic next-step --story story_034_public_launch_prep
```

The demo builds the local development container, confirms the Codex CLI is
available inside Docker, runs tests and linting, prints project status, and asks
the CLI what should happen next for an existing story.

## Try The Minimal Demo

For a small public-safe toy project, follow `docs/demo_walkthrough.md`. It shows
how `examples/minimal_project/` moves from demo blueprint to generated story
workspace, prepare phase, prompt pack, and review evidence without cloud models,
secrets, or deployment.

## Why This Project Matters

Agent-assisted development is easiest to trust when plans, prompts, checks, and
handoffs are not scattered across chat history. This repo keeps those pieces in
predictable places:

- `blueprints/` holds planned stories.
- `stories/` holds one workspace per story.
- `src/agentic_dev/` holds the CLI implementation.
- `tests/` holds automated checks.
- `docs/` holds public workflow documentation.
- `.agentic/` holds local runtime config and ignored queue state.

The goal is not to remove the human owner. The goal is to make every story
traceable from plan to tests to review evidence, so reviewers can see what was
requested, what changed, what passed, what still needs human judgment, and what
must stay local.

## Core Commands

Run commands from the repo root through Docker:

```powershell
docker compose run --rm dev agentic COMMAND
```

Common workflow commands:

```powershell
docker compose run --rm dev agentic generate-stories
docker compose run --rm dev agentic workflow-run --story STORY_SLUG --phase prepare --execute
docker compose run --rm dev agentic next-step --story STORY_SLUG
docker compose run --rm dev agentic build-context --story STORY_SLUG --all --force
docker compose run --rm dev agentic codex-task create --story STORY_SLUG --all --force
docker compose run --rm dev agentic workflow-run --story STORY_SLUG --phase local-finalize --execute
docker compose run --rm dev agentic workflow-run --story STORY_SLUG --phase cloud-review-prep --execute
docker compose run --rm dev agentic cloud-queue create --story STORY_SLUG --title "Explain the blocker"
docker compose run --rm dev agentic cloud-queue export --all-ready
docker compose run --rm dev agentic cloud-queue import --file OUTPUT_FILE
docker compose run --rm dev agentic record-cloud-review --story STORY_SLUG --result-file OUTPUT_FILE
docker compose run --rm dev agentic merge-readiness --story STORY_SLUG
docker compose run --rm dev agentic project-status
```

`workflow-run --phase prepare --execute` runs `prepare-story`,
`micro-readiness`, and `workflow-preview`. The micro-readiness result helps
choose micro, slim, or stronger configured agent runtime usage before generated
prompts are run.

`finalize-story`, `review-bundle`, and `workflow-run --phase local-finalize`
use the project `default_base_ref` from `.agentic/agent_runtime.yaml` when it is
set, then fall back to `origin/main`. The selected base ref must resolve; the
CLI does not silently substitute a different branch.
Pass `--base-ref` to override the project default explicitly.

Local validation and hygiene:

```powershell
docker compose build
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic artifact-policy
docker compose run --rm dev agentic public-readiness
docker compose run --rm dev agentic runtime-config validate
docker compose run --rm dev agentic micro-readiness --story STORY_SLUG
```

Local model runtime checks:

```powershell
docker compose run --rm dev agentic local-model validate
docker compose run --rm dev agentic local-execute --story STORY_SLUG --dry-run
docker compose run --rm dev agentic local-execute --story STORY_SLUG --role documentation
docker compose run --rm dev agentic local-execute --story STORY_SLUG --resume
docker compose run --rm dev agentic demo-subtasks --mode fake --scenario success
docker compose run --rm dev agentic demo-subtasks --mode fake --scenario resume --keep-workspace
docker compose run --rm dev agentic demo-subtasks --mode local --scenario success
docker compose run --rm dev agentic local-model dry-run
docker compose run --rm dev agentic local-agent run-prompt --prompt-file prompt.md --output-file reports/local_agent_output.md
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-agent draft --story story_045_local_agent_draft_runner --agent docs_agent --model-label gemma-4-26b --prompt-mode slim --force
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-agent draft --story story_045_local_agent_draft_runner --agent docs_agent --model-label gemma-4-26b --prompt-mode micro --force
docker compose run --rm dev agentic local-model scorecard-create
docker compose run --rm dev agentic local-model scorecard-report
docker compose run --rm dev agentic local-model scorecard-scaffold-scores
docker compose run --rm dev agentic local-model scorecard-recommend
```

`agentic local-execute` uses the assigned agents from `agent_plan.yaml`, so
blueprint-defined agents remain authoritative. Each assigned agent may carry
optional `role`, `model`, and `writable_paths` metadata in `agent_plan.yaml`.
Model resolution is: blueprint role override, runtime role default, global
local-model default, then blocked if unresolved. The command reuses role
context packets, records per-role audit artifacts and resumable execution
state, enforces writable paths before applying files, and does not fall back to
Codex or cloud code-generation. When a blueprint declares `subtasks`, the same
command executes dependency-ready, context-safe sub-tasks only after the full
required prompt fits the task's usable local-model input budget. Oversized
sub-tasks are blocked for cloud redecomposition instead of being trimmed or
split locally. Cloud review remains manual, and local repair loops are handled
by Story 069.

`agentic cloud-queue` is the manual-first path for local blockers. It packages
requests, exports batches, imports manual responses, classifies them
independently, and records checksum-locked approvals without paid API calls or
automatic application of imported content.

`agentic demo-subtasks` is the Story 062 operator proof for that same sub-task pipeline. It creates a disposable Python sandbox, seeds a blueprint-defined calculator fixture, and then runs the shared Story 061 parser, dependency graph, readiness checks, context assembly, context-fit gate, writable-path enforcement, handoff persistence, resume state, and final requirement validation. `--mode fake` is deterministic and CI-safe. `--mode local` uses only the configured local OpenAI-compatible runtime and never falls back to cloud or Codex execution. Supported scenarios are `success`, `oversized`, `resume`, and `dependency-failure`. By default the sandbox is deleted automatically. Use `--keep-workspace` only when you need to inspect the preserved sandbox path.

For review readiness, `agentic quality-gate --mode pre-merge` still checks the committed story evidence and review bundle. Story 062 also adds `agentic quality-gate --mode post-merge`, which is a clean-checkout verification path that regenerates current pytest and Ruff evidence, reruns policy and runtime-config checks, does not require committed runtime review artifacts, and fails if the checkout becomes dirty.

## Learn The Codebase

Start with `docs/code_tour.md` for a beginner-friendly tour of the repository.
Use `docs/command_map.md` to connect each `agentic` command to its CLI entry,
core module, tests, and related story workspace.

## Contributing And Security

Before proposing changes, read `CONTRIBUTING.md`. For secrets, credentials,
private prompts, or vulnerability reports, read `SECURITY.md` and do not open a
public issue.

## Portfolio / Interview Guide

For a public-facing explanation of the project, use
`docs/portfolio_case_study.md`. For interview preparation, use
`docs/interview_talking_points.md` and `docs/skills_matrix.md`.

## Current Status

This repository is public and under active development. It is a
portfolio-ready v0.1 / early public version of the local workflow, with story
generation, agent assignment, prompt packs, prepare, test-layer checks, review
bundles, quality gates, local finalization, manual cloud review packet
preparation, cloud review result recording, merge readiness, runtime config
validation, queue handling, public-readiness checks, project status reporting,
and bounded local-model execution for blueprint-selected roles.

LangGraph is currently used for safe local `workflow-preview` and
`workflow-run` phases. It is not an autonomous agent executor.

Local OpenAI-compatible models can be configured for bounded draft and dry-run
work through LM Studio or Ollama. Use `docs/local_model_scorecard.md` to compare
local models on repeatable agent-style prompts before assigning them to roles.
Use `docs/local_model_role_assignment.md` for the manual scoring and role
assignment process. Use `docs/local_agent_drafts.md` to save story context as
reviewable local drafts, and `docs/local_agent_context_packets.md` for slim and
micro local-model context packets. Use micro mode when Gemma returns hidden
`reasoning_content` but empty visible content. See `docs/local_models.md` for
setup. See `docs/local_repair_loop.md` for the local-only retry loop that
validates outputs, reruns checks, and writes manual support evidence when the
retry budget is exhausted.

Use `docs/micro_readiness.md` to interpret story sizing guidance. Warnings mean
local models may need micro mode, slim mode, a stronger configured agent
runtime, or a story split; they are not automatic workflow failures.
Use `docs/role_context_builder.md` to build focused context packets for each
assigned agent before handing work to a configured runtime.
Use `docs/runtime_config.md` to understand the tiered Codex-first runtime
defaults, local-execution model resolution order, context-safe sub-task
execution, and command approval policy.
Use `docs/codex_runtime.md` to create Codex-ready task files from those role
context packets and to configure the disabled-by-default automatic Codex
adapter. The Docker smoke-check command shape is
`codex exec --sandbox workspace-write -`.
Use `docs/codex_task_execution.md` to run generated Codex task files manually or
through the enabled adapter, one role at a time, without committing generated
runtime artifacts.

The Docker `dev` image installs the Codex CLI. Verify it with
`docker compose run --rm dev which codex` and
`docker compose run --rm dev codex --version`, then check command compatibility
with `docker compose run --rm dev codex exec --help`. The automatic adapter
feeds generated task file content through stdin.

Default safe runtime:
`codex exec --sandbox workspace-write -`

`codex exec` accepts `-` to read from stdin and is read-only by default, so
agentic prefers `workspace-write` when it works. That lets Codex create the
required story report files inside the mounted workspace without dropping the
inner Codex sandbox. The installed CLI help should confirm that this command
shape remains supported.

Some Docker environments cannot start Codex's inner Linux sandbox and fail with
`bwrap: No permissions to create a new namespace`. When that happens, the only
supported fallback is an explicit Docker-isolated config.

Docker-compatible fallback:
`codex exec --sandbox danger-full-access -`

Requires:
`docker_isolation_acknowledged: true`

That mode is disabled by default and rejected unless the acknowledgement flag
is true. In that fallback, Docker becomes the isolation boundary, Codex can
read and write the mounted workspace, and Codex may access auth state inside
the container. Use it only for trusted repos and controlled local automation.
The runner still does not merge, push, force-push, deploy, open PRs, or call
GitHub APIs.

Authentication is not baked into the image and credentials are not stored in the
repo; see
`docs/codex_docker_runtime.md` for device-code login, Docker volume storage,
and one-off `CODEX_API_KEY` usage. If Codex is unavailable, automatic execution
blocks safely with `BLOCKED_CODEX_COMMAND_NOT_FOUND`.

## Tiered Codex Runtime Defaults

`.agentic/agent_runtime.yaml` is the source of truth for agent provider and
model choices. Blueprints describe the story work. For `agentic local-execute`,
Story 060 adds a narrow blueprint override path for the local model assigned to
an already-selected role.

Codex is the primary runtime because this workflow is centered on repository
changes, tests, review evidence, and local safety rules. The default worker tier
is `gpt-5.4` for planner, developer, and test roles. Lighter research and docs
roles use `gpt-5.4-mini`. High-risk security, final local review, DeFi,
risk-sensitive work, and final judgment use `gpt-5.5`. `cloud_reviewer` remains
a manual handoff to `main_cloud_model`, and Gemma remains available only as an
optional `local_model_helper` micro-mode draft helper.

For release and repository hygiene, use `docs/public_launch_checklist.md`,
`docs/release_process.md`, `docs/v0_1_release_checklist.md`,
`docs/release_notes_v0_1.md`, and `CHANGELOG.md`.

## Safety Model

The safety model is deliberately boring: the CLI prepares local artifacts,
records evidence, and reports status. It does not:

- Call cloud models automatically.
- Run generated prompts automatically outside the configured runtime adapters.
- Commit, push, merge, or deploy automatically.
- Change GitHub repository visibility.
- Approve pull requests or merge readiness on behalf of the human owner.
- Track secrets, `.env` files, generated review artifacts, or local queue
  runtime files.

Cloud review is a manual handoff. The system can prepare
`cloud_review_export.md`, but a human decides whether to send it to a model,
records the result, reviews the PR, and decides whether to merge.

Private local operator guidance belongs in `blueprints/agentic-architecture.md`.
That file is ignored and blocked by policy. The public-safe example is
`blueprints/agentic-architecture.example.md`.

## Public Docs

- `docs/system_map.md` explains the system with ASCII diagrams.
- `docs/golden_path.md` walks through the normal blueprint-to-PR-review path.
- `docs/code_tour.md` explains the repository structure in beginner-friendly
  language.
- `docs/command_map.md` maps commands to code, tests, and related stories.
- `docs/public_readiness.md` explains what must stay out of Git before a public
  release.
- `docs/public_launch_checklist.md` is the manual checklist for public repo and
  release hygiene.
- `docs/local_models.md` explains local OpenAI-compatible runtime setup with LM
  Studio, Ollama, and safety boundaries.
- `docs/local_agent_drafts.md` explains save-only local draft reports from story
  context or prompt-pack files.
- `docs/local_agent_context_packets.md` explains slim local-agent context
  packets, micro final-answer-focused packets, and truncation warnings for local
  models.
- `docs/local_repair_loop.md` explains the local-only repair loop orchestrator
  and its manual support fallback.
- `docs/micro_readiness.md` explains how to check whether assigned agent tasks
  are small enough for micro-mode local prompts.
- `docs/role_context_builder.md` explains focused role context packets for
  assigned story agents.
- `docs/runtime_config.md` explains tiered Codex-first runtime defaults and
  local-execution model resolution.
- `docs/codex_runtime.md` explains Codex-ready task files generated from role
  context packets.
- `docs/codex_docker_runtime.md` explains the supported Docker Codex CLI and
  authentication setup.
- `docs/codex_task_execution.md` explains safe manual execution of generated
  Codex task files, one role at a time.
- `docs/local_model_scorecard.md` explains how to compare local models on the
  same public-safe agent-style prompts before role assignment.
- `docs/local_model_role_assignment.md` explains manual local model scoring,
  role assignment, and safety boundaries.
- `docs/release_process.md` explains how PR merges differ from GitHub releases
  and what checks are required before a release.
- `docs/v0_1_release_checklist.md` is the manual checklist for the v0.1
  milestone.
- `docs/release_notes_v0_1.md` summarizes the v0.1 release scope.
- `CHANGELOG.md` summarizes public release changes.
- `docs/github_metadata.md` suggests GitHub description, topics, website field,
  and manual setup steps.
- `docs/repo_settings.md` suggests public repo settings and links to metadata
  guidance.
- `docs/langgraph_workflow.md` explains the current LangGraph preview and safe
  workflow-run phases.
- `docs/ci_cd.md` explains CI behavior.
- `docs/portfolio_case_study.md` explains the project as a professional
  engineering case study.
- `docs/interview_talking_points.md` provides interview-ready project
  narratives and suggested answers.
- `docs/skills_matrix.md` maps project skills to repo evidence and interview
  talking points.

## License

The repository owner still controls the license decision. No `LICENSE` file is
added automatically unless the owner explicitly requests it. Until a license is
added, default copyright applies and outside reuse is not granted automatically.
