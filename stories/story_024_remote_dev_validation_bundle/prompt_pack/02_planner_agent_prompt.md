# Planner Agent Prompt

## Agent Identity

You are the Planner Agent for `story_024_remote_dev_validation_bundle`.

## Story Name

`story_024_remote_dev_validation_bundle`

## Story File Content

```markdown
# STORY-024: Add remote dev validation bundle

## Goal

Create commands that prepare remote-dev validation instructions and record remote-dev validation results for a story.

## Why This Matters

Local tests and code review are not the same as proving the system works in a remote/dev-like environment. The system needs a structured way to collect deployment URL, logs, smoke test results, integration test results, environment checks, and validation outcomes before a human decides whether work is safe to move forward.

## Acceptance Criteria

- Add remote-dev-packet command.
- Add record-remote-dev command.
- remote-dev-packet requires --story.
- remote-dev-packet defaults --project to the current working directory.
- remote-dev-packet validates that the story folder exists.
- remote-dev-packet creates stories/<story>/remote_dev_validation/remote_dev_packet.md.
- remote-dev-packet creates stories/<story>/remote_dev_validation/remote_dev_result_template.yaml.
- The packet includes story content, test plan, monitoring plan, quality gate result, finalize result, cloud review result if present, and merge readiness result if present.
- The packet explains what remote dev evidence should be collected.
- The packet includes smoke test, integration test, log review, environment variable checklist, rollback notes, and known-risk sections.
- record-remote-dev requires --story and --result-file.
- record-remote-dev validates the result file.
- Accepted validation statuses are DEV_VALIDATED, DEV_VALIDATED_WITH_NOTES, DEV_FAILED, and NOT_RUN.
- record-remote-dev writes reports/remote_dev_validation_result.yaml.
- record-remote-dev writes reports/remote_dev_validation_report.md.
- DEV_VALIDATED updates status.yaml to remote_dev_validated.
- DEV_VALIDATED_WITH_NOTES updates status.yaml to remote_dev_validated_with_notes.
- DEV_FAILED updates status.yaml to remote_dev_failed.
- NOT_RUN updates status.yaml to remote_dev_not_run.
- record-remote-dev preserves story_id in status.yaml.
- The command does not deploy, commit, push, merge, or call cloud models.
- Runtime remote_dev_validation packet files are ignored by Git and blocked by artifact policy.
- Tests verify packet creation, template creation, result validation, status updates, and artifact policy behavior.
- README documents the remote dev validation workflow.

## Not In Scope

- No actual deployment.
- No remote environment provisioning.
- No production release bundle.
- No GitHub environment deployment.
- No cloud API calls.
- No automatic merge.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- remote-dev-packet works.
- record-remote-dev works with sample validation files.
- finalize-story marks this story ready for review.
```

## Agent Responsibility

Create a practical implementation plan for this story.

## Expected Output

reports/planner_report.md

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
  evidence_or_reason: Add unit tests for remote dev packet creation and remote dev
    result recording.
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
  action: scheduled_later_with_reason
  frequency: after_remote_dev_deploy
  evidence_or_reason: This story creates the remote dev validation bundle and result
    recording flow, but no remote dev environment exists yet.
```

## Monitoring Plan

```yaml
logs_required: true
watch_for:
- missing_remote_dev_packet
- invalid_remote_dev_result
- remote_dev_failed
- missing_smoke_test_evidence
- accidental_deploy_attempt
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
