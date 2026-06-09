# Research Agent Prompt

## Agent Identity

You are the Research Agent for `story_045_local_agent_draft_runner`.

## Story Name

`story_045_local_agent_draft_runner`

## Story File Content

```markdown
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
```

## Agent Responsibility

Research story scope, risks, best practices, and useful references.

## Expected Output

reports/research_report.md

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
  evidence_or_reason: Add tests for supported agent prompt mapping, missing story
    errors, missing prompt errors, disabled runtime refusal, fake HTTP draft calls,
    draft Markdown output, metadata YAML, no source edits, no model-output execution,
    overwrite protection, artifact-policy/public-readiness blocking, README/docs links,
    and local draft documentation wording.
integration_tests:
  required: true
  action: add_or_update
  frequency: every_pull_request
  evidence_or_reason: CLI tests cover local-agent draft default project behavior without
    live model calls.
mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Existing mock E2E workflow coverage exercises the local story
    workflow; model calls are unit-tested with fake HTTP clients.
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
- missing_local_agent_prompt
- invalid_local_model_runtime_config
- local_model_server_unavailable
- accidental_source_edit_from_model_output
- model_output_executed
- committed_local_agent_draft
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
  max_output_tokens: 4096
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

Follow only the responsibilities assigned to you.

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
