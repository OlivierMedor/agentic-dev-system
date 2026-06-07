# Changelog

All notable public release changes are summarized here. This project uses this
file as a human-reviewed companion to GitHub release notes; it does not create
GitHub releases automatically.

## v0.1.0 - Unreleased

Initial public release candidate for the local-first agentic development
workflow system.

### Added

- Blueprint-to-story workflow for turning approved blueprint entries into
  traceable story workspaces.
- Story workspaces with story files, status, plans, prompts, reports, and
  review evidence locations.
- Prompt packs for research, planning, development, testing, docs,
  security/quality, and local review roles.
- Review bundles for manual reviewer handoff.
- Quality gates for story readiness checks.
- Test layers for unit, integration, mock E2E, live read-only, and remote dev
  smoke test expectations.
- Queue loops for improvement, maintenance, and feature follow-up.
- Support queue for structured blocked-agent questions and manual cloud review
  handoff.
- Public-readiness guard for tracked private guidance, secrets, generated
  runtime artifacts, and queue runtime files.
- Minimal demo project and walkthrough.
- Code tour and command map for understanding the repository and CLI surface.
- LangGraph workflow preview and workflow-run phases for deterministic local
  prepare, local-finalize, and cloud-review-prep orchestration.

### Not Included

- Automatic cloud model execution.
- Automatic deployment, package publishing, merge, or PR approval.
- Automatic GitHub release creation.
- A `LICENSE` file or automatic license decision.
