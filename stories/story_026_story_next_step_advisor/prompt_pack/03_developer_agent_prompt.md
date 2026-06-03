# Developer Agent Prompt

## Agent Identity

You are the Developer Agent for `story_026_story_next_step_advisor`.

## Story Name

`story_026_story_next_step_advisor`

## Story File Content

```markdown
# STORY-026: Add story next-step advisor

## Goal

Create a command that inspects a story workspace and recommends the next workflow action.

## Why This Matters

The agentic development system now has many commands and review gates. The user needs a simple way to ask "what should I do next for this story?" without manually checking every file. The advisor should inspect story state and recommend the next safe step.

## Acceptance Criteria

- Add a next-step command.
- next-step requires --story.
- next-step defaults --project to the current working directory.
- next-step validates that the story folder exists.
- next-step reads story status, agent plan, prompt pack, reports, review bundle, quality gate result, finalize result, cloud review result, merge readiness result, and remote dev validation result when present.
- next-step recommends prepare-story when agent_plan or prompt_pack is missing.
- next-step recommends running configured agent prompts when prompts exist but required agent reports are missing.
- next-step recommends finalize-story when required reports exist but finalize result is missing or stale.
- next-step recommends cloud-review-packet when finalize-story is ready and no cloud review packet exists.
- next-step recommends record-cloud-review when cloud review packet exists but cloud review result is missing.
- next-step recommends merge-readiness when cloud review result exists but merge readiness result is missing.
- next-step recommends remote-dev-packet when merge readiness exists and remote dev validation is not recorded.
- next-step recommends human PR/CI review when merge readiness and/or remote dev validation indicate readiness.
- next-step explains blocked/request-changes states clearly.
- next-step writes reports/next_step_report.md.
- next-step prints a beginner-friendly recommendation to the terminal.
- Tests verify next-step recommendations for common workflow states.
- README documents the next-step workflow.

## Not In Scope

- No automatic execution of recommended commands.
- No cloud API calls.
- No GitHub API calls.
- No automatic merge.
- No LangGraph yet.
- No web dashboard.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- next-step gives useful recommendations.
- finalize-story marks this story ready for review.
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
  evidence_or_reason: Add unit tests for next-step recommendation logic.
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
  evidence_or_reason: This story does not call live external APIs.
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
- missing_next_step_report
- inaccurate_next_step_recommendation
- unsafe_next_step_recommendation
- next_step_recommends_auto_merge
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

## Final Reporting Requirement

Before finishing, write the expected output file and include:
- Files changed
- What you did
- Validation performed
- Assumptions
- Warnings or uncertainty
