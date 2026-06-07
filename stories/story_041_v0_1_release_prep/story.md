# STORY-041: v0.1 Release Prep and License Decision

## Goal

Prepare the public repo for a clean v0.1 milestone with release process docs, release checklist, changelog structure, release notes updates, and explicit license guidance.

## Why This Matters

The repository is public and needs a repeatable release process that separates PR review from GitHub releases, preserves human owner approval, and avoids accidentally granting reuse rights without an explicit license decision.

## Acceptance Criteria

- Add Story 041 to blueprints/blueprint.yaml.
- Add docs/release_process.md.
- Add docs/v0_1_release_checklist.md.
- Add or update docs/release_notes_v0_1.md if needed.
- Add CHANGELOG.md if helpful.
- Update README.md to link to release docs.
- Update docs/public_launch_checklist.md if needed.
- Add or update tests that verify release docs exist and README links to them.
- docs/release_process.md explains what a release means for this repo.
- docs/release_process.md explains the difference between PR merge and GitHub release.
- docs/release_process.md lists pytest, Ruff, artifact-policy, public-readiness, runtime-config validate, project-status, and GitHub Actions as required checks.
- docs/release_process.md says human owner approval is required.
- docs/release_process.md says not to deploy anything automatically.
- docs/release_process.md says not to call cloud models automatically.
- docs/v0_1_release_checklist.md includes required v0.1 docs, contribution/security files, issue templates, public-readiness, license decision, GitHub metadata, CI, and release notes review.
- CHANGELOG.md includes a v0.1.0 unreleased or initial public release section.
- CHANGELOG.md summarizes blueprint-to-story workflow, story workspaces, prompt packs, review bundles, quality gates, test layers, queue loops, support queue, public-readiness guard, minimal demo, code tour, command map, and LangGraph workflow preview/run phases.
- If the human owner explicitly chooses MIT, add a standard MIT LICENSE file.
- If the human owner does not explicitly choose a license, do not add LICENSE.
- If no license is added, clearly document that default copyright applies and outside reuse is not granted automatically.
- Do not add new CLI behavior.
- Do not expose private prompts, secrets, generated runtime artifacts, or private strategy logic.

## Not In Scope

- No new CLI behavior.
- No cloud model calls.
- No automatic merge, deployment, repository visibility change, GitHub release creation, package publishing, or approval.
- No automatic license selection or LICENSE file creation without an explicit owner decision.
- No private prompts, private strategy guidance, secrets, generated runtime artifacts, or local-only operator details.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 041 prepare workflow-run passes.
- Story 041 local-finalize workflow-run passes.
- Story 041 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 041 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
