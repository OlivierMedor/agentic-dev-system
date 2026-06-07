# Portfolio Case Study: Agentic Development System

## Project Overview

`agentic-dev-system` is a local-first workflow system for managing AI-assisted
software work as traceable engineering stories. It turns approved blueprint
items into story workspaces, prompt packs, reports, review bundles, quality
gates, cloud review packets, and human merge decisions.

The project is intentionally conservative. It organizes agentic coding work,
records evidence, and prepares review handoffs, but it does not call cloud
models automatically, merge pull requests, deploy software, or approve its own
changes.

## Problem Statement

AI coding tools can move quickly, but unstructured agentic work creates common
engineering risks:

- Requirements live only in chat history.
- Generated prompts are hard to audit later.
- Tests, lint checks, and review evidence are easy to skip.
- Reviewers cannot always see what the agent was asked to do.
- Safety decisions can blur when automation is allowed to proceed too far.

The project addresses those risks by making each story explicit, file-backed,
reviewable, and gated before human approval.

## Why Agentic Coding Needs Structure

Agentic coding benefits from the same discipline as human team development:
clear scope, small stories, repeatable setup, automated checks, peer review, and
explicit ownership of release decisions. Without structure, an agent can produce
code that looks complete while hiding missing tests, unclear assumptions, or
unsafe automation.

This repository treats the agent as a contributor inside a controlled process.
The workflow gives the agent context and checklists, then requires local quality
evidence and human judgment before merge.

## Solution Architecture

The system is built around a few durable repository concepts:

- `blueprints/blueprint.yaml` defines approved stories and acceptance criteria.
- `stories/` contains generated story workspaces, status files, runbooks, prompt
  packs, and reports.
- `src/agentic_dev/` contains the Python CLI modules that generate and validate
  workflow artifacts.
- `tests/` contains pytest coverage for CLI behavior, artifact policy, public
  readiness, story generation, workflow phases, and documentation checks.
- `docs/` contains public explanations of the system, workflows, and safety
  model.
- Docker and GitHub Actions provide repeatable local and CI validation.

The CLI is deliberately file-oriented. That keeps state inspectable, makes
workflow evidence easy to diff, and lets a reviewer understand a story without
needing access to private chat history.

## Workflow Diagram

```text
Idea / Blueprint
  |
  v
Story Workspaces
  |
  v
Agent Prompt Packs
  |
  v
Configured Agent Runtime
  |
  v
Review Bundle + Quality Gate
  |
  v
Cloud Review Packet
  |
  v
Human Merge Decision
```

## Key Features

- Blueprint-to-story generation for scoped work items.
- Story workspaces with status, reports, runbooks, and agent prompt packs.
- Configured agent runtime checks that keep local execution explicit.
- Review bundles that collect story context and quality evidence for reviewers.
- Quality gates that report whether a story is ready for review or needs
  changes.
- Manual cloud review packet preparation without automatic model calls.
- Artifact policy checks that block generated runtime files, secrets, and local
  private guidance from being committed.
- Public-readiness checks for repository hygiene.
- Project status and next-step commands for operational visibility.
- Documentation that explains the system to new contributors and interviewers.

## Safety Model

The safety model separates preparation from approval. The CLI can prepare
artifacts and summarize evidence, but human approval remains the final decision
point.

The system does not automatically:

- Call cloud models.
- Run generated prompts.
- Commit, push, merge, or deploy.
- Approve pull requests.
- Change GitHub repository settings.
- Track secrets, `.env` files, generated review bundles, cloud review packets,
  remote validation files, queue runtime files, or private operator guidance.

This makes automation useful without letting it cross the boundary into
unsupervised release control.

## Testing Strategy

The test suite uses pytest to cover the CLI and repository policies at multiple
levels:

- Unit-style tests validate story generation, prompt pack generation, quality
  gates, review bundles, cloud review packet preparation, runtime config, and
  artifact policy behavior.
- Documentation tests verify that public docs exist and README links stay
  current.
- Workflow tests exercise LangGraph-backed preview and run phases.
- E2E-style tests cover the local story workflow on a controlled example.

Ruff enforces style and catches common Python issues before review.

## CI/CD Strategy

GitHub Actions run the project checks in Docker so pull requests are validated
in a clean environment. The CI/CD strategy is focused on quality gates, not
deployment. It builds the development container, runs pytest, runs Ruff, checks
artifact policy, and verifies generated story consistency.

There is no production deployment pipeline in this project. That is intentional:
the repository is a workflow tool and portfolio project, and merge decisions
stay with the human owner.

## LangGraph Usage

LangGraph is used for deterministic local workflow phases such as workflow
preview and workflow run. In this project, LangGraph models the phase sequence
and state transitions; it is not used as an autonomous agent executor.

That design keeps the benefits of graph-based workflow orchestration while
preserving explicit command execution, local evidence, and human approval.

## What Is Intentionally Not Automated

The project intentionally avoids automating high-trust actions:

- No automatic cloud model calls.
- No automatic execution of generated agent prompts.
- No automatic Git commits, pushes, merges, or deployments.
- No automatic GitHub settings changes.
- No automatic PR approval.
- No secret handling beyond blocking accidental tracking.

Those limits are part of the architecture, not missing features.

## Lessons Learned

- Agentic development is easier to review when every phase writes durable
  evidence.
- Small stories and explicit acceptance criteria reduce ambiguity for both
  humans and agents.
- Safety controls should be boring, testable, and visible in CI.
- Generated artifacts are useful for review but should not become permanent
  repository history.
- LangGraph is most valuable here as deterministic workflow structure, not as a
  license for uncontrolled autonomy.

## Future Roadmap

- Broaden story lifecycle reporting while keeping generated artifacts ignored.
- Improve review bundle summaries for faster human review.
- Add more examples that show safe local-only workflows.
- Expand public documentation for contributors and interviewers.
- Continue strengthening artifact policy and public-readiness checks.
- Explore additional LangGraph phase modeling where it improves clarity without
  adding unsafe automation.
