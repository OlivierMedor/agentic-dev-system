# STORY-033: Public Readiness + Private Instructions Guard

## Goal

Add safeguards and documentation so the repo can eventually be made public without leaking private local instructions, secrets, generated artifacts, or runtime review files.

## Why This Matters

The repository needs an explicit guardrail for public readiness, and private local operator guidance must remain untracked while a sanitized example stays available for public users.

## Acceptance Criteria

- Add Story 033 to blueprints/blueprint.yaml.
- Add an agentic public-readiness command.
- public-readiness accepts optional --project and defaults to the current working directory.
- public-readiness checks Git-tracked files.
- public-readiness fails if blueprints/agentic-architecture.md is tracked.
- public-readiness fails if .env or .env.* is tracked, except .env.example.
- public-readiness fails if review_to_chatgpt artifacts, zip files, generated review bundles, generated cloud review packets, generated remote dev validation files, support queue runtime files, feature scan runtime files, or runtime queue item files are tracked.
- public-readiness allows .gitkeep files where needed.
- public-readiness prints a clear pass/fail report.
- public-readiness writes reports/public_readiness_report.md.
- public-readiness does not delete files, call cloud models, commit, push, merge, or deploy.
- Add docs/public_readiness.md.
- Add blueprints/agentic-architecture.example.md as a sanitized public example.
- Ensure blueprints/agentic-architecture.md is ignored and blocked from being tracked.
- Update README.md to explain public readiness.
- Update artifact-policy if needed so private instructions and runtime queue files stay blocked.
- Add tests for pass, blocked private guidance, .env handling, generated review artifacts, support queue runtime files, report writing, artifact-policy, and README docs links.

## Not In Scope

- No secret scanning engine.
- No automatic deletion of local files.
- No cloud model calls.
- No GitHub API automation beyond manually opening the PR if available.
- No automatic merge, deployment, or approval.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- public-readiness passes on the current tracked repo.
- project-status runs.
- Story reports are written for development, testing, and local review.
