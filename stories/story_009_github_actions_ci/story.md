# STORY-009: Add GitHub Actions CI workflow

## Goal

Create a GitHub Actions workflow that automatically builds the Docker environment and runs quality checks on pushes and pull requests.

## Why This Matters

The system should not rely only on local checks. Every PR should prove that the project builds and passes tests in a clean GitHub runner before merge.

## Acceptance Criteria

- Add .github/workflows/ci.yml.
- CI runs on pull requests targeting main.
- CI runs on pushes to main and story branches.
- CI builds the Docker Compose environment.
- CI runs pytest inside the dev container.
- CI runs Ruff inside the dev container.
- CI runs agentic generate-stories as an idempotency/sanity check.
- CI fails if generated stories are missing from the committed repo.
- Add tests that verify the workflow file contains the required CI commands.
- Update README with CI usage notes.
- Add docs/ci_cd.md explaining what the CI workflow checks.

## Not In Scope

- No deployment.
- No remote dev validation environment.
- No GitHub branch protection automation.
- No cloud model review integration.
- No secrets or environment-specific credentials.

## Definition of Done

- pytest passes locally.
- ruff passes locally.
- .github/workflows/ci.yml exists.
- tests verify the CI workflow content.
- GitHub Actions runs successfully on the PR.
