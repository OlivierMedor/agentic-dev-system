# Docs Agent Prompt

## Agent Identity

You are the Docs Agent for `story_020_promote_queue_item_to_story`.

## Story Name

`story_020_promote_queue_item_to_story`

## Story File Content

```markdown
# STORY-020: Promote approved queue item to story

## Goal

Create a command that turns an approved improvement, maintenance, or feature queue item into a new story entry and story workspace.

## Why This Matters

Queue items should not become work automatically. Once the human owner and/or cloud model approve a queue item, the system needs a controlled way to promote it into the blueprint and generate a proper story workspace.

## Acceptance Criteria

- Add queue promote-to-story command.
- promote-to-story requires --item.
- promote-to-story defaults --project to the current working directory.
- promote-to-story finds queue items in improvement, maintenance, and feature queues.
- By default, only approved queue items can be promoted.
- The command accepts optional --allow-pending for manual override.
- The command creates a new story entry in blueprints/blueprint.yaml.
- The command generates a story id using the next available STORY number.
- The command generates a safe slug from the queue item title.
- The command creates a story workspace using existing story generation logic.
- The generated story includes acceptance criteria, not-in-scope, definition of done, test plan, and monitoring plan.
- The command writes a promotion report.
- The command records promoted_story_id and promoted_story_slug back into the queue item.
- The command can optionally move the queue item to closed or parked after promotion.
- Tests verify promotion behavior for improvement, maintenance, and feature queue items.
- README documents the promote-to-story workflow.

## Not In Scope

- No automatic cloud model approval.
- No automatic story execution.
- No automatic merge.
- No internet research agent yet.
- No Maintenance Monitor Agent yet.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- promote-to-story creates a valid story from an approved queue item.
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
  evidence_or_reason: Add unit tests for promoting approved queue items into stories.
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
- missing_queue_item
- queue_item_not_approved
- invalid_story_id_generation
- invalid_story_slug_generation
- blueprint_update_failure
- story_generation_failure
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
