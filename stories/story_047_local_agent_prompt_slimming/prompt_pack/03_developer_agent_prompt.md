# Developer Agent Prompt

## Agent Identity

You are the Developer Agent for `story_047_local_agent_prompt_slimming`.

## Story Name

`story_047_local_agent_prompt_slimming`

## Story File Content

```markdown
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
```

## Agent Responsibility

Implement only the approved story scope. Do not write tests.

## Expected Output

reports/developer_report.md

## Project Rules

```yaml
rules:
  - Developer agent must not write tests.
  - Test agent must write tests independently.
  - Human approval is required before merge.
  - Do not commit secrets, API keys, private keys, or .env files.
```

## Quality Gates

```yaml
quality_gates:
  - tests_required
  - docs_required
  - review_bundle_required
  - local_review_required
```

## Test Plan

```yaml
test_layers_version: 1
unit_tests:
  required: true
  action: add_or_update
  frequency: every_commit
  evidence_or_reason: Add tests for slim default mode, full prompt-pack mode, custom
    prompt-file mode, context packet creation and contents, excluded review/cloud
    artifacts, metadata fields, length truncation warnings, empty length failure,
    raw response saving, artifact/public-readiness blocking, docs links, and safety
    boundaries.
integration_tests:
  required: true
  action: add_or_update
  frequency: every_pull_request
  evidence_or_reason: Existing CLI tests cover local-agent draft command wiring with
    fake runtime calls; this story adds prompt-mode argument coverage without live
    model calls.
mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Existing mock E2E workflow coverage exercises story workflow;
    local model calls are unit-tested with fake HTTP clients.
live_read_only_checks:
  required: false
  action: not_applicable_with_reason
  frequency: manual_only
  evidence_or_reason: Live local draft calls depend on optional host-side LM Studio
    or Ollama setup and are not required in automated tests.
remote_dev_smoke_tests:
  required: false
  action: not_applicable_with_reason
  frequency: after_remote_dev_deploy
  evidence_or_reason: This story does not deploy to a remote dev environment.
```

## Monitoring Plan

```yaml
logs_required: true
watch_for:
- empty_model_response
- truncated_local_model_output
- oversized_local_agent_prompt
- missing_local_agent_context_packet
- committed_local_agent_context
- committed_local_agent_draft
- committed_raw_response
- accidental_source_edit_from_model_output
- model_output_executed
- secret_exposure
- cloud_model_call
```

## Runtime Config

```yaml
agents:
  research_agent:
    provider: codex
    model: gpt-5.5
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  planner_agent:
    provider: codex
    model: gpt-5.5
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  developer_agent:
    provider: codex
    model: gpt-5.5
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  test_agent:
    provider: codex
    model: gpt-5.5
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  docs_agent:
    provider: local_model_optional
    model: qwen_coder_or_codex_fallback
    approval_mode: workspace_write_no_prompt
    fallback_provider: codex

  security_quality_agent:
    provider: codex
    model: gpt-5.5
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  local_reviewer_agent:
    provider: codex
    model: gpt-5.5
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  cloud_reviewer:
    provider: manual_cloud_model
    model: main_cloud_model
    approval_mode: manual_only
    fallback_provider: human_owner

command_policy:
  allowed_without_approval:
    - docker compose run --rm dev pytest
    - docker compose run --rm dev ruff check .
    - docker compose run --rm dev agentic generate-stories
    - docker compose run --rm dev agentic prepare-story
    - docker compose run --rm dev agentic review-bundle
    - docker compose run --rm dev agentic quality-gate
    - docker compose run --rm dev agentic test-layers
    - docker compose run --rm dev agentic finalize-story
    - docker compose run --rm dev agentic artifact-policy

  requires_human_approval:
    - git push
    - git merge
    - git reset --hard
    - git rebase
    - deployment commands
    - secret changes
    - credential changes
    - wallet/private-key actions
    - destructive file deletion

support_policy:
  if_agent_blocked: create_support_ticket
  preferred_responder: cloud_model
  escalate_to_human_when:
    - cloud_model_uncertain
    - business_decision_required
    - security_sensitive_decision
    - real_money_or_deployment_risk

local_model_runtime:
  enabled: true
  provider: local_openai_compatible
  base_url: http://host.docker.internal:1234/v1
  model: google/gemma-4-26b-a4b-qat
  api_key_env: LOCAL_MODEL_API_KEY
  timeout_seconds: 120
  max_output_tokens: 8192
  temperature: 0.2

local_model_profiles:
  lm_studio:
    base_url: http://host.docker.internal:1234/v1
    api_key_hint: lm-studio
  ollama:
    base_url: http://host.docker.internal:11434/v1
    api_key_hint: ollama
```

## Runtime Expectation

- Provider: `codex`
- Model: `gpt-5.5`
- Approval mode: `workspace_write_no_prompt`
- Fallback provider: `manual_cloud_model`

## Agent-Specific Rule

Do not write tests. Implementation only.

## Do-Not-Do Rules

- Do not commit anything.
- Do not create zip files.
- Do not make unrelated changes.
- Do not overwrite another agent's report unless explicitly instructed.
- Do not ignore project rules, quality gates, test plan, or monitoring plan.
- Prefer plain ASCII output.
- Avoid emoji/checkmark symbols.
- Avoid unnecessary nested Markdown code fences.
- Use requested headings exactly.

## Final Reporting Requirement

Before finishing, write the expected output file and include:
- Files changed
- What you did
- Validation performed
- Assumptions
- Warnings or uncertainty
