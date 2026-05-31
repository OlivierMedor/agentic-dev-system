# Agentic Development System

This repo contains a small reusable CLI for preparing a project to use an agentic development workflow.

## What it does

The CLI can initialize a target project, generate story workspaces from a blueprint, and create review bundles.

- `.agentic/`
- `blueprints/`
- `stories/`
- `src/`
- `tests/`
- `docs/`

It also creates the first setup story, basic project rules, quality gates, and starter instructions for the agent roles used by the workflow.
Agent runtime queues live under `.agentic/`, including the support queue used when agents are blocked and need structured cloud-model review.
Projects can also define per-agent runtime behavior in `.agentic/agent_runtime.yaml`.

## Runtime config

The runtime config is a project-level YAML file at `.agentic/agent_runtime.yaml`.
It defines:

- which provider each agent should use
- which model name is expected
- which approval mode each agent should run under
- which fallback provider to use when the preferred runtime is unavailable
- which routine commands are allowed without repeated approval
- which risky commands must always require human approval

The default config includes all core agents, a `cloud_reviewer` with
`provider: manual_cloud_model`, and support for the future
`local_model_optional` provider type.

## Story sizing

User stories should be narrow enough to have clear acceptance criteria and a focused code change, but large enough to justify the full agent workflow: Research, Planner, Developer, Test, Docs, Security/Quality, and Reviewer. If only one agent has meaningful work, the story is probably too small. If the story touches many unrelated features or modules, it is probably too large.

## Why this exists

The goal is to make agent-assisted development repeatable. A project can start from a blueprint, organize work into stories, collect agent reports, and prepare review bundles for human or cloud review.

## Try it on a sandbox project

Run this from the repo root:

```powershell
docker compose run --rm dev agentic init
```

This initializes the current project folder inside the container. Use `--project /sandbox-product` when you want to initialize the separate sandbox project mounted at `/sandbox-product`.

## Generate story workspaces

Run this from the repo root to create story folders from `blueprints/blueprint.yaml`:

```powershell
docker compose run --rm dev agentic generate-stories
```

Use `--project` to target another project folder or `--blueprint` to use a different blueprint file.

## Assign agents to a story

Run this from the repo root to create an execution map for a story:

```powershell
docker compose run --rm dev agentic assign-agents --story story_004_agent_assignment
```

The command writes `stories/<story>/agent_plan.yaml`. That file is the story's execution map: it lists the core agent team, their execution order, each agent's instruction file, and each expected report output.

Use `--force` when you intentionally want to regenerate an existing `agent_plan.yaml`.

## Generate prompt packs

Run this from the repo root to create Codex-ready prompts for each assigned agent in a story:

```powershell
docker compose run --rm dev agentic generate-prompts --story story_006_agent_prompt_packs
```

The command reads the story file, agent plan, test plan, monitoring plan, project rules, and quality gates. It writes one prompt per assigned agent into `stories/<story>/prompt_pack/`.

Use `--force` when you intentionally want to overwrite existing prompt files.
When `.agentic/agent_runtime.yaml` is present, the generated prompt files also include the
runtime config content and a short per-agent runtime expectation summary with provider, model,
approval mode, and fallback provider.

## Inspect runtime config

Print the current project runtime config:

```powershell
docker compose run --rm dev agentic runtime-config show
```

Validate that the runtime config has the required agents, known provider types, known approval
modes, and human-approval coverage for risky commands:

```powershell
docker compose run --rm dev agentic runtime-config validate
```

## Prepare a story

Run this from the repo root to prepare a story for agent execution:

```powershell
docker compose run --rm dev agentic prepare-story --story story_007_prepare_story_command
```

The command validates that `stories/<story>/` exists, creates `agent_plan.yaml` when missing,
generates prompt files in `stories/<story>/prompt_pack/`, writes `story_runbook.md`, writes
`reports/prepare_story_report.md`, and updates `status.yaml` to `prepared` with
`ready_for_review: false`.

Use `--force` when you intentionally want to refresh an existing `agent_plan.yaml` and overwrite
existing prompt files. The command does not execute agents, run cloud models, create a review
bundle, or run the quality gate.

## Create a review bundle

Run this from the repo root to collect review files for a story:

```powershell
docker compose run --rm dev agentic review-bundle --story story_003_generate_stories_from_blueprint
```

The command writes Git status, recent commits, unstaged changes, staged changes, test output, lint output, a file tree, and a short handoff into the story's `review_bundle/` folder. It also records untracked file lists and safe text snapshots for untracked files so reviewers can see newly created files before they are staged.

## Run a quality gate

Run this from the repo root to decide whether a story is ready for human or cloud review:

```powershell
docker compose run --rm dev agentic quality-gate --story story_005_quality_gate
```

The command checks that required story files, agent reports, review bundle files, passing pytest output, passing Ruff output, and local reviewer approval are present. It writes `stories/<story>/reports/quality_gate_result.yaml` and `stories/<story>/reports/quality_gate_report.md` with either `READY_FOR_REVIEW` or `REQUEST_CHANGES`.

## Finalize a story

Run this from the repo root after agent work and local review are complete:

```powershell
docker compose run --rm dev agentic finalize-story --story story_008_finalize_story_command
```

The command validates that `stories/<story>/` exists, creates or refreshes the review bundle,
runs the quality gate, regenerates the review bundle so final evidence is captured, writes
`stories/<story>/reports/finalize_story_result.yaml`, writes
`stories/<story>/reports/finalize_story_report.md`, and updates `status.yaml`.

If the quality gate returns `READY_FOR_REVIEW`, `status.yaml` is updated to
`status: ready_for_review` with `ready_for_review: true`. If the quality gate returns
`REQUEST_CHANGES`, `status.yaml` is updated to `status: request_changes` with
`ready_for_review: false`. The command does not commit, push, merge, deploy, or call cloud
models.

## Create a cloud review packet

Run this from the repo root to prepare a cloud-model-ready packet for a completed story:

```powershell
docker compose run --rm dev agentic cloud-review-packet --story story_010_cloud_review_packet
```

The command validates that `stories/<story>/` and `story.md` exist, then writes
`cloud_review_prompt.md`, `cloud_review_context.md`, `cloud_review_checklist.md`, and
`cloud_review_result_template.md` into `stories/<story>/cloud_review_packet/`. The context
includes story content plus available quality gate, finalize, review bundle, Git status, diff stat,
and untracked-file evidence. Missing optional evidence is listed in the context instead of causing
failure.

Use `--force` when you intentionally want to overwrite existing cloud review packet files. The
command does not call cloud models, commit, push, merge, or deploy.

## Use the support queue

Run this from the repo root when an agent is blocked and needs a structured answer:

```powershell
docker compose run --rm dev agentic support-ticket create --story story_012_agent_support_queue --agent developer_agent --blocker-type requirements --question "Should the ticket answer command move or copy the file?"
```

The command writes a YAML ticket into `.agentic/support_queue/pending/` and, when the matching
story folder exists, updates `stories/<story>/status.yaml` to `status: blocked` with
`ready_for_review: false` and `blocked_by: <ticket_id>`.

List the queue at any time:

```powershell
docker compose run --rm dev agentic support-ticket list
```

Create a cloud-model-ready support packet without calling any APIs:

```powershell
docker compose run --rm dev agentic support-ticket cloud-packet --ticket SUPPORT-20260530-120000
```

The packet is written next to the ticket as Markdown and instructs the cloud model to return one
of `ANSWER`, `NEEDS_HUMAN`, or `REQUEST_MORE_CONTEXT` while using only the ticket context.

Record a response from a file and move the ticket into `.agentic/support_queue/answered/`:

```powershell
docker compose run --rm dev agentic support-ticket answer --ticket SUPPORT-20260530-120000 --answer-file docs/support_answer.md
```

Close a ticket when no further queue work is needed:

```powershell
docker compose run --rm dev agentic support-ticket close --ticket SUPPORT-20260530-120000
```

The support queue creates runtime YAML and Markdown files only. It does not call cloud APIs,
notify humans, resume agents automatically, or trigger Codex execution.

## Check generated artifact policy

Run this from the repo root to verify generated review artifacts and environment files are not
tracked by Git:

```powershell
docker compose run --rm dev agentic artifact-policy
```

The command uses `git ls-files` and fails if tracked files include generated review bundle files,
generated cloud review packet files, support queue runtime YAML or Markdown files,
`review_to_chatgpt/`, zip files, `.env`, or `.env.*` files. It allows `.gitkeep` inside generated
artifact folders and `.env.example`.

## Local checks

```powershell
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic artifact-policy
```

## Continuous integration

GitHub Actions runs the `CI` workflow on pull requests targeting `main`, pushes to `main`, and pushes to `story/**` branches. The workflow builds the Docker Compose environment, runs pytest and Ruff inside the `dev` container, runs `agentic generate-stories`, fails if generated story files are missing or stale, and runs `agentic artifact-policy`.

See `docs/ci_cd.md` for the full CI behavior and failure-handling notes.
