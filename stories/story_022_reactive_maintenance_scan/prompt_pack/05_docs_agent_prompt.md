# Docs Agent Prompt

## Agent Identity

You are the Docs Agent for `story_022_reactive_maintenance_scan`.

## Story Name

`story_022_reactive_maintenance_scan`

## Story File Content

```markdown
# STORY-022: Add reactive maintenance scan

## Goal

Create commands that generate a maintenance scan packet from story/test/log evidence and record structured maintenance findings into the maintenance queue.

## Why This Matters

When tests, logs, CI, remote dev, or external integrations fail, agents should not guess or silently change code. The system should create a structured maintenance ticket that can be reviewed by the cloud model and human owner before becoming repair work.

## Acceptance Criteria

- Add maintenance-scan create command.
- Add maintenance-scan record command.
- maintenance-scan create requires --story.
- maintenance-scan create defaults --project to the current working directory.
- maintenance-scan create creates stories/<story>/maintenance/maintenance_scan_packet.md.
- maintenance-scan create creates stories/<story>/maintenance/maintenance_findings_template.yaml.
- maintenance-scan packet includes story content, monitoring plan, test plan, review bundle handoff, pytest output, ruff output, quality gate result, finalize result, and optional log files when present.
- maintenance-scan packet instructs the reviewer to identify broken behavior, regressions, or external dependency failures.
- maintenance-scan packet instructs the reviewer not to implement fixes automatically.
- maintenance-scan record requires --story and --findings-file.
- maintenance-scan record validates findings YAML.
- maintenance-scan record creates maintenance queue items under .agentic/maintenance_queue/pending.
- Each maintenance item includes source_story, severity, source_type, problem, evidence, suspected_cause, recommended_action, suggested_acceptance_criteria, and next_action.
- Tests verify packet creation, findings validation, and maintenance queue item creation.
- README documents the reactive maintenance workflow.

## Not In Scope

- No automatic repair.
- No automatic cloud model call.
- No internet lookup yet.
- No scheduled log monitor yet.
- No remote dev validation environment yet.
- No production incident workflow yet.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- maintenance-scan create works.
- maintenance-scan record works with a sample findings file.
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
  evidence_or_reason: Add unit tests for maintenance scan packet creation and findings
    recording.
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
  evidence_or_reason: No remote dev deployment environment exists yet.
```

## Monitoring Plan

```yaml
logs_required: true
watch_for:
- missing_maintenance_scan_packet
- invalid_maintenance_findings_yaml
- failed_maintenance_queue_recording
- accidental_auto_fix_attempt
- external_dependency_failure
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
