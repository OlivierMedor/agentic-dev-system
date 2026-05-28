# Local Reviewer Agent Prompt

## Agent Identity

You are the Local Reviewer Agent for `story_008_finalize_story_command`.

## Story Name

`story_008_finalize_story_command`

## Story File Content

```markdown
# STORY-008: Add finalize-story command

## Goal

Create a command that finalizes a story by generating a review bundle, running the quality gate, regenerating the review bundle, writing a finalize report, and updating story status.

## Why This Matters

The system should reduce manual final review steps after agent work is completed. One command should collect evidence, run the quality gate, record the result, and mark the story ready for human/cloud review or request changes.

## Acceptance Criteria

- Add a finalize-story command.
- The command requires --story.
- The command defaults --project to the current working directory.
- The command accepts optional --force.
- The command validates that the story folder exists.
- The command creates or refreshes the review bundle.
- The command runs the quality gate.
- The command regenerates the review bundle after the quality gate so final evidence is captured.
- The command writes reports/finalize_story_report.md.
- The command writes reports/finalize_story_result.yaml.
- If the quality gate returns READY_FOR_REVIEW, the command updates status.yaml to ready_for_review true.
- If the quality gate returns REQUEST_CHANGES, the command updates status.yaml to request_changes and ready_for_review false.
- The command does not commit, push, merge, deploy, or call cloud models.

## Not In Scope

- No automatic Git commits.
- No automatic GitHub PR creation.
- No cloud model review yet.
- No remote dev validation yet.
- No production deployment.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- finalize-story creates review bundle evidence.
- finalize-story creates quality gate outputs.
- finalize-story creates finalize report files.
- finalize-story updates status.yaml safely.
```

## Agent Responsibility

Review all work and decide whether it is ready for cloud/human review.

## Expected Output

reports/local_review_report.md

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
- missing_story_folder
- review_bundle_failure
- quality_gate_failure
- invalid_status_update
- missing_finalize_report
```

## Agent-Specific Rule

Do not approve unless pytest and Ruff pass.

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
