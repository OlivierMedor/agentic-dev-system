# STORY-048: Add Micro Local-Agent Prompt Mode For Gemma Reliability

## Goal

Add a smaller local-agent prompt mode designed for local reasoning models like Gemma that may spend too much output budget in reasoning_content and return empty visible message.content.

## Why This Matters

Gemma can answer tiny direct prompts but still fail local-agent drafts in slim mode because the story prompt is too large or too reasoning-heavy. A micro mode should provide the smallest final-answer-focused context while preserving save-only local draft boundaries.

## Acceptance Criteria

- Add --prompt-mode micro to local-agent draft.
- Keep full and slim modes working.
- Make micro mode much smaller than slim mode.
- Create micro context packets under stories/STORY_SLUG/reports/local_agent_context/AGENT_ID_MODEL_LABEL_context.md.
- Micro metadata records prompt_mode micro, context_character_count, and source_files_used.
- Micro context includes story slug, agent id, agent role or responsibility, one short story goal, up to five top acceptance criteria, expected output path, safety boundary, and final visible answer instructions.
- Micro context excludes review bundles, cloud review packets, remote dev validation packets, raw model responses, prior local-agent drafts, unrelated story files, large reports, and long prompt packs.
- Micro mode targets a short prompt, ideally under 2,000 characters where practical.
- If micro context exceeds a reasonable threshold, metadata records a warning.
- Empty visible message.content still fails with status empty_model_response.
- Non-empty visible content with finish_reason length saves a draft with a warning.
- Do not use reasoning_content as the final draft by default.
- Raw local model responses are still saved for debugging.
- Do not apply local model output to source files.
- Do not call cloud models.
- Do not commit generated local-agent runtime artifacts.
- Update local-agent context, draft, local model, and relevant README documentation.
- Tests use fake local model HTTP clients and do not require a live model server.

## Not In Scope

- No automatic source edits from local model output.
- No shell command execution from model output.
- No cloud model calls.
- No automatic commit, push, merge, deploy, or GitHub API calls.
- No committing local_agent_drafts output files.
- No committing local_agent_context runtime files.
- No committing raw local model response files.
- No hardcoded tiny output token limit.
- No secret exposure.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 048 prepare workflow-run passes.
- Story 048 local-finalize workflow-run passes.
- Story 048 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 048 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
