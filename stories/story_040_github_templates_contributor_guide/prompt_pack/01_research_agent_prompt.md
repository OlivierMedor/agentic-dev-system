# Research Agent Prompt

## Agent Identity

You are the Research Agent for `story_040_github_templates_contributor_guide`.

## Story Name

`story_040_github_templates_contributor_guide`

## Story File Content

```markdown
# STORY-040: GitHub Templates and Contributor Guide

## Goal

Add public GitHub collaboration files so visitors, future contributors, and the project owner have clear templates for issues, pull requests, security concerns, and contribution expectations.

## Why This Matters

Public repositories need clear contribution, security, pull request, and issue guidance that maps external collaboration into the existing story-scoped workflow without exposing private prompts, secrets, or generated runtime artifacts.

## Acceptance Criteria

- Add Story 040 to blueprints/blueprint.yaml.
- Add CONTRIBUTING.md.
- Add SECURITY.md.
- Add .github/pull_request_template.md.
- Add .github/ISSUE_TEMPLATE/bug_report.md.
- Add .github/ISSUE_TEMPLATE/feature_request.md.
- Add .github/ISSUE_TEMPLATE/improvement_suggestion.md.
- Add .github/ISSUE_TEMPLATE/config.yml if useful.
- Update README.md to link to CONTRIBUTING.md and SECURITY.md.
- Add or update tests verifying these public repo files exist and contain key safety wording.
- CONTRIBUTING.md explains the local-first agentic development workflow, issue or discussion expectation before large changes, story-scoped changes, tests and Ruff expectations, generated artifact exclusions, human review requirement, and maintainer control of roadmap and merge approval.
- SECURITY.md explains that secrets and vulnerabilities should not be reported in public issues, API keys, .env files, private prompts, and credentials must not be committed, the project does not execute production deployments or real-money workflows, sensitive reports should be handled privately, and the owner can add preferred contact details.
- The pull request template checks pytest, Ruff, artifact-policy, public-readiness, runtime-config validate, generated artifacts, secrets, story workspace updates, and human approval before merge.
- The bug report template maps reports to the maintenance queue.
- The feature request template maps requests to the feature queue.
- The improvement suggestion template maps suggestions to the improvement queue.
- Do not add new CLI behavior.
- Do not expose private prompts, private strategies, secrets, or generated runtime artifacts.

## Not In Scope

- No new CLI behavior.
- No cloud model calls.
- No automatic merge, deployment, repository visibility change, GitHub metadata change, or approval.
- No private prompts, private strategy guidance, secrets, generated runtime artifacts, or local-only operator details.
- No generated review bundle, cloud review packet, remote dev validation, support queue, or feature scan runtime files in the commit.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 040 prepare workflow-run passes.
- Story 040 local-finalize workflow-run passes.
- Story 040 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 040 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
```

## Agent Responsibility

Research story scope, risks, best practices, and useful references.

## Expected Output

reports/research_report.md

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
  evidence_or_reason: Add public repository tests verifying CONTRIBUTING.md, SECURITY.md,
    pull request template, issue templates, README links, safety wording, validation
    checklist wording, and queue mapping.
integration_tests:
  required: true
  action: confirm_existing
  frequency: every_pull_request
  evidence_or_reason: Existing CLI and workflow tests cover command behavior; this
    story changes public collaboration documentation and GitHub templates only.
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
  evidence_or_reason: This story reads and updates local documentation only and does
    not call live external APIs.
remote_dev_smoke_tests:
  required: false
  action: not_applicable_with_reason
  frequency: after_remote_dev_deploy
  evidence_or_reason: This story does not deploy to a remote dev environment.
```

## Monitoring Plan

```yaml
logs_required: false
watch_for:
- missing_contributing_doc
- missing_security_doc
- missing_pull_request_template
- missing_issue_template
- stale_readme_link
- private_guidance_tracked
- committed_generated_artifact
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
