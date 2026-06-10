# Agentic Development System

[![CI](https://github.com/OlivierMedor/agentic-dev-system/actions/workflows/ci.yml/badge.svg)](https://github.com/OlivierMedor/agentic-dev-system/actions/workflows/ci.yml)

`agentic-dev-system` is a local-first agentic development workflow system. It
turns approved blueprints into story workspaces, separates planning,
development, testing, review, cloud review preparation, and human approval, and
keeps every step visible in files a reviewer can inspect.

The system is intentionally conservative: it does not call cloud models automatically,
does not merge, does not deploy, and does not approve its own work. Human approval remains required.

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

## Quick Demo

Run these commands from the repository root:

```powershell
docker compose build
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic project-status
docker compose run --rm dev agentic next-step --story story_034_public_launch_prep
```

The demo builds the local development container, runs tests and linting, prints
project status, and asks the CLI what should happen next for an existing story.

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
docker compose run --rm dev agentic <command>
```

Common workflow commands:

```powershell
docker compose run --rm dev agentic generate-stories
docker compose run --rm dev agentic workflow-run --story <story> --phase prepare --execute
docker compose run --rm dev agentic next-step --story <story>
docker compose run --rm dev agentic workflow-run --story <story> --phase local-finalize --execute
docker compose run --rm dev agentic workflow-run --story <story> --phase cloud-review-prep --execute
docker compose run --rm dev agentic record-cloud-review --story <story> --result-file <path>
docker compose run --rm dev agentic merge-readiness --story <story>
docker compose run --rm dev agentic project-status
```

Local validation and hygiene:

```powershell
docker compose build
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic artifact-policy
docker compose run --rm dev agentic public-readiness
docker compose run --rm dev agentic runtime-config validate
```

Local model runtime checks:

```powershell
docker compose run --rm dev agentic local-model validate
docker compose run --rm dev agentic local-model dry-run
docker compose run --rm dev agentic local-agent run-prompt --prompt-file prompt.md --output-file reports/local_agent_output.md
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-agent draft --story story_045_local_agent_draft_runner --agent docs_agent --model-label gemma-4-26b --prompt-mode slim --force
docker compose run --rm dev agentic local-model scorecard-create
docker compose run --rm dev agentic local-model scorecard-report
docker compose run --rm dev agentic local-model scorecard-scaffold-scores
docker compose run --rm dev agentic local-model scorecard-recommend
```

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
validation, queue handling, public-readiness checks, and project status
reporting.

LangGraph is currently used for safe local `workflow-preview` and
`workflow-run` phases. It is not an autonomous agent executor.

Local OpenAI-compatible models can be configured for bounded draft and dry-run
work through LM Studio or Ollama. Use `docs/local_model_scorecard.md` to compare
local models on repeatable agent-style prompts before assigning them to roles.
Use `docs/local_model_role_assignment.md` for the manual scoring and role
assignment process. Use `docs/local_agent_drafts.md` to save story context as
reviewable local drafts, and `docs/local_agent_context_packets.md` for slim
local-model context packets. See `docs/local_models.md` for setup.

For release and repository hygiene, use `docs/public_launch_checklist.md`,
`docs/release_process.md`, `docs/v0_1_release_checklist.md`,
`docs/release_notes_v0_1.md`, and `CHANGELOG.md`.

## Safety Model

The safety model is deliberately boring: the CLI prepares local artifacts,
records evidence, and reports status. It does not:

- Call cloud models automatically.
- Run generated prompts automatically.
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
  packets and truncation warnings for local models.
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
