# STORY-038: Public Metadata and Release Readiness

## Goal

Clean up the public repo status, GitHub metadata guidance, and first release-readiness docs.

## Why This Matters

The repository is public and needs current README wording, manual GitHub metadata guidance, v0.1 release notes, and tests that catch stale public-launch language.

## Acceptance Criteria

- Add Story 038 to blueprints/blueprint.yaml.
- Update README.md so it says the repo is public and under active development.
- Update README.md so it says the system is portfolio-ready v0.1 / early public version.
- Ensure README.md no longer says the repo is preparing for a future public launch.
- Keep the human-approval safety model clear.
- Keep README.md concise.
- Add docs/github_metadata.md with suggested GitHub description, topics, website field guidance, and manual setup steps.
- docs/github_metadata.md explains that GitHub description and topics are set manually in the GitHub UI.
- docs/github_metadata.md mentions that a portfolio website URL can be added later.
- Add docs/release_notes_v0_1.md summarizing v0.1 features and what is not included yet.
- docs/release_notes_v0_1.md mentions blueprint-to-story workflow, story workspaces, agent prompt packs, review bundles, quality gates, test layers, support/improvement/maintenance/feature queues, public-readiness guard, minimal demo project, code tour and command map, and LangGraph workflow-preview and workflow-run phases.
- Update docs/public_launch_checklist.md if needed.
- Update docs/repo_settings.md if needed.
- Add or update tests verifying README/public docs are current.
- Do not add new CLI features.
- Do not expose private prompts, secrets, generated runtime artifacts, or private strategy logic.
- Do not add a LICENSE file unless the owner explicitly requested it.
- Keep license guidance as a decision the owner still controls.

## Not In Scope

- No new CLI features.
- No cloud model calls.
- No automatic merge, deployment, repository visibility change, GitHub metadata change, or approval.
- No automatic license selection or LICENSE file creation.
- No private prompts, private strategy guidance, secrets, generated runtime artifacts, or local-only operator details.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 038 prepare workflow-run passes.
- Story 038 local-finalize workflow-run passes.
- Story 038 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 038 but generated bundle files are not committed.
