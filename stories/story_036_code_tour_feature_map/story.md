# STORY-036: Code Tour and Feature Map

## Goal

Create beginner-friendly documentation that maps each major system feature to the code files, tests, docs, and story workspace that implement it.

## Why This Matters

New contributors and reviewers need a plain-language map from repository structure and commands to the code, tests, docs, and stories that support them.

## Acceptance Criteria

- Add Story 036 to blueprints/blueprint.yaml.
- Add docs/code_tour.md.
- Add docs/command_map.md.
- Update README.md to link to both docs.
- Update docs/system_map.md if a link or short reference helps.
- Add or update tests that verify the new docs exist and README links to them.
- docs/code_tour.md explains .agentic/, .github/workflows/, blueprints/, docs/, src/agentic_dev/, stories/, tests/, Dockerfile / compose.yml, README.md, and pyproject.toml.
- docs/code_tour.md uses simple analogies for blueprints, stories, src/agentic_dev, tests, docs, and .agentic.
- docs/code_tour.md includes an ASCII visual from user command to tests.
- docs/command_map.md maps commands to CLI entry, core module, tests, and related story where obvious.
- If a mapping is uncertain, docs/command_map.md says best-known mapping.
- Do not add new CLI behavior unless absolutely necessary.
- Do not expose private prompts, private strategies, secrets, or generated runtime artifacts.

## Not In Scope

- No new CLI behavior.
- No cloud model calls.
- No automatic merge, deployment, repository visibility change, or approval.
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
- Review bundle is generated for Story 036 but generated bundle files are not committed.
