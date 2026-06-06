# Agentic Development System

`agentic-dev-system` is a local CLI and repo pattern for repeatable
agent-assisted software development. It turns an approved blueprint into story
workspaces, prepares agent prompt packs, records local evidence, creates review
handoffs, and shows when a story is ready for a human merge decision.

The system is intentionally conservative: it does not call cloud models
automatically, does not deploy, does not merge pull requests, and does not
approve its own work.

## Why It Exists

Agent-assisted development can become hard to review when plans, prompts,
checks, and handoffs are scattered. This repo keeps those pieces in predictable
places:

- `blueprints/` holds planned stories.
- `stories/` holds one workspace per story.
- `src/agentic_dev/` holds the CLI implementation.
- `tests/` holds automated checks.
- `docs/` holds public workflow documentation.
- `.agentic/` holds local runtime config and ignored queue state.

The goal is not to remove the human owner. The goal is to make every story
traceable from plan to tests to review evidence.

## Workflow At A Glance

```text
Blueprint
  |
  v
agentic generate-stories
  |
  v
stories/story_x/
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

## Current Status

This project is preparing for a future public launch. The core local workflow is
implemented for story generation, agent assignment, prompt packs, prepare,
test-layer checks, review bundles, quality gates, local finalization, manual
cloud review packet preparation, cloud review result recording, merge readiness,
runtime config validation, queue handling, public-readiness checks, and project
status reporting.

LangGraph is currently used for safe local `workflow-preview` and
`workflow-run` phases. It is not an autonomous agent executor.

Before changing repository visibility, use `docs/public_launch_checklist.md`.

## Safety Model

The CLI prepares and records evidence. It does not:

- Call cloud models automatically.
- Run generated prompts automatically.
- Commit, push, merge, or deploy automatically.
- Change GitHub repository visibility.
- Approve pull requests or merge readiness on behalf of the human owner.
- Track secrets, `.env` files, generated review artifacts, or local queue
  runtime files.

Private local operator guidance belongs in `blueprints/agentic-architecture.md`.
That file is ignored and blocked by policy. The public-safe example is
`blueprints/agentic-architecture.example.md`.

## Public Docs

- `docs/system_map.md` explains the system with ASCII diagrams.
- `docs/golden_path.md` walks through the normal blueprint-to-PR-review path.
- `docs/public_readiness.md` explains what must stay out of Git before a public
  release.
- `docs/public_launch_checklist.md` is the final manual checklist before making
  the repository public.
- `docs/langgraph_workflow.md` explains the current LangGraph preview and safe
  workflow-run phases.
- `docs/ci_cd.md` explains CI behavior.

## License

Choose a license before making the repository public. MIT is a common
permissive option, but the repository owner must decide which license fits the
project.
