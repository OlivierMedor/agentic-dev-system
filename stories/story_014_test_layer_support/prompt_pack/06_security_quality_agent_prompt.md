# Security/Quality Agent Prompt

## Agent Identity

You are the Security/Quality Agent for `story_014_test_layer_support`.

## Story Name

`story_014_test_layer_support`

## Story File Content

```markdown
# STORY-014: Add test layer support

## Goal

Create structured support for unit, integration, mock E2E, live read-only, and remote dev smoke test layers in story test plans and quality gates.

## Why This Matters

Every story should address the full testing picture. A story may add new tests, update existing tests, confirm existing coverage, or explain why a layer is not applicable. The quality gate should be able to verify that the required testing layers were addressed before human/cloud review.

## Acceptance Criteria

- Add a standard test layer schema for story test plans.
- Add an agentic test-layers command.
- test-layers validates that each testing layer is addressed.
- test-layers writes reports/test_layer_result.yaml.
- test-layers writes reports/test_layer_report.md.
- Story test plans support unit_tests, integration_tests, mock_e2e_tests, live_read_only_checks, and remote_dev_smoke_tests.
- Each layer must have required, action, frequency, and evidence_or_reason fields.
- Valid actions include add_or_update, update_existing, confirm_existing, not_applicable_with_reason, scheduled_later_with_reason.
- Update story generation so new stories get the full test layer template.
- Update prompt pack generation so Test Agent prompts explain the test layer requirements.
- Update quality gate so it checks test layer results when a story uses the new test layer schema.
- Update finalize-story so it runs test-layers before quality-gate when applicable.
- Add docs/test_layers.md explaining the testing layers.
- Add tests for the test layer validation logic.
- README is updated with usage instructions.

## Not In Scope

- No Playwright/Cypress/Selenium setup.
- No real live API calls.
- No remote dev environment yet.
- No actual deployment smoke tests yet.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- test-layers passes for story_014_test_layer_support.
- finalize-story marks this story ready for review.
```

## Agent Responsibility

Check for secrets, unsafe behavior, bad patterns, and quality risks.

## Expected Output

reports/security_quality_report.md

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
unit_tests:
  required: true
  action: add_or_update
  frequency: every_commit
  evidence_or_reason: Add unit tests for test layer validation logic.
integration_tests:
  required: true
  action: confirm_existing
  frequency: every_pull_request
  evidence_or_reason: Existing CLI tests and quality gate tests cover command integration.
frequency: TODO
```

## Monitoring Plan

```yaml
logs_required: true
watch_for:
- invalid_test_plan
- missing_test_layer_result
- missing_test_layer_evidence
- quality_gate_test_layer_failure
- finalize_story_test_layer_failure
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
```

## Runtime Expectation

- Provider: `codex`
- Model: `gpt-5.5`
- Approval mode: `workspace_write_no_prompt`
- Fallback provider: `manual_cloud_model`

## Agent-Specific Rule

Check for secrets, unsafe behavior, excessive permissions, and risky file access.

## Do-Not-Do Rules

- Do not commit anything.
- Do not create zip files.
- Do not make unrelated changes.
- Do not overwrite another agent's report unless explicitly instructed.
- Do not ignore project rules, quality gates, test plan, or monitoring plan.

## Final Reporting Requirement

Before finishing, write the expected output file and include:
- Files changed
- What you did
- Validation performed
- Assumptions
- Warnings or uncertainty
