# Research Agent Prompt

## Agent Identity

You are the Research Agent for `story_041_v0_1_release_prep`.

## Story Name

`story_041_v0_1_release_prep`

## Story File Content

```markdown
# STORY-041: v0.1 Release Prep and License Decision

## Goal

Prepare the public repo for a clean v0.1 milestone with release process docs, release checklist, changelog structure, release notes updates, and explicit license guidance.

## Why This Matters

The repository is public and needs a repeatable release process that separates PR review from GitHub releases, preserves human owner approval, and avoids accidentally granting reuse rights without an explicit license decision.

## Acceptance Criteria

- Add Story 041 to blueprints/blueprint.yaml.
- Add docs/release_process.md.
- Add docs/v0_1_release_checklist.md.
- Add or update docs/release_notes_v0_1.md if needed.
- Add CHANGELOG.md if helpful.
- Update README.md to link to release docs.
- Update docs/public_launch_checklist.md if needed.
- Add or update tests that verify release docs exist and README links to them.
- docs/release_process.md explains what a release means for this repo.
- docs/release_process.md explains the difference between PR merge and GitHub release.
- docs/release_process.md lists pytest, Ruff, artifact-policy, public-readiness, runtime-config validate, project-status, and GitHub Actions as required checks.
- docs/release_process.md says human owner approval is required.
- docs/release_process.md says not to deploy anything automatically.
- docs/release_process.md says not to call cloud models automatically.
- docs/v0_1_release_checklist.md includes required v0.1 docs, contribution/security files, issue templates, public-readiness, license decision, GitHub metadata, CI, and release notes review.
- CHANGELOG.md includes a v0.1.0 unreleased or initial public release section.
- CHANGELOG.md summarizes blueprint-to-story workflow, story workspaces, prompt packs, review bundles, quality gates, test layers, queue loops, support queue, public-readiness guard, minimal demo, code tour, command map, and LangGraph workflow preview/run phases.
- If the human owner explicitly chooses MIT, add a standard MIT LICENSE file.
- If the human owner does not explicitly choose a license, do not add LICENSE.
- If no license is added, clearly document that default copyright applies and outside reuse is not granted automatically.
- Do not add new CLI behavior.
- Do not expose private prompts, secrets, generated runtime artifacts, or private strategy logic.

## Not In Scope

- No new CLI behavior.
- No cloud model calls.
- No automatic merge, deployment, repository visibility change, GitHub release creation, package publishing, or approval.
- No automatic license selection or LICENSE file creation without an explicit owner decision.
- No private prompts, private strategy guidance, secrets, generated runtime artifacts, or local-only operator details.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 041 prepare workflow-run passes.
- Story 041 local-finalize workflow-run passes.
- Story 041 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 041 but generated bundle files are not committed.
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
  evidence_or_reason: Add release documentation tests verifying release process and
    checklist docs exist, CHANGELOG.md exists, README links to release docs, v0.1
    checklist mentions required release checks, and release process requires human
    owner approval with no automatic deployment.
integration_tests:
  required: true
  action: confirm_existing
  frequency: every_pull_request
  evidence_or_reason: Existing CLI and workflow tests cover command behavior; this
    story changes public documentation only.
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
- missing_release_process_doc
- missing_v0_1_release_checklist
- missing_changelog
- stale_readme_link
- accidental_license_file
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
