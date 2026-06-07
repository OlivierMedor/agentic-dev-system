# Release Process

This repository uses releases as human-approved milestones for the public
project state. A release means the owner has reviewed the code, docs, validation
evidence, and release notes, and has decided that a named version is ready to be
presented as a stable checkpoint.

The local workflow prepares evidence for that decision. It does not create a
release automatically, deploy anything automatically, publish packages, approve
pull requests, merge branches, or call cloud models automatically.

## PR Merge vs GitHub Release

A pull request merge moves reviewed changes into `main`. It proves that the
story branch was reviewed, CI passed, and the owner accepted the change.

A GitHub release is a separate manual milestone. It usually points to a tag,
uses reviewed release notes, and tells public readers which project state is the
named release. A PR can be merged without creating a GitHub release, and a
GitHub release should not be created until the owner explicitly approves it.

## Required Checks

Before a release is approved, run or confirm:

- `docker compose run --rm dev pytest`
- `docker compose run --rm dev ruff check .`
- `docker compose run --rm dev agentic artifact-policy`
- `docker compose run --rm dev agentic public-readiness`
- `docker compose run --rm dev agentic runtime-config validate`
- `docker compose run --rm dev agentic project-status`
- GitHub Actions passing on the release PR or release candidate commit.

The owner may also run `docker compose build` before the checks to verify the
local container can be rebuilt cleanly.

## Approval Rules

The human owner must approve every release. The CLI and story workflow can
prepare release notes, review bundles, status reports, and check output, but
they do not make the release decision.

Do not deploy anything automatically as part of this release process. Do not
publish packages automatically. Do not call cloud models automatically. Cloud
review, if used, is a manual handoff controlled by the human owner.

## License And Reuse

No `LICENSE` file is added unless the human owner explicitly chooses one. If no
license is present, default copyright applies. It does not grant outside reuse
automatically. Public visibility alone does not grant copying, redistribution,
or modification rights automatically.
