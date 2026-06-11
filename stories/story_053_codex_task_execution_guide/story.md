# STORY-053: Codex Task Execution Guide

## Goal

Create beginner-friendly documentation that explains how a human operator should safely use generated Codex task files manually, one role at a time.

## Why This Matters

Story 051 created role-specific context packets and Story 052 created Codex-ready task files. Operators now need a clear manual execution guide before any future automatic Codex execution exists.

## Acceptance Criteria

- Add Story 053 to blueprints/blueprint.yaml.
- Add docs/codex_task_execution.md.
- Update docs/codex_runtime.md to link to the manual execution guide.
- Update docs/golden_path.md with the manual Codex task-file step.
- Update docs/system_map.md if helpful with the role context to Codex task flow.
- Update README.md with a short link to docs/codex_task_execution.md.
- Explain what Codex task files are.
- Explain how Codex task files differ from prompt packs and role context packets.
- Document that generated task files live in stories/STORY_SLUG/reports/codex_tasks/.
- Explain that generated codex_tasks files are runtime artifacts and should not be committed.
- Document the recommended execution order of research_agent, planner_agent, developer_agent, test_agent, docs_agent, security_quality_agent, and local_reviewer_agent.
- Explain how to run one role at a time.
- Explain what each Codex role should and should not do.
- Document the reports each role should write.
- Document checks to run after Codex work.
- Explain what the human still approves.
- Include the requested ASCII flow from Story through build-context, role_context, codex-task create, codex_tasks, manual role passes, reports, and local-finalize.
- State that Codex task files are instructions, not automatic execution.
- State that Codex is not invoked automatically.
- State that human approval is required before merge.
- State not to run all task files blindly.
- State to run Developer before Test and Local Reviewer last.
- State not to let Codex merge, deploy, or commit secrets.
- State not to commit generated codex_tasks or role_context files.
- Explain that normal stories can use one Codex session with role phases, high-risk stories can use separate Codex sessions for independence, and DeFi/risk/security stories should use stronger separation.
- Add deterministic tests that verify the guide exists, README links to it, docs/codex_runtime.md links to it, required commands are mentioned, Codex is not invoked automatically, human approval is required before merge, and generated codex_tasks should not be committed.

## Not In Scope

- No automatic Codex execution.
- No calling Codex from the agentic command.
- No local model calls.
- No cloud model calls.
- No generated task execution.
- No automatic source edits from generated task files.
- No automatic commit, push, merge, deploy, or GitHub API calls from the command.
- No new command that runs task files.
- No committing generated review_bundle, cloud_review_packet, role_context packet, codex_tasks, local_agent_context, or local_agent_drafts files except allowed .gitkeep placeholders.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 053 generate-stories passes.
- Story 053 workflow-run prepare execute passes.
- Story 053 build-context command passes.
- Story 053 codex-task create command passes.
- Story 053 workflow-run local-finalize execute passes.
- Story 053 workflow-run cloud-review-prep execute passes.
- Review bundle is generated for Story 053 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
