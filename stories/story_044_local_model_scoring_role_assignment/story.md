# STORY-044: Local Model Scoring and Role Assignment

## Goal

Add a formal way to record human scores for local model scorecard runs and generate recommended model assignments for agent roles.

## Why This Matters

Saved local model scorecard responses need a structured human scoring layer before any model is considered for role-specific local draft or report work.

## Acceptance Criteria

- Add Story 044 to blueprints/blueprint.yaml.
- Add scoring support to local model scorecard.
- Add docs/local_model_role_assignment.md.
- Update docs/local_model_scorecard.md.
- Update README.md if useful.
- Add agentic local-model scorecard-scaffold-scores.
- Add agentic local-model scorecard-recommend.
- scorecard-scaffold-scores accepts optional --project defaulting to the current working directory.
- scorecard-scaffold-scores reads .agentic/local_model_scorecard/results/ model folders if present.
- scorecard-scaffold-scores creates .agentic/local_model_scorecard/scorecard_scores.yaml.
- scorecard-scaffold-scores includes one scoring entry per model and role response found.
- scorecard-scaffold-scores does not overwrite scorecard_scores.yaml unless --force is used.
- Scores are blank/null by default.
- Score entries include model_label, role, response_file, instruction_following, correctness, hallucination_control, code_quality, test_quality, safety_compliance, clarity, overall_fit_for_role, speed_notes, and reviewer_notes.
- scorecard-recommend accepts optional --project defaulting to the current working directory.
- scorecard-recommend reads .agentic/local_model_scorecard/scorecard_scores.yaml.
- scorecard-recommend validates required scoring fields.
- scorecard-recommend ignores incomplete entries and reports them.
- scorecard-recommend computes role recommendations based on overall_fit_for_role first.
- scorecard-recommend uses safety_compliance, hallucination_control, correctness, and instruction_following as tie-breakers.
- scorecard-recommend writes reports/local_model_role_recommendations.md and reports/local_model_role_recommendations.yaml.
- scorecard-recommend does not automatically update .agentic/agent_runtime.yaml.
- scorecard-recommend does not claim a winner if scores are missing.
- Recommendation output includes best model per role, runner-up per role, scoring evidence summary, incomplete scoring warnings, safety recommendation, and a final note that the human owner controls runtime assignment.
- Supported roles are developer_agent, test_agent, docs_agent, reviewer_agent, and maintenance_agent.
- Local model prompts prefer plain ASCII, avoid emoji/checkmark symbols that can render poorly in Windows/PowerShell logs, avoid unnecessary nested whole-response Markdown code fences, and use requested headings exactly.
- Runtime scorecard result folders remain ignored.
- scorecard_scores.yaml and local_model_role_recommendations reports are ignored by Git and blocked by artifact-policy and public-readiness.
- Tests use fake result folders and manual YAML scores only.

## Not In Scope

- No automatic source edits from local model output.
- No shell command execution from model output.
- No cloud model calls.
- No automatic commit, push, merge, deploy, or GitHub API calls.
- No automatic changes to agent runtime defaults.
- No committing runtime scorecard result folders.
- No committing local scoring artifacts or recommendation reports by default.
- No secret exposure.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 044 prepare workflow-run passes.
- Story 044 local-finalize workflow-run passes.
- Story 044 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 044 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
