# STORY-051: Role-Specific Context Builder

## Goal

Add a command that builds role-specific context packets for each assigned agent in a story so each agent receives the smallest complete context needed for its role instead of the whole repository.

## Why This Matters

Prompt packs tell agents what role they are playing. Context packets tell agents what information they need for that role. The workflow needs deterministic context packets before connecting assigned roles to future runtimes.

## Acceptance Criteria

- Add Story 051 to blueprints/blueprint.yaml.
- Add agentic build-context --story STORY_SLUG.
- Support --agent AGENT_ID, --all, optional --project, optional --force, and optional --target-chars defaulting to 8000.
- Add src/agentic_dev/role_context.py.
- Update src/agentic_dev/cli.py, README.md, docs/code_tour.md, and docs/command_map.md.
- Add docs/role_context_builder.md.
- Validate the story folder exists.
- Read agent_plan.yaml and build all assigned agents by default when neither --all nor --agent is provided.
- Do not overwrite existing context packets unless --force is used.
- Write packets to stories/STORY_SLUG/reports/role_context/AGENT_ID_context.md.
- Write stories/STORY_SLUG/reports/role_context_result.yaml and reports/role_context_report.md.
- Track included files, skipped files, estimated character count, and warnings.
- Shared context includes story.md, status.yaml when present, agent_plan.yaml, the specific agent instruction file, relevant .agentic/rules.yaml safety rules when present, and .agentic/agent_runtime.yaml runtime guidance when present.
- Role-specific packets follow the developer, test, docs, reviewer, security, research, and planner context rules described for this story.
- Each packet includes Agent identity, Story, Role responsibility, Shared premise, Role-specific context, Included files, Skipped files, Warnings, Expected output, Safety boundaries, and Suggested next command or handoff note.
- Result YAML includes story, agents_built, target_characters, status, context_packets, warnings, failed_checks, and false safety flags for cloud models, local models, executed agents, committed_or_merged, and deployed.
- Statuses include CONTEXT_READY, CONTEXT_READY_WITH_WARNINGS, and CONTEXT_FAILED.
- Generated role_context files are runtime artifacts and are blocked from tracking except .gitkeep.
- Do not call Codex, local models, cloud models, or execute agent prompts.
- Add tests for role context creation, all assigned agents, missing story, missing agent_plan, force overwrite, no overwrite without force, required role boundary text, reviewer evidence, excluded review/cloud packet content, result YAML, false safety flags, model/GitHub safety, and artifact-policy blocking generated role_context files.

## Not In Scope

- No Codex calls.
- No local model calls.
- No cloud model calls.
- No agent prompt execution.
- No automatic source edits from generated context.
- No automatic commit, push, merge, deploy, or GitHub API calls from the command.
- No committing generated review_bundle, cloud_review_packet, remote_dev_validation, local_agent_context, local_agent_drafts, or role_context packet files except allowed .gitkeep placeholders.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 051 generate-stories passes.
- Story 051 workflow-run prepare execute passes.
- Story 051 build-context command passes.
- Story 051 workflow-run local-finalize execute passes.
- Story 051 workflow-run cloud-review-prep execute passes.
- Review bundle is generated for Story 051 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
