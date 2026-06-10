# Developer Agent Prompt

## Agent Identity

You are the Developer Agent for `story_050_micro_readiness_workflow_integration`.

## Story Name

`story_050_micro_readiness_workflow_integration`

## Story File Content

```markdown
# STORY-050: Micro-Readiness Workflow Integration

## Goal

Integrate micro-readiness into the normal workflow so story sizing guidance is visible in project-status, next-step, and workflow-run prepare.

## Why This Matters

Story 049 added the deterministic micro-readiness checker. The normal workflow should now surface that checker at the points where operators decide whether a story should be split, use micro or slim local prompts, or use a stronger configured agent runtime.

## Acceptance Criteria

- Add Story 050 to blueprints/blueprint.yaml.
- Update workflow-run prepare so dry-run planned steps include prepare-story, micro-readiness, and workflow-preview.
- Update workflow-run prepare execute mode so it runs prepare-story, micro-readiness, and workflow-preview.
- workflow_run_result.yaml records the micro-readiness step result.
- workflow-run safety flags remain false for agent execution, cloud models, GitHub APIs, commits, merges, deployment, destructive commands, and arbitrary commands.
- project-status reads reports/micro_readiness_result.yaml when present.
- project-status displays micro_readiness_status for each story and warning count when available.
- project-status shows not recorded when micro-readiness is missing.
- project-status handles malformed micro_readiness_result.yaml gracefully.
- next-step recommends micro-readiness when agent_plan.yaml and prompt_pack exist but reports/micro_readiness_result.yaml is missing.
- next-step continues normal workflow for READY_FOR_MICRO.
- next-step explains warnings for MICRO_READY_WITH_WARNINGS without treating them as automatic failure.
- next-step recommends splitting the story or using a stronger configured agent runtime for TOO_LARGE_FOR_MICRO.
- next-step does not recommend automatic merge or deployment.
- Use configured agent runtime wording rather than Codex-only wording.
- Update README.md and docs/micro_readiness.md for the integrated workflow.
- Add or update tests for workflow-run prepare, project-status, and next-step behavior.

## Not In Scope

- No local model calls.
- No cloud model calls.
- No generated prompt execution.
- No autonomous merge behavior.
- No deployment behavior.
- No GitHub API calls except manual PR creation tooling after local validation.
- No committing generated review_bundle, cloud_review_packet, remote_dev_validation, local_agent_context, or local_agent_drafts artifacts.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 050 generate-stories passes.
- Story 050 workflow-run prepare execute passes.
- Story 050 micro-readiness command passes.
- Story 050 workflow-run local-finalize execute passes.
- Story 050 workflow-run cloud-review-prep execute passes.
- Review bundle is generated for Story 050 but generated bundle files are not committed.
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
  evidence_or_reason: Add tests for workflow-run prepare dry-run and execute step
    sequence, micro-readiness step result recording, project-status display and malformed
    handling, next-step missing micro-readiness guidance, TOO_LARGE_FOR_MICRO guidance,
    READY_FOR_MICRO continuation, and warning guidance.
integration_tests:
  required: true
  action: add_or_update
  frequency: every_pull_request
  evidence_or_reason: CLI paths are covered by existing workflow-run, project-status,
    and next-step tests without real local or cloud model calls.
mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Existing workflow-run coverage exercises deterministic local
    story phases; this story extends the prepare allowlist only.
live_read_only_checks:
  required: false
  action: not_applicable_with_reason
  frequency: manual_only
  evidence_or_reason: Micro-readiness reads local story files only and does not require
    live model servers or cloud credentials.
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
- missing_micro_readiness_result
- malformed_micro_readiness_result
- oversized_micro_prompt_estimate
- story_should_be_split
- workflow_prepare_safety_flag_regression
- local_model_call
- cloud_model_call
- generated_prompt_execution
- automatic_merge_or_deploy
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
