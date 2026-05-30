# STORY-011: Add generated artifact policy guard

## Goal

Create a command and CI check that prevents generated review artifacts from being committed.

## Why This Matters

Review bundles and cloud review packets are generated evidence. They should be regenerated as needed, not permanently committed. CI should fail if generated artifacts are accidentally tracked.

## Acceptance Criteria

- Add an artifact-policy command.
- The command defaults --project to the current working directory.
- The command checks tracked Git files.
- The command fails if generated review bundle files are tracked.
- The command fails if generated cloud review packet files are tracked.
- The command fails if review_to_chatgpt files are tracked.
- The command fails if zip files are tracked.
- The command fails if .env or .env.* files are tracked, except .env.example.
- .gitkeep files inside generated artifact folders are allowed.
- CI runs the artifact-policy command.
- Tests verify allowed and blocked paths.
- README and docs/ci_cd.md are updated.

## Not In Scope

- No secret scanning engine yet.
- No dependency vulnerability scanning yet.
- No production deployment.
- No cloud model review automation.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes on the current repo.
- CI workflow includes artifact-policy.
- tracked generated artifacts would fail the policy.
