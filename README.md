# Agentic Development System

This is a reusable tool for preparing software projects for an agentic development workflow.

## Current goal

The first version creates the standard project structure:

- `.agentic/`
- `blueprints/`
- `stories/`
- `src/`
- `tests/`
- `docs/`

## Why this exists

The system is designed so that a project can start from a blueprint, create story workspaces, assign agents, collect reports, and prepare review bundles for human/cloud review.

## Try it on a sandbox project

From this repo:

```powershell
docker compose run --rm agentic agentic init --project /sandbox-product