# Public Launch Checklist

Use this checklist before public release-readiness updates, repository metadata
changes, or any future repository visibility changes. The final visibility,
license, release, and metadata decisions are manual and should happen only after
the human owner reviews the repository, CI, and local checks.

## Required Local Checks

- Run `docker compose build`.
- Run `docker compose run --rm dev pytest`.
- Run `docker compose run --rm dev ruff check .`.
- Run `docker compose run --rm dev agentic artifact-policy`.
- Run `docker compose run --rm dev agentic public-readiness`.
- Run `docker compose run --rm dev agentic runtime-config validate`.
- Run `docker compose run --rm dev agentic project-status`.

## Repository Hygiene

- Confirm no `.env` files are tracked.
- Confirm no review bundle files are tracked except `.gitkeep`.
- Confirm no cloud review packet files are tracked except `.gitkeep`.
- Confirm no remote dev validation files are tracked except `.gitkeep`.
- Confirm no support queue runtime tickets are tracked.
- Confirm no feature scan runtime files are tracked.
- Confirm no runtime queue item YAML files are tracked.
- Confirm `blueprints/agentic-architecture.md` is not tracked.
- Confirm `blueprints/agentic-architecture.example.md` is public-safe.
- Confirm README is public-safe.
- Confirm docs are beginner-friendly.
- Confirm no private strategy logic, private prompts, secrets, account names, or
  local-only operator details are included in tracked files.

## License Decision

Choose a license before making the repository public. This project should not
assume a license automatically unless the owner has already committed one.

MIT is a common permissive option for open source projects, but the human owner
must decide which license fits the project goals and any legal requirements. If
no license is chosen, public visitors may not know what reuse rights they have.

## GitHub And Release Readiness

- Confirm CI passes on the release-readiness PR.
- Review `docs/github_metadata.md` for suggested GitHub description, topics,
  website field guidance, and manual setup steps.
- Review `docs/repo_settings.md` for public repository settings.
- Confirm branch protection and review expectations are acceptable.
- Confirm open issues, PR text, and story reports are public-safe.
- Confirm generated local reports under ignored paths are not staged.
- Confirm the human owner has reviewed the final diff.
- If any repository visibility change is needed later, change GitHub repository visibility manually in the GitHub UI.

Do not merge, deploy, publish packages, or change repository visibility from the
CLI workflow.
