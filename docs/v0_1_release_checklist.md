# v0.1 Release Checklist

Use this checklist before creating a v0.1 GitHub release. The owner makes the
final decision manually after reviewing the repository, release notes, checks,
and pull request.

## Repository Docs

- README polished.
- `docs/golden_path.md` exists.
- `docs/system_map.md` exists.
- `docs/demo_walkthrough.md` exists.
- `docs/code_tour.md` exists.
- `docs/command_map.md` exists.
- `docs/portfolio_case_study.md` exists.
- `docs/release_process.md` exists.
- `docs/release_notes_v0_1.md` exists.
- `CHANGELOG.md` exists.
- `CONTRIBUTING.md` exists.
- `SECURITY.md` exists.
- Issue templates exist.

## Required Checks

- `docker compose build` passes.
- `docker compose run --rm dev pytest` passes.
- `docker compose run --rm dev ruff check .` passes.
- `docker compose run --rm dev agentic artifact-policy` passes.
- `docker compose run --rm dev agentic public-readiness` passes.
- `docker compose run --rm dev agentic runtime-config validate` passes.
- `docker compose run --rm dev agentic project-status` runs and has no release
  blocker.
- GitHub Actions CI passes.

## Release Decisions

- License decision made.
- If no `LICENSE` file is added, default copyright applies and outside reuse is
  not granted automatically.
- GitHub description set manually.
- GitHub topics set manually.
- Branch protection and review expectations are acceptable.
- Release notes reviewed.
- Changelog reviewed.
- Human owner approves the release.

## Safety

- No generated review bundle files are tracked except `.gitkeep`.
- No generated cloud review packet files are tracked except `.gitkeep`.
- No generated remote dev validation files are tracked except `.gitkeep`.
- No support queue runtime tickets are tracked.
- No feature scan runtime files are tracked.
- No `.env` files or secrets are tracked.
- No private prompts, private strategy logic, or local-only operator guidance is
  tracked.
- No deployment, package publishing, or cloud model call is triggered
  automatically.
