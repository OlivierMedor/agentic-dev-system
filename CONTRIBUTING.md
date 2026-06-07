# Contributing

`agentic-dev-system` is a local-first agentic development workflow system. It
turns approved blueprint entries into story workspaces, prompt packs, validation
reports, review bundles, and manual review handoffs.

## Before Large Changes

Use an issue or discussion before starting large or cross-cutting work. The
maintainer controls the roadmap, story priority, merge approval, and final
scope decisions.

All changes should be story-scoped. Keep each pull request tied to a clear story
workspace or a small maintenance item, and avoid unrelated refactors in the same
change.

## Local Checks

Before opening a pull request, run the normal local validation commands:

```powershell
docker compose build
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic artifact-policy
docker compose run --rm dev agentic public-readiness
docker compose run --rm dev agentic runtime-config validate
```

Tests and Ruff should pass before review. If a check cannot run, document the
reason in the pull request.

## Files That Must Stay Out Of Git

Do not commit generated review artifacts, local runtime files, secrets, or
private operator guidance. In particular, keep these out of commits:

- Generated `review_bundle` files.
- Generated `cloud_review_packet` files.
- Generated `remote_dev_validation` files.
- Support queue runtime files.
- Feature scan runtime files.
- `.env` files and other local credential files.
- API keys, tokens, credentials, or private prompts.
- `blueprints/agentic-architecture.md`.

The repository includes `artifact-policy` and `public-readiness` checks to catch
many of these mistakes, but contributors are still responsible for reviewing
their own diffs before opening a pull request.

## Review And Merge

Human review is required before merge. The CLI can prepare evidence and review
handoffs, but it does not approve, merge, deploy, or make roadmap decisions.

The maintainer has final approval on whether a change fits the project, whether
the story is complete, and when it can merge.
