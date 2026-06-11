# STORY-052: Codex Runtime Connector

## Goal

Create a Codex runtime connector that turns role-specific context packets into Codex-ready task files.

## Why This Matters

Role-specific context packets say what each agent needs to know. Codex task files should tell Codex exactly what to do with that context, without automatically invoking Codex or any cloud model.

## Acceptance Criteria

- Add Story 052 to blueprints/blueprint.yaml.
- Add agentic codex-task create --story STORY_SLUG.
- Support --agent AGENT_ID, --all, optional --project, optional --force, and optional --model.
- Add src/agentic_dev/codex_runtime.py.
- Update src/agentic_dev/cli.py, README.md, docs/code_tour.md, and docs/command_map.md.
- Add docs/codex_runtime.md.
- Read role context packets from stories/STORY_SLUG/reports/role_context/AGENT_ID_context.md.
- If role context is missing, return a clear error telling the user to run agentic build-context --story STORY_SLUG --all --force.
- Write Codex task files to stories/STORY_SLUG/reports/codex_tasks/AGENT_ID_codex_task.md.
- Write stories/STORY_SLUG/reports/codex_task_result.yaml and reports/codex_task_report.md.
- Each task file includes Agent identity, Story slug, Model recommendation, Safety rules, Context packet content, Exact role objective, Required output report path, Validation commands, and Do-not-do list.
- Do-not-do list includes do not merge, do not deploy, do not call cloud models, do not commit secrets, do not modify unrelated files, and do not bypass artifact-policy.
- Use .agentic/agent_runtime.yaml model recommendations when present, and use --model as a task-file recommendation override without switching Codex models.
- Read execution_order from agent_plan.yaml when present.
- If execution_order is missing, use the standard order of research_agent, planner_agent, developer_agent, test_agent, docs_agent, security_quality_agent, and local_reviewer_agent.
- Include recommended_execution_order in codex_task_result.yaml and codex_task_report.md.
- Each task file includes where the agent sits in execution order, which agent usually comes before it, which agent usually comes after it, and a reminder to only do that agent's role.
- If --all is used, create Codex task files for all role context packets.
- If --agent is used, create one Codex task file.
- If neither --all nor --agent is provided, default to all role context packets.
- Do not overwrite existing task files unless --force is used.
- Track generated files, skipped files, warnings, and safety flags.
- Result YAML safety flags are false for called_codex, called_cloud_models, executed_agents, called_github_apis, committed_or_merged, and deployed.
- Do not automatically invoke Codex.
- Do not call cloud models.
- Do not call GitHub APIs, commit, push, merge, or deploy from this command.
- Generated codex_tasks files are runtime artifacts and are blocked from tracking except .gitkeep.
- Add tests for missing story folder, missing role context, one-agent creation, all-agent creation, force overwrite, no overwrite without force, task safety rules, role context inclusion, required output report path, execution order from agent_plan.yaml, fallback standard execution order, result YAML creation, false safety flags, model/GitHub safety, and artifact-policy blocking generated codex_tasks files.

## Not In Scope

- No automatic Codex execution.
- No local model calls.
- No cloud model calls.
- No generated task execution.
- No automatic source edits from generated task files.
- No automatic commit, push, merge, deploy, or GitHub API calls from the command.
- No committing generated review_bundle, cloud_review_packet, role_context packet, or codex_tasks files except allowed .gitkeep placeholders.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 052 generate-stories passes.
- Story 052 workflow-run prepare execute passes.
- Story 052 build-context command passes.
- Story 052 codex-task create command passes.
- Story 052 workflow-run local-finalize execute passes.
- Story 052 workflow-run cloud-review-prep execute passes.
- Review bundle is generated for Story 052 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
