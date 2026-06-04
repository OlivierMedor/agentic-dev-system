# Security/Quality Agent Prompt

## Agent Identity

You are the Security/Quality Agent for `story_029_workflow_run_status_integration`.

## Story Name

`story_029_workflow_run_status_integration`

## Story File Content

```markdown
# STORY-029: Integrate workflow-run into project status and next-step

## Goal

Update project-status and next-step so they understand workflow_run_result.yaml and recommend workflow-run for safe local finalization when appropriate.

## Why This Matters

The system now has a LangGraph safe workflow runner. The dashboard and next-step advisor should use workflow-run evidence so the user can see whether a story's safe local workflow was executed and what should happen next.

## Acceptance Criteria

- project-status reads reports/workflow_run_result.yaml when present.
- project-status displays workflow-run phase, status, executed flag, and safety flags.
- project-status includes workflow-run status in reports/project_status_report.md.
- next-step reads reports/workflow_run_result.yaml when present.
- next-step recommends workflow-run local-finalize when required local finalization evidence is missing or stale.
- next-step recommends cloud-review-packet after workflow-run local-finalize completes and finalize-story is ready.
- next-step does not require workflow-run when manual finalize evidence is already valid.
- next-step does not recommend automatic merge or deployment.
- README documents how workflow-run fits into the normal story lifecycle.
- docs/langgraph_workflow.md is updated to show preview versus workflow-run versus future orchestration.
- Tests verify project-status and next-step behavior with workflow_run_result.yaml.

## Not In Scope

- No new LangGraph phases.
- No automatic agent execution.
- No cloud model calls.
- No GitHub API calls.
- No automatic merge.
- No deployment.
- No LangGraph checkpointing yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- project-status shows workflow-run status.
- next-step recommends the correct safe next action.
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
test_layers_version: 1
unit_tests:
  required: true
  action: add_or_update
  frequency: every_commit
  evidence_or_reason: Add or update unit tests for workflow-run status detection in
    project-status and next-step.
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
- missing_workflow_run_status
- inaccurate_next_step_recommendation
- unsafe_workflow_run_recommendation
- workflow_run_status_parse_error
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
