# Security/Quality Agent Prompt

## Agent Identity

You are the Security/Quality Agent for `story_031_workflow_run_cloud_review_prep`.

## Story Name

`story_031_workflow_run_cloud_review_prep`

## Story File Content

```markdown
# STORY-031: Add workflow-run cloud review prep phase

## Goal

Extend the LangGraph safe workflow runner with a cloud-review-prep phase that prepares cloud review evidence without calling cloud models.

## Why This Matters

The system already has safe prepare and local-finalize phases. The next safe phase is cloud review preparation: creating a cloud review packet and refreshing workflow preview evidence. This reduces manual steps while still avoiding automatic cloud model calls, GitHub API calls, merge, push, or deployment.


## Acceptance Criteria

- Extend workflow-run to support --phase cloud-review-prep.
- workflow-run cloud-review-prep requires --story.
- workflow-run cloud-review-prep defaults --project to the current working directory.
- workflow-run cloud-review-prep requires --execute before running safe steps.
- Without --execute, workflow-run cloud-review-prep writes a plan but does not run steps.
- With --execute, workflow-run cloud-review-prep runs cloud-review-packet and workflow-preview.
- cloud-review-prep should check whether finalize-story result is ready_for_review true before execution.
- If finalize-story is missing or not ready, cloud-review-prep should return REQUEST_CHANGES or a clear failed status instead of creating misleading cloud review evidence.
- workflow-run cloud-review-prep records graph nodes visited.
- workflow-run cloud-review-prep writes reports/workflow_run_result.yaml.
- workflow-run cloud-review-prep writes reports/workflow_run_report.md.
- workflow-run cloud-review-prep records planned steps and executed steps.
- workflow-run cloud-review-prep does not execute agents.
- workflow-run cloud-review-prep does not call cloud models.
- workflow-run cloud-review-prep does not call GitHub APIs.
- workflow-run cloud-review-prep does not commit, push, merge, deploy, or run destructive commands.
- next-step recommends workflow-run cloud-review-prep when finalize-story is ready and cloud_review_export.md is missing.
- README documents the cloud-review-prep phase.
- docs/langgraph_workflow.md explains prepare, local-finalize, and cloud-review-prep phases.
- Tests verify dry-run behavior, execute behavior, safe step sequence, readiness guard, and next-step integration.

## Not In Scope

- No automatic cloud model calls.
- No record-cloud-review automation.
- No GitHub API calls.
- No automatic merge.
- No deployment.
- No LangGraph checkpointing or persistence yet.
- No human-in-the-loop pause/resume yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- workflow-run cloud-review-prep dry-run works.
- workflow-run cloud-review-prep execute mode works after local-finalize is ready.
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
  evidence_or_reason: Add or update tests for workflow-run cloud-review-prep phase
    and next-step integration.
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
- workflow_run_cloud_review_prep_failure
- missing_finalize_ready_state
- accidental_cloud_call
- unsafe_command_attempt
- missing_cloud_review_export
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
