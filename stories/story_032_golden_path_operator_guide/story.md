# STORY-032: Golden Path Operator Guide

## Goal

Create beginner-friendly operator documentation that explains how to use the
agentic-dev-system from blueprint to PR merge decision.

## Why

The project now has several workflow commands and review artifacts. Operators
need one plain-language guide that explains what each major artifact means, how
the normal path works, and where human approval is still required.

## Acceptance criteria

- Add `docs/golden_path.md`.
- Update `README.md` to link to `docs/golden_path.md`.
- Update `docs/langgraph_workflow.md` if needed.
- Add or update tests that verify `docs/golden_path.md` exists.
- Tests confirm the guide mentions the core commands.
- Tests confirm `README.md` links to `docs/golden_path.md`.
- The guide explains what the system is.
- The guide explains what lives in the project repo.
- The guide explains what lives in `.agentic/`.
- The guide explains what stories are.
- The guide explains what review bundles are.
- The guide explains what cloud review packets are.
- The guide explains what workflow-run phases are.
- The guide explains how support, improvement, maintenance, and feature queues differ.
- The guide explains the normal happy path.
- The guide explains what to do when a story is blocked.
- The guide explains what to do when tests or logs fail.
- The guide explains what not to commit.
- The guide explains what the human owner must still approve.
- The guide uses plain language and ASCII diagrams.
- Do not add new automation commands unless absolutely necessary.
- Do not change workflow behavior unless a documentation test requires a tiny supporting change.

## Not in scope

- No new CLI commands.
- No workflow behavior changes.
- No automatic cloud model calls.
- No GitHub API automation beyond any manually created PR.
- No merge, deployment, or auto-approval behavior.

## Definition of done

- `pytest` passes.
- `ruff check .` passes.
- `agentic artifact-policy` passes.
- `agentic runtime-config validate` passes.
- `agentic project-status` runs.
- Story reports are written for development, testing, docs, and local review.
