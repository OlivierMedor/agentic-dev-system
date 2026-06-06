# Release Notes v0.1

v0.1 is the early public, portfolio-ready version of `agentic-dev-system`. It
focuses on a conservative local workflow for planning, preparing, validating,
and reviewing story-based work without automatic cloud model calls, merges, or
deployments.

## Included

- Blueprint-to-story workflow for turning approved blueprint entries into story
  workspaces.
- Story workspaces with story files, plans, prompt packs, reports, status, and
  review evidence locations.
- Agent prompt packs for research, planning, development, testing, docs,
  security/quality, and local review roles.
- Local review bundles for reviewer handoff.
- Local quality gates that check required reports, test evidence, local review
  readiness, and validation outcomes.
- Test layers that document unit, integration, mock E2E, live read-only, and
  remote dev smoke test expectations.
- Support, improvement, maintenance, and feature queues for structured follow-up
  work.
- Public-readiness guard for preventing tracked private guidance, secrets,
  generated runtime artifacts, and queue runtime files.
- Minimal demo project and walkthrough under `examples/minimal_project/` and
  `docs/demo_walkthrough.md`.
- Code tour and command map docs for understanding the repository and CLI
  surface.
- LangGraph workflow-preview and workflow-run phases for deterministic local
  prepare, local-finalize, and cloud-review-prep orchestration.

## Not Included Yet

- Automatic cloud model execution.
- Autonomous agent execution from generated prompts.
- Automatic GitHub metadata setup, repository visibility changes, PR approval,
  merge, deployment, or package publishing.
- A production release bundle.
- A committed license decision or `LICENSE` file.
- Full remote development deployment automation.
- Real external service integrations for the minimal demo.
