# Test Agent Prompt

## Agent Identity

You are the Test Agent for `story_032_golden_path_operator_guide`.

## Story Name

`story_032_golden_path_operator_guide`

## Story File Content

```markdown
# STORY-032: Golden Path Operator Guide

## Goal

Create beginner-friendly operator documentation that explains how to use the
agentic-dev-system from blueprint to PR merge decision.

## Why

The project now has several workflow commands and review artifacts. Operators
need one plain-language guide that explains what each major artifact means, how
the normal path works, and where human approval is still required.

## Acceptance criteria

- Add `docs/golden_path.md`.
- Update `README.md` to link to `docs/golden_path.md`.
- Update `docs/langgraph_workflow.md` if needed.
- Add or update tests that verify `docs/golden_path.md` exists.
- Tests confirm the guide mentions the core commands.
- Tests confirm `README.md` links to `docs/golden_path.md`.
- The guide explains what the system is.
- The guide explains what lives in the project repo.
- The guide explains what lives in `.agentic/`.
- The guide explains what stories are.
- The guide explains what review bundles are.
- The guide explains what cloud review packets are.
- The guide explains what workflow-run phases are.
- The guide explains how support, improvement, maintenance, and feature queues differ.
- The guide explains the normal happy path.
- The guide explains what to do when a story is blocked.
- The guide explains what to do when tests or logs fail.
- The guide explains what not to commit.
- The guide explains what the human owner must still approve.
- The guide uses plain language and ASCII diagrams.
- Do not add new automation commands unless absolutely necessary.
- Do not change workflow behavior unless a documentation test requires a tiny supporting change.

## Not in scope

- No new CLI commands.
- No workflow behavior changes.
- No automatic cloud model calls.
- No GitHub API automation beyond any manually created PR.
- No merge, deployment, or auto-approval behavior.

## Definition of done

- `pytest` passes.
- `ruff check .` passes.
- `agentic artifact-policy` passes.
- `agentic runtime-config validate` passes.
- `agentic project-status` runs.
- Story reports are written for development, testing, docs, and local review.
```

## Agent Responsibility

Write independent tests based on the story acceptance criteria.

## Expected Output

reports/test_report.md

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
  evidence_or_reason: Add docs tests confirming the golden path guide exists, references required commands, and is linked from README.
integration_tests:
  required: true
  action: confirm_existing
  frequency: every_pull_request
  evidence_or_reason: Existing CLI and workflow tests cover command behavior; this story changes documentation only.
mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Existing mock E2E workflow coverage exercises the local story workflow.
live_read_only_checks:
  required: false
  action: not_applicable_with_reason
  frequency: scheduled_or_before_release
  evidence_or_reason: This documentation story does not call live external APIs.
remote_dev_smoke_tests:
  required: false
  action: not_applicable_with_reason
  frequency: after_remote_dev_deploy
  evidence_or_reason: This documentation story does not deploy to a remote dev environment.
```

## Monitoring Plan

```yaml
logs_required: false
watch_for:
  - missing_operator_command
  - stale_workflow_description
  - committed_generated_artifact
  - unclear_human_approval_boundary
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

Do not modify implementation code unless a tiny fix is required to make tests runnable, and explain any such fix.

Every story must address unit, integration, mock E2E, live read-only, and remote dev smoke test layers. You may add tests, update tests, confirm existing coverage, or explain why a layer is not applicable. Do not fake tests just to satisfy a layer; if a layer does not apply, provide a clear reason in test_plan.yaml or your report.

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
