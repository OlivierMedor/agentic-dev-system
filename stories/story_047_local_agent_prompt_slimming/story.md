# STORY-047: Local Agent Prompt Slimming and Truncation Guard

## Goal

Fix local-agent draft reliability for local models by adding slim context prompts and clear truncation warnings.

## Why This Matters

Local models such as Gemma can fail on full Codex-style prompt packs by returning hidden reasoning with no visible content, while other local models can return truncated drafts. The draft command needs local-model-friendly prompts and explicit warning metadata.

## Acceptance Criteria

- Add Story 047 to blueprints/blueprint.yaml.
- Add --prompt-mode full|slim to agentic local-agent draft.
- local-agent draft defaults to --prompt-mode slim.
- full mode uses the existing story prompt_pack file behavior.
- --prompt-file uses that file directly and records prompt_mode custom.
- slim mode creates a smaller local-model-friendly context packet from story.md, status.yaml, test_plan.yaml, monitoring_plan.yaml, agent_plan.yaml, relevant agent instructions, short safety rules, and the expected output path.
- slim mode excludes review bundles, cloud review packets, unrelated story files, generated runtime artifacts, draft outputs, and raw model responses.
- slim context packets are saved under stories/<story>/reports/local_agent_context/<agent>_<model-label>_context.md.
- Draft metadata records story, agent, model_label, configured_model, prompt_mode, prompt_file for full/custom mode, context_file for slim mode, output_file, raw_response_file, prompt_character_count, response_character_count, finish_reason, status, warnings, context_character_count, source_files_used, safety flags, and next_action.
- If finish_reason is length and visible content is empty, local-agent draft fails with status empty_model_response.
- If finish_reason is length and visible content is non-empty, local-agent draft saves the draft with status draft_saved_with_warning and warning model output may be truncated.
- Raw response JSON is still saved for local-agent drafts.
- The command still does not edit source files, execute model output, call cloud models, call GitHub APIs, commit, push, merge, or deploy.
- docs/local_agent_context_packets.md explains slim context packets and truncation warnings.
- docs/local_agent_drafts.md, docs/local_models.md, and README.md link to the context packet guide and document slim mode.
- local_agent_context runtime files, local_agent_drafts runtime files, and *_raw_response.json files are ignored by Git and blocked by artifact-policy and public-readiness except .gitkeep files.
- Tests use fake HTTP clients and do not require a live local model server.

## Not In Scope

- No automatic source edits from local model output.
- No shell command execution from model output.
- No cloud model calls.
- No automatic commit, push, merge, deploy, or GitHub API calls.
- No committing local_agent_drafts output files.
- No committing local_agent_context runtime files.
- No committing raw local model response files.
- No secret exposure.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 047 prepare workflow-run passes.
- Story 047 local-finalize workflow-run passes.
- Story 047 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 047 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
