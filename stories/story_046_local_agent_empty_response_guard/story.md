# STORY-046: Local Agent Empty Response Guard

## Goal

Fix local-agent draft and local-agent run-prompt so they never silently succeed when the local model returns an empty response.

## Why This Matters

A local-agent draft and a direct run-prompt command previously wrote empty Markdown while reporting success, making it unclear whether the model returned empty content or response parsing failed.

## Acceptance Criteria

- Add Story 046 to blueprints/blueprint.yaml.
- Update local model response handling for local-agent draft and local-agent run-prompt.
- Empty or whitespace-only extracted model content is treated as failure.
- local-agent draft does not mark status draft_saved when content is empty.
- local-agent draft writes metadata with status empty_model_response or failed when content is empty.
- Failure metadata explains that raw response JSON and model/server config should be inspected.
- local-agent draft saves raw response JSON beside the draft metadata.
- local-agent run-prompt saves raw response JSON beside the output path.
- Response extraction supports choices[0].message.content as a string.
- Response extraction supports choices[0].message.content as a list of text parts.
- Response extraction supports choices[0].text.
- Response extraction supports output_text.
- Hidden/internal reasoning fields are not used as final output.
- If only hidden/internal reasoning is present, local-agent commands treat the response as empty_model_response.
- Draft metadata includes prompt_character_count, response_character_count, raw_response_file, finish_reason, status, configured_model, output_file, and safety flags.
- The commands still do not edit source files, execute model output, call cloud models, call GitHub APIs, commit, push, merge, or deploy.
- docs/local_agent_drafts.md explains empty response failures, raw response JSON debugging, and common causes.
- docs/local_models.md mentions raw response JSON for run-prompt debugging.
- Raw local model response JSON and local_agent_drafts runtime files are ignored and blocked by artifact-policy and public-readiness.
- Tests use fake HTTP clients and do not require a live local model server.

## Not In Scope

- No automatic source edits from local model output.
- No shell command execution from model output.
- No cloud model calls.
- No automatic commit, push, merge, deploy, or GitHub API calls.
- No replacement of Codex as the coding runtime.
- No committing local_agent_drafts output files.
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
- Story 046 prepare workflow-run passes.
- Story 046 local-finalize workflow-run passes.
- Story 046 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 046 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
