# Developer Agent Prompt

## Agent Identity

You are the Developer Agent for `story_049_micro_readiness_story_sizing`.

## Story Name

`story_049_micro_readiness_story_sizing`

## Story File Content

```markdown
# STORY-049: Micro-Readiness and Story Sizing Guard

## Goal

Add a deterministic micro-readiness check that helps decide whether each assigned agent's responsibility can be summarized in a clear local-model micro prompt.

## Why This Matters

Micro local-agent prompts are most useful when each agent has a focused task. The workflow needs an explicit sizing guard that warns when a story is too broad, too vague, or too large for agent-specific micro-mode assignments.

## Acceptance Criteria

- Add Story 049 to blueprints/blueprint.yaml.
- Add an agentic micro-readiness command.
- The command requires --story.
- The command defaults --project to the current working directory.
- The command accepts optional --target-chars with default 2000.
- The command validates that the story folder exists.
- The command reads story.md.
- The command reads agent_plan.yaml if present.
- The command reads instructions/ if present.
- The command estimates whether each core agent could receive a micro prompt under the target size.
- The command writes reports/micro_readiness_result.yaml.
- The command writes reports/micro_readiness_report.md.
- The command prints a beginner-friendly summary.
- Result statuses include READY_FOR_MICRO, MICRO_READY_WITH_WARNINGS, TOO_LARGE_FOR_MICRO, and NEEDS_REVIEW.
- The check covers story goal length, acceptance criteria count, not-in-scope clarity, Definition of Done clarity, agent plan existence, assigned-agent responsibilities, per-agent prompt estimates, broad module touch, and split signals.
- Missing story.md returns NEEDS_REVIEW.
- Missing agent_plan.yaml returns a warning or NEEDS_REVIEW.
- More than 10 acceptance criteria warns.
- More than 15 acceptance criteria is likely TOO_LARGE_FOR_MICRO.
- Missing or empty not-in-scope warns.
- Per-agent estimates use story slug, agent id, responsibility, story goal, top five acceptance criteria, expected output, safety rules, and final-visible-answer instruction.
- docs/micro_readiness.md explains micro readiness, micro mode, small local-model prompts, context limits, story versus agent-task sizing, command usage, and status meanings.
- docs/story_sizing.md explains that stories should be narrow enough for clear acceptance criteria, large enough for all agents, and micro-summarizable per agent.
- README.md includes a concise link or mention.
- Tests cover missing story folders, focused stories, many acceptance criteria, missing not-in-scope, missing agent_plan, per-agent estimates, result YAML, report Markdown, target override, no local model calls, no cloud model calls, and no real Git repo requirement.

## Not In Scope

- No local model calls.
- No cloud model calls.
- No agent execution.
- No source changes based on model output.
- No automatic commit, push, merge, deploy, or GitHub API calls from the command.
- No replacement for human story sizing judgment.
- No generated review bundle, cloud review packet, remote dev validation, local_agent_context, or local_agent_drafts artifacts committed.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 049 generate-stories passes.
- Story 049 prepare workflow-run passes.
- Story 049 micro-readiness command passes.
- Story 049 local-finalize workflow-run passes.
- Story 049 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 049 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
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
  evidence_or_reason: Add deterministic tests for story-folder validation, focused
    story readiness, acceptance-criteria sizing warnings, missing boundaries, missing
    agent plans, per-agent estimates, report outputs, target override, no model calls,
    and no Git repo dependency.
integration_tests:
  required: true
  action: add_or_update
  frequency: every_pull_request
  evidence_or_reason: CLI coverage verifies micro-readiness command wiring, default
    project behavior, target override handling, and model-call safety without live
    models.
mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Existing workflow-run coverage exercises story workspace preparation
    and finalization; this command is deterministic and tested through the CLI path.
live_read_only_checks:
  required: false
  action: not_applicable_with_reason
  frequency: manual_only
  evidence_or_reason: The command reads local story files only and does not require
    live services or model servers.
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
- missing_story_folder
- missing_story_file
- missing_agent_plan
- oversized_micro_prompt_estimate
- vague_story_goal
- too_many_acceptance_criteria
- missing_not_in_scope
- story_should_be_split
- local_model_call
- cloud_model_call
- agent_execution
- accidental_source_edit_from_model_output
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

local_model_runtime:
  enabled: true
  provider: local_openai_compatible
  base_url: http://host.docker.internal:1234/v1
  model: google/gemma-4-26b-a4b-qat
  api_key_env: LOCAL_MODEL_API_KEY
  timeout_seconds: 120
  max_output_tokens: 8192
  temperature: 0.2

local_model_profiles:
  lm_studio:
    base_url: http://host.docker.internal:1234/v1
    api_key_hint: lm-studio
  ollama:
    base_url: http://host.docker.internal:11434/v1
    api_key_hint: ollama
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
- Prefer plain ASCII output.
- Avoid emoji/checkmark symbols.
- Avoid unnecessary nested Markdown code fences.
- Use requested headings exactly.

## Final Reporting Requirement

Before finishing, write the expected output file and include:
- Files changed
- What you did
- Validation performed
- Assumptions
- Warnings or uncertainty
