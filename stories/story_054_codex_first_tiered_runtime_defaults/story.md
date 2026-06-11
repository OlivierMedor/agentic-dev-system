# STORY-054: Codex-First Tiered Runtime Defaults

## Goal

Update the agent runtime defaults so Codex is the primary runtime, with model tiers by role.

## Why This Matters

The workflow should use strong Codex models where correctness matters and cheaper or faster Codex models where the role is lower-risk. Runtime model assignment belongs in agent_runtime.yaml so blueprints stay focused on story scope.

## Acceptance Criteria

- Add Story 054 to blueprints/blueprint.yaml.
- Update .agentic/agent_runtime.yaml defaults so required agents use the Codex-first tiered policy.
- Update default runtime config scaffolding so new initialized projects receive the same defaults.
- research_agent uses provider codex and model gpt-5.4-mini.
- planner_agent uses provider codex and model gpt-5.4.
- developer_agent uses provider codex and model gpt-5.4.
- test_agent uses provider codex and model gpt-5.4.
- docs_agent uses provider codex and model gpt-5.4-mini, not local_model_optional.
- security_quality_agent uses provider codex and model gpt-5.5.
- local_reviewer_agent uses provider codex and model gpt-5.5.
- cloud_reviewer remains provider manual_cloud_model and model main_cloud_model.
- Keep Gemma/local model support as an optional local_model_helper or local_draft_agent with provider local_model_optional, model gemma-4-26b, and prompt_mode micro.
- Keep safe Docker, test, lint, and workflow commands allowed without repeated approval.
- Keep merge, deploy, secret, credential, wallet, irreversible Git, and destructive actions requiring human approval.
- Update docs/runtime_config.md or create it if missing.
- Update docs/codex_runtime.md.
- Update README.md with a short explanation of tiered Codex defaults.
- Explain why Codex is the primary runtime.
- Explain why gpt-5.4 is the default worker.
- Explain why gpt-5.4-mini is used for lighter roles.
- Explain why gpt-5.5 is reserved for high-risk review, security, and final judgment.
- Explain why Gemma remains optional for micro-mode local drafts.
- Explain that blueprint files are not where model assignment belongs.
- Explain that agent_runtime.yaml controls runtime and model choices.
- Ensure codex-task create includes model recommendations from agent_runtime.yaml in generated Codex task files.
- Add or update deterministic tests for the tiered runtime defaults and Codex task recommendations.

## Not In Scope

- No automatic Codex execution.
- No calling Codex from the agentic command.
- No cloud model calls.
- No local model calls.
- No generated task execution.
- No removing Gemma support.
- No automatic merge, deploy, secret, credential, wallet, or destructive actions.
- No committing generated review_bundle, cloud_review_packet, role_context packet, codex_tasks, local_agent_context, or local_agent_drafts files except allowed .gitkeep placeholders.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 054 generate-stories passes.
- Story 054 workflow-run prepare execute passes.
- Story 054 build-context command passes.
- Story 054 codex-task create command passes.
- Story 054 workflow-run local-finalize execute passes.
- Story 054 workflow-run cloud-review-prep execute passes.
- Review bundle is generated for Story 054 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
- Local review report says Decision READY_FOR_REVIEW only if all checks pass.
