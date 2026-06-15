# Public Readiness

This repository is designed so it can eventually be published, but only after local-only files and
generated runtime artifacts are kept out of Git.

## What Can Be Public

These files are intended to be safe to publish:

- Source code under `src/`.
- Tests under `tests/`.
- Public docs under `docs/`.
- Story definitions, story runbooks, story test plans, and committed story reports under `stories/`.
- Blueprint content in `blueprints/blueprint.yaml` and `blueprints/blueprint.md`.
- The sanitized operator example at `blueprints/agentic-architecture.example.md`.
- `.env.example` files that contain placeholder names only.
- `.gitkeep` files used to preserve generated artifact folders.

## What Must Stay Private

Do not commit local runtime files, generated review packets, secrets, or private operator guidance.
The public-readiness check fails if Git tracks any of these paths:

- `blueprints/agentic-architecture.md`
- `.env` and `.env.*` except `.env.example`
- `review_to_chatgpt/**`
- `*.zip`
- `stories/**/review_bundle/*` except `.gitkeep`
- `stories/**/cloud_review_packet/*` except `.gitkeep`
- `stories/**/remote_dev_validation/*` except `.gitkeep`
- `.agentic/support_queue/**/*.yaml` and `.agentic/support_queue/**/*.md`
- `.agentic/feature_scan/*.md` and `.agentic/feature_scan/*.yaml`
- `.agentic/local_model_scorecard/results/**`
- `stories/**/reports/local_agent_drafts/*` except `.gitkeep`
- `stories/**/reports/local_agent_context/*` except `.gitkeep`
- `stories/**/reports/role_context/*` except `.gitkeep`
- `stories/**/reports/codex_tasks/*` except `.gitkeep`
- `stories/**/reports/codex_runtime/*` except `.gitkeep`
- `*_raw_response.json`
- `.agentic/local_model_scorecard/scorecard_scores.yaml`
- `reports/local_model_scorecard_report.md`
- `reports/local_model_role_recommendations.md`
- `reports/local_model_role_recommendations.yaml`
- `.agentic/improvement_queue/**/IMP-*.yaml`
- `.agentic/maintenance_queue/**/MAINT-*.yaml`
- `.agentic/feature_queue/**/FEATURE-*.yaml`

## Private Architecture Guidance

`blueprints/agentic-architecture.md` is private local operator guidance. It may include local
workflow preferences, safety instructions, machine-specific details, or private operating context.
It is ignored by Git and must remain untracked.

Use `blueprints/agentic-architecture.example.md` when you need a public, sanitized template. Keep
the example generic. Do not copy private instructions, secrets, local paths, account names, tokens,
or unpublished operating details into it.

## Run The Check

From the repository root:

```powershell
docker compose run --rm dev agentic public-readiness
```

The command checks Git-tracked files only. It prints a pass/fail summary and writes
`reports/public_readiness_report.md`. It does not delete files, call cloud models, commit, push,
merge, or deploy.

## Before Making The Repo Public

Run these checks before any public-release decision:

- `docker compose run --rm dev agentic public-readiness`
- `docker compose run --rm dev agentic artifact-policy`
- `docker compose run --rm dev pytest`
- `docker compose run --rm dev ruff check .`
- `git status --short --untracked-files=all`

Also manually review the current branch and any open PR for credentials, private customer or
operator context, generated review packets, local support tickets, feature scan runtime files,
local model scorecard outputs, local agent draft outputs, local model raw responses, and queue item runtime files. Public readiness is a guardrail, not a
full secret scanner.

For the final public-launch sequence, use `docs/public_launch_checklist.md`.

## License Decision

Choose a license before making the repository public. This project does not select a license
automatically unless the owner has already committed one.

MIT is a common permissive option, but the human owner must decide which license fits the project
goals and any legal requirements. Without a license, public visitors may not know what reuse rights
they have.
