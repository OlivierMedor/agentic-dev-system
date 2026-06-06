# Planner Agent Prompt

## Agent Identity

You are the Planner Agent for `story_034_public_launch_prep`.

## Story Name

`story_034_public_launch_prep`

## Story File Content

```markdown
# STORY-034: Public Launch Prep

## Goal

Prepare the repository for a future public launch with beginner-friendly public docs, launch checklist, architecture explanation, and repository hygiene tests.

## Why This Matters

The project is close to being public-ready, but new visitors need a clear README, system map, launch checklist, and explicit reminders about local-only artifacts before repository visibility changes.

## Acceptance Criteria

- Add Story 034 to blueprints/blueprint.yaml.
- Add docs/system_map.md with simple ASCII diagrams for the blueprint-to-story flow, story workspace structure, agent prompt pack flow, review bundle and quality gate flow, cloud review and merge readiness flow, queue loops, and LangGraph workflow-run phases.
- Add docs/public_launch_checklist.md with required local checks, repository hygiene checks, license reminder, CI check, and manual repository visibility step.
- Update README.md so public visitors quickly understand what the system is, why it exists, how the workflow works, core commands, current status, safety model, and docs links.
- Update docs/golden_path.md if needed.
- Update docs/public_readiness.md if needed.
- Add or update tests verifying the new public docs exist, README links to public docs, the sanitized architecture example exists, and private architecture guidance remains ignored and blocked by policy.
- Do not expose private strategy logic, private prompts, secrets, or local-only operator guidance.
- Do not commit blueprints/agentic-architecture.md.

## Not In Scope

- No new CLI commands.
- No workflow behavior changes.
- No automatic license selection.
- No cloud model calls.
- No GitHub API automation beyond opening the PR if available.
- No automatic merge, deployment, repository visibility change, or approval.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- docker compose build passes.
- Story reports are written for development, testing, and local review.
- Review bundle is generated for Story 034 but generated bundle files are not committed.
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
  evidence_or_reason: Add docs tests confirming docs/system_map.md and docs/public_launch_checklist.md
    exist, README links to required docs, and private architecture guidance is ignored
    and blocked by policy.
integration_tests:
  required: true
  action: confirm_existing
  frequency: every_pull_request
  evidence_or_reason: Existing CLI and workflow tests cover command behavior; this
    story changes public documentation and repository hygiene tests.
mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Existing mock E2E workflow coverage exercises the local story
    workflow.
live_read_only_checks:
  required: false
  action: not_applicable_with_reason
  frequency: scheduled_or_before_release
  evidence_or_reason: This story reads local files and does not call live external
    APIs.
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
- missing_public_doc
- stale_readme_link
- private_guidance_tracked
- committed_generated_artifact
- unclear_public_launch_instruction
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
