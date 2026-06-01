# Docs Agent Prompt

## Agent Identity

You are the Docs Agent for `story_019_queue_management`.

## Story Name

`story_019_queue_management`

## Story File Content

```markdown
# STORY-019: Add queue management commands

## Goal

Create commands for managing improvement, maintenance, and feature queue items.

## Why This Matters

The system needs a structured way to capture future improvements, maintenance issues, and new feature ideas without expanding the current story scope. These queues let agents propose work, while the human owner and cloud model decide what becomes a future story.

## Acceptance Criteria

- Add queue create command.
- Add queue list command.
- Add queue show command.
- Add queue set-status command.
- Supported queue types are improvement, maintenance, and feature.
- queue create writes a structured YAML item into the selected queue pending folder.
- queue items include id, queue_type, title, source_story, category, priority, status, details, created_at, and next_action.
- improvement items use prefix IMP.
- maintenance items use prefix MAINT.
- feature items use prefix FEATURE.
- queue list shows pending, approved, rejected, parked, and closed items.
- queue show prints one item clearly.
- queue set-status moves an item between pending, approved, rejected, parked, and closed.
- queue set-status records a decision note.
- project-status includes queue counts for improvement, maintenance, and feature queues.
- README documents the queue workflow.
- Tests verify queue creation, listing, showing, status changes, invalid queue types, and project-status queue counts.

## Not In Scope

- No automatic story creation from approved queue items yet.
- No internet research agent yet.
- No automatic Maintenance Monitor Agent yet.
- No cloud API calls.
- No LangGraph yet.
- No web dashboard.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- queue commands work on tmp_path in tests.
- project-status shows queue counts.
- finalize-story marks this story ready for review.
```

## Agent Responsibility

Update documentation related to this story.

## Expected Output

reports/docs_report.md

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
  evidence_or_reason: Add unit tests for queue item creation, listing, showing, and
    status transitions.
integration_tests:
  required: true
  action: confirm_existing
  frequency: every_pull_request
  evidence_or_reason: Existing command tests cover CLI integration patterns.
mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Existing mock E2E workflow test covers the local story workflow.
live_read_only_checks:
  required: false
  action: not_applicable_with_reason
  frequency: scheduled_or_before_release
  evidence_or_reason: This story does not call live APIs or external services.
remote_dev_smoke_tests:
  required: false
  action: not_applicable_with_reason
  frequency: after_remote_dev_deploy
  evidence_or_reason: No remote dev environment exists yet.
```

## Monitoring Plan

```yaml
logs_required: true
watch_for:
- invalid_queue_type
- missing_queue_item
- invalid_queue_status
- failed_queue_status_move
- inaccurate_queue_counts
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
```

## Runtime Expectation

- Provider: `local_model_optional`
- Model: `qwen_coder_or_codex_fallback`
- Approval mode: `workspace_write_no_prompt`
- Fallback provider: `codex`

## Agent-Specific Rule

Follow only the responsibilities assigned to you.

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
