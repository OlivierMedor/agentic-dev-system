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

## Validate test layers

Run this from the repo root to check that a story test plan addresses every standard testing
layer:

```powershell
docker compose run --rm dev agentic test-layers --story story_014_test_layer_support
```

Story test plans that use `test_layers_version: 1` must address `unit_tests`,
`integration_tests`, `mock_e2e_tests`, `live_read_only_checks`, and
`remote_dev_smoke_tests`. Each layer declares whether it is required, which action was taken or
planned, how often it should run, and the evidence or reason.

Actual tests live in project-level test folders such as `tests/`; `stories/<story>/test_plan.yaml`
declares the coverage plan for review. Not every story needs a new test in every layer, but every
story using the schema must address every layer. If a layer does not apply, use
`not_applicable_with_reason` or `scheduled_later_with_reason` and explain why.

The command writes `stories/<story>/reports/test_layer_result.yaml` and
`stories/<story>/reports/test_layer_report.md`. When a test layer result exists, the quality gate
requires it to have `status: PASSED`. When `test_plan.yaml` uses `test_layers_version: 1`, the
quality gate requests changes if the test layer result is missing.

See `docs/test_layers.md` for the schema and layer definitions.

## Mock E2E testing

Mock E2E tests exercise the full local workflow with temporary projects, fake data, and local
doubles instead of live APIs, cloud models, browser tooling, deployed environments, or a real Git
repository. Project-level mock E2E tests live in `tests/e2e/`; story `test_plan.yaml` files declare
whether mock E2E coverage is required.

See `docs/e2e_testing.md` for the test layer definitions and the recommended mock workflow pattern.

## Finalize a story

Run this from the repo root after agent work and local review are complete:

```powershell
docker compose run --rm dev agentic finalize-story --story story_008_finalize_story_command
```

The command validates that `stories/<story>/` exists, creates or refreshes the review bundle,
validates test layers when `test_plan.yaml` uses `test_layers_version: 1`, runs the quality gate,
regenerates the review bundle so final evidence is captured, writes
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
`cloud_review_prompt.md`, `cloud_review_context.md`, `cloud_review_checklist.md`,
`cloud_review_result_template.md`, and `cloud_review_export.md` into
`stories/<story>/cloud_review_packet/`. The context includes story content plus available quality
gate, finalize, review bundle, Git status, diff stat, and untracked-file evidence. Missing
optional evidence is listed in the context instead of causing failure.

Use `cloud_review_export.md` as the single file to paste or upload to the main cloud model.

Use `--force` when you intentionally want to overwrite existing cloud review packet files. The
command does not call cloud models, commit, push, merge, or deploy.

## Record a cloud review result

After the main cloud model returns its answer, save that answer to a local Markdown file and record
the decision:

```powershell
docker compose run --rm dev agentic record-cloud-review --story story_010_cloud_review_packet --result-file docs/cloud_review_answer.md
```

The result file must contain exactly one accepted decision, preferably on a line such as
`Decision: APPROVE`. Accepted decisions are `APPROVE`, `APPROVE_WITH_NOTES`, and
`REQUEST_CHANGES`.

The command writes `stories/<story>/reports/cloud_review_result.yaml` and
`stories/<story>/reports/cloud_review_report.md`, then updates `status.yaml` with the cloud review
decision. `APPROVE` and `APPROVE_WITH_NOTES` mark the story ready for a human merge decision;
`REQUEST_CHANGES` marks the story as needing changes. The command does not call cloud models,
commit, push, merge, or deploy, and cloud review is not automatic merge approval.

The full cloud review workflow is:

1. Run `finalize-story`.
2. Run `cloud-review-packet`.
3. Paste or upload `stories/<story>/cloud_review_packet/cloud_review_export.md` to the main cloud model.
4. Save the cloud model answer to a local Markdown file.
5. Run `record-cloud-review --story <story> --result-file <path>`.
6. Have the human owner decide whether to merge.

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
docker compose run --rm dev agentic test-layers --story story_014_test_layer_support
```

## Continuous integration

GitHub Actions runs the `CI` workflow on pull requests targeting `main`, pushes to `main`, and pushes to `story/**` branches. The workflow builds the Docker Compose environment, runs pytest and Ruff inside the `dev` container, runs `agentic generate-stories`, fails if generated story files are missing or stale, and runs `agentic artifact-policy`.

See `docs/ci_cd.md` for the full CI behavior and failure-handling notes.
