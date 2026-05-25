# Agentic Development System

This repo contains a small reusable CLI for preparing a project to use an agentic development workflow.

## What it does

The current command initializes a target project with a standard structure:

- `.agentic/`
- `blueprints/`
- `stories/`
- `src/`
- `tests/`
- `docs/`

It also creates the first setup story, basic project rules, quality gates, and starter instructions for the agent roles used by the workflow.

## Why this exists

The goal is to make agent-assisted development repeatable. A project can start from a blueprint, organize work into stories, collect agent reports, and prepare review bundles for human or cloud review.

## Try it on a sandbox project

Run this from the repo root:

```powershell
docker compose run --rm agentic agentic init --project /sandbox-product
```

This initializes the separate sandbox project mounted at `/sandbox-product`. The tool repo stays separate from the project being prepared.
