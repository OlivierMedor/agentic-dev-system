# Research Agent Prompt

## Agent Identity

You are the Research Agent for `story_011_artifact_policy_guard`.

## Story Name

`story_011_artifact_policy_guard`

## Story File Content

```markdown
# STORY-011: Add generated artifact policy guard

## Goal

Create a command and CI check that prevents generated review artifacts from being committed.

## Why This Matters

Review bundles and cloud review packets are generated evidence. They should be regenerated as needed, not permanently committed. CI should fail if generated artifacts are accidentally tracked.

## Acceptance Criteria

- Add an artifact-policy command.
- The command defaults --project to the current working directory.
- The command checks tracked Git files.
- The command fails if generated review bundle files are tracked.
- The command fails if generated cloud review packet files are tracked.
- The command fails if review_to_chatgpt files are tracked.
- The command fails if zip files are tracked.
- The command fails if .env or .env.* files are tracked, except .env.example.
- .gitkeep files inside generated artifact folders are allowed.
- CI runs the artifact-policy command.
- Tests verify allowed and blocked paths.
- README and docs/ci_cd.md are updated.

## Not In Scope

- No secret scanning engine yet.
- No dependency vulnerability scanning yet.
- No production deployment.
- No cloud model review automation.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes on the current repo.
- CI workflow includes artifact-policy.
- tracked generated artifacts would fail the policy.
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
unit_tests: true
integration_tests: false
frequency: every_commit
```

## Monitoring Plan

```yaml
logs_required: true
watch_for:
- committed_review_bundle
- committed_cloud_review_packet
- committed_zip_file
- committed_env_file
- ci_artifact_policy_failure
```

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
