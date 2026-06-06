# STORY-035: Public Repo Polish

## Goal

Polish the public-facing GitHub repository so a visitor can quickly understand what the agentic-dev-system is, why it exists, how to run it, and why it is safe/conservative.

## Why This Matters

The repository needs a sharper first impression for public visitors, including a clear README, CI badge, quick demo, safety explanation, and suggested GitHub repo metadata.

## Acceptance Criteria

- Add Story 035 to blueprints/blueprint.yaml.
- Improve README.md public presentation.
- Add a CI badge near the top of README.md.
- Add a concise Quick Demo section.
- Add a Why this project matters section.
- Add a Safety model section or improve the existing one.
- Add docs/repo_settings.md with suggested GitHub description, topics, website field, public repo settings, and license note.
- Update docs/system_map.md if the public-facing map can be clearer.
- Update docs/golden_path.md if the operator flow needs clearer wording.
- Update docs/public_launch_checklist.md if needed.
- Add or update tests that verify the new public-facing docs and README links exist.
- Do not add major new CLI features.
- Do not expose private prompts, private strategies, secrets, or generated runtime artifacts.

## Not In Scope

- No major new CLI features.
- No cloud model calls.
- No automatic merge, deployment, repository visibility change, or approval.
- No automatic license selection or LICENSE file creation.
- No private prompts, private strategy guidance, secrets, or generated runtime artifacts.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story reports are written for development, testing, and local review.
- Review bundle is generated for Story 035 but generated bundle files are not committed.
