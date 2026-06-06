# Developer Agent Prompt

## Agent Identity

You are the Developer Agent for `story_038_public_metadata_release_readiness`.

## Story Name

`story_038_public_metadata_release_readiness`

## Story File Content

```markdown
# STORY-038: Public Metadata and Release Readiness

## Goal

Clean up the public repo status, GitHub metadata guidance, and first release-readiness docs.

## Why This Matters

The repository is public and needs current README wording, manual GitHub metadata guidance, v0.1 release notes, and tests that catch stale public-launch language.

## Acceptance Criteria

- Add Story 038 to blueprints/blueprint.yaml.
- Update README.md so it says the repo is public and under active development.
- Update README.md so it says the system is portfolio-ready v0.1 / early public version.
- Ensure README.md no longer says the repo is preparing for a future public launch.
- Keep the human-approval safety model clear.
- Keep README.md concise.
- Add docs/github_metadata.md with suggested GitHub description, topics, website field guidance, and manual setup steps.
- docs/github_metadata.md explains that GitHub description and topics are set manually in the GitHub UI.
- docs/github_metadata.md mentions that a portfolio website URL can be added later.
- Add docs/release_notes_v0_1.md summarizing v0.1 features and what is not included yet.
- docs/release_notes_v0_1.md mentions blueprint-to-story workflow, story workspaces, agent prompt packs, review bundles, quality gates, test layers, support/improvement/maintenance/feature queues, public-readiness guard, minimal demo project, code tour and command map, and LangGraph workflow-preview and workflow-run phases.
- Update docs/public_launch_checklist.md if needed.
- Update docs/repo_settings.md if needed.
- Add or update tests verifying README/public docs are current.
- Do not add new CLI features.
- Do not expose private prompts, secrets, generated runtime artifacts, or private strategy logic.
- Do not add a LICENSE file unless the owner explicitly requested it.
- Keep license guidance as a decision the owner still controls.

## Not In Scope

- No new CLI features.
- No cloud model calls.
- No automatic merge, deployment, repository visibility change, GitHub metadata change, or approval.
- No automatic license selection or LICENSE file creation.
- No private prompts, private strategy guidance, secrets, generated runtime artifacts, or local-only operator details.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 038 prepare workflow-run passes.
- Story 038 local-finalize workflow-run passes.
- Story 038 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 038 but generated bundle files are not committed.
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
  evidence_or_reason: Add public-doc tests verifying README says public and under
    active development, does not contain stale future-launch wording, docs/github_metadata.md
    and docs/release_notes_v0_1.md exist, metadata contains the suggested description
    and topics, and release notes mention LangGraph, review bundles, quality gates,
    and minimal demo.
integration_tests:
  required: true
  action: confirm_existing
  frequency: every_pull_request
  evidence_or_reason: Existing CLI and workflow tests cover command behavior; this
    story changes documentation and repository metadata guidance only.
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
- stale_public_launch_wording
- missing_github_metadata_doc
- missing_release_notes
- missing_metadata_topic
- committed_generated_artifact
- private_guidance_tracked
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
