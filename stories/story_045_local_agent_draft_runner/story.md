# STORY-045: Local Agent Draft Runner

## Goal

Add a safe local-agent draft command that sends a selected story prompt-pack file to the configured local model and saves the model output as a draft report.

## Why This Matters

The system can validate and call a local model and score local models by role. The next safe step is letting a local model draft responses from prompt_pack files while keeping all output saved-only for human/Codex review.

## Acceptance Criteria

- Add Story 045 to blueprints/blueprint.yaml.
- Add local agent draft support in the local model runtime.
- Update src/agentic_dev/cli.py.
- Add agentic local-agent draft.
- The command requires --story and --agent.
- The command accepts optional --project defaulting to the current working directory.
- The command accepts optional --prompt-file, --output-file, --model-label, and --force.
- Supported agents are developer_agent, test_agent, docs_agent, reviewer_agent, and maintenance_agent.
- Default prompt files map developer_agent to prompt_pack/03_developer_agent_prompt.md, test_agent to prompt_pack/04_test_agent_prompt.md, docs_agent to prompt_pack/05_docs_agent_prompt.md, reviewer_agent to prompt_pack/07_local_reviewer_agent_prompt.md, and maintenance_agent to prompt_pack/07_local_reviewer_agent_prompt.md unless an explicit prompt file is provided.
- Missing stories and missing prompt files raise clear errors.
- The command reads local_model_runtime from .agentic/agent_runtime.yaml.
- The command requires local_model_runtime.enabled true before calling the model.
- The command sends prompt file contents to the configured local OpenAI-compatible model.
- The command saves raw draft Markdown under stories/<story>/reports/local_agent_drafts/.
- The command saves metadata YAML beside the draft Markdown.
- Draft metadata records story, agent, model_label, configured_model, prompt_file, output_file, status, applied_to_source false, executed_model_output false, called_cloud_models false, called_github_apis false, committed_or_merged false, deployed false, and next_action.
- Existing draft output is not overwritten unless --force is used.
- The command prints the output path and safety reminder.
- docs/local_agent_drafts.md explains local agent drafts, save-only behavior, LM Studio setup for Gemma or Devstral, example usage, recommended Gemma/Devstral/Qwen usage, human/Codex review, and human/cloud review for high-risk logic.
- README.md and docs/local_models.md link to docs/local_agent_drafts.md.
- Prompt guidance asks for plain ASCII, avoids emoji/checkmark symbols, avoids unnecessary nested Markdown code fences, and uses requested headings exactly.
- Local agent draft outputs are ignored by Git and blocked by artifact-policy and public-readiness, except .gitkeep files.
- Tests use fake HTTP clients and do not require a live local model server.

## Not In Scope

- No automatic source edits from local model output.
- No shell command execution from model output.
- No automatic commit, push, merge, deploy, or GitHub API calls.
- No cloud model calls.
- No replacing Codex as the coding runtime yet.
- No secret exposure.
- No committing local_agent_drafts output files.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 045 prepare workflow-run passes.
- Story 045 local-finalize workflow-run passes.
- Story 045 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 045 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
