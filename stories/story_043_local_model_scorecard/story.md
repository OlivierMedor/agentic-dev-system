# STORY-043: Local Model Scorecard

## Goal

Add a repeatable local model scorecard workflow so the project owner can compare local models such as Qwen3 Coder, Devstral, Qwen2.5 Coder, and Gemma on the same agent-style tasks before assigning models to agent roles.

## Why This Matters

The system should not guess which local model is best. It should standardize local-agent prompts, save comparable responses, and leave final role assignment to manual scoring and review.

## Acceptance Criteria

- Add Story 043 to blueprints/blueprint.yaml.
- Add docs/local_model_scorecard.md.
- Add local model scorecard support under src/agentic_dev/.
- Update src/agentic_dev/cli.py.
- Add agentic local-model scorecard-create.
- Add agentic local-model scorecard-run.
- Add agentic local-model scorecard-report.
- scorecard-create defaults --project to the current working directory.
- scorecard-create accepts optional --force.
- scorecard-create creates .agentic/local_model_scorecard/prompts/.
- scorecard-create creates .agentic/local_model_scorecard/results/.
- scorecard-create creates .agentic/local_model_scorecard/scorecard_template.yaml.
- scorecard-create creates .agentic/local_model_scorecard/README.md.
- scorecard-create creates standard prompt files for Developer Agent, Test Agent, Docs Agent, Reviewer Agent, and Maintenance Agent.
- Prompt tasks are small, public-safe, include context, and require structured output.
- scorecard-create does not overwrite existing files unless --force is used.
- scorecard-run requires --model-label.
- scorecard-run defaults --project to the current working directory.
- scorecard-run accepts optional --prompt-dir defaulting to .agentic/local_model_scorecard/prompts.
- scorecard-run reads local_model_runtime from .agentic/agent_runtime.yaml.
- scorecard-run requires local_model_runtime.enabled true.
- scorecard-run sends each scorecard prompt to the configured local OpenAI-compatible model.
- scorecard-run saves raw responses under .agentic/local_model_scorecard/results/<model-label>/.
- scorecard-run writes .agentic/local_model_scorecard/results/<model-label>/run_summary.md.
- scorecard-report defaults --project to the current working directory.
- scorecard-report reads scorecard_template.yaml and result folders if present.
- scorecard-report creates reports/local_model_scorecard_report.md.
- The report summarizes model result folders, prompt responses, human scoring needs, and recommended scoring dimensions.
- The report does not automatically claim a winner unless scores are actually present.
- README.md and docs/local_models.md link to docs/local_model_scorecard.md.
- Runtime scorecard results and generated scorecard reports are ignored by Git and blocked by artifact-policy and public-readiness.
- Tests use fake HTTP clients and do not require a live LM Studio or Ollama server.

## Not In Scope

- No automatic source edits from local model output.
- No shell command execution from model output.
- No automatic commit, push, merge, deploy, or GitHub API calls.
- No cloud model calls.
- No automatic model winner selection or role assignment.
- No secret exposure.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 043 prepare workflow-run passes.
- Story 043 local-finalize workflow-run passes.
- Story 043 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 043 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
