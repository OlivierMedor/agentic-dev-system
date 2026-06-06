# STORY-037: Minimal Demo Project + Walkthrough

## Goal

Create a small public demo project and walkthrough that shows how a user can run the agentic-dev-system on a simple toy project.

## Why This Matters

New users need a safe, concrete example that maps the real workflow to a tiny project without secrets, cloud model calls, deployment, databases, wallets, or private strategy logic.

## Acceptance Criteria

- Add Story 037 to blueprints/blueprint.yaml.
- Add docs/demo_walkthrough.md.
- Add examples/minimal_project/.
- Update README.md to link to docs/demo_walkthrough.md.
- Add tests that verify the demo files and docs exist.
- examples/minimal_project/README.md exists.
- examples/minimal_project/blueprints/blueprint.yaml exists.
- The sample blueprint describes a tiny fake project such as building a simple task tracker CLI using mock data.
- The sample blueprint contains a stories list.
- The demo does not require real APIs, cloud model calls, secrets, deployment, databases, wallets, or private strategy logic.
- The walkthrough explains what the demo is, why it exists, how it maps to the real workflow, how to run it safely, and what files to inspect afterward.
- The walkthrough includes the requested ASCII workflow visual.
- The walkthrough documents the required Docker and agentic commands.
- If the current workflow cannot fully finalize the demo without agent reports, the walkthrough explains that clearly.
- Do not fake a completed story.
- Do not add secrets, .env files, generated review bundles, cloud review packets, remote dev validation artifacts, support queue runtime tickets, feature scan runtime files, or large files.

## Not In Scope

- No new CLI behavior.
- No cloud model calls.
- No automatic merge, deployment, repository visibility change, or approval.
- No real external services, APIs, databases, wallets, or secrets.
- No private prompts, private strategy guidance, or generated runtime artifacts.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story reports are written for development, testing, and local review.
- Review bundle is generated for Story 037 but generated bundle files are not committed.
