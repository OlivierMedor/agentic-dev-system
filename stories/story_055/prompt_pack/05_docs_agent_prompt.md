# Docs Agent Prompt

## Agent Identity

You are the Docs Agent for `story_055`.

## Story Name

`story_055`

## Story File Content

```markdown
﻿# Story 055 — One-command story runner

## Goal

Add a one-command story runner so a user can run a complete local story workflow without manually opening prompt files or pasting agent prompts.

Desired commands:

agentic run-story --story <story-folder-or-slug> --execute

agentic run-next-story --execute

## Problem

The current workflow has useful pieces, but the user has to manually connect them.

Current pieces include:

- generate-stories
- workflow-run prepare
- build-context
- codex-task
- manual prompt execution
- workflow-run local-finalize
- cloud review
- merge readiness

The blueprint should feel like the first domino in an automated chain.

## Scope

Implement the first version of one-command story execution.

This story should run one story only.

It should not merge automatically.
It should not deploy.
It should not run stories in parallel.

## Required behavior

The command should:

1. Resolve the target project folder.
2. Resolve the story by folder name or slug.
3. Run or reuse story preparation.
4. Assign agents if needed.
5. Generate prompts if needed.
6. Build context if needed.
7. Create Codex/local-agent task files if needed.
8. Run the configured automatic agent runtime if available.
9. Fail clearly if no automatic runtime is configured.
10. Detect missing required agent reports.
11. Run local finalize.
12. Run quality gate.
13. Update story status.
14. Stop before merge.
15. Print the next action for the human owner.

## Safety rules

The command must not:

- merge branches
- push to git
- deploy
- open PRs automatically
- modify unrelated story folders
- pick stories alphabetically
- run future stories unless explicitly requested
- continue after quality gate failure
- continue after missing required reports

## Acceptance criteria

- CLI exposes agentic run-story --story <story>.
- CLI exposes agentic run-next-story if feasible.
- run-story can resolve a story by exact folder name.
- run-story can resolve a story by slug if metadata supports it.
- run-story without --execute prints or writes a plan only.
- run-story --execute performs safe local workflow steps in order.
- If no automatic runtime is configured, the command stops with a clear error.
- The command does not merge, push, deploy, or open PRs.
- Tests cover story resolution, dry-run planning, missing runtime behavior, and no-auto-merge safety.
- Existing tests continue to pass.
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
# Not found: test_plan.yaml
```

## Monitoring Plan

```yaml
# Not found: monitoring_plan.yaml
```

## Runtime Config

```yaml
agents:
  research_agent:
    provider: codex
    model: gpt-5.4-mini
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  planner_agent:
    provider: codex
    model: gpt-5.4
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  developer_agent:
    provider: codex
    model: gpt-5.4
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  test_agent:
    provider: codex
    model: gpt-5.4
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  docs_agent:
    provider: codex
    model: gpt-5.4-mini
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

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

  local_model_helper:
    provider: local_model_optional
    model: gemma-4-26b
    prompt_mode: micro
    approval_mode: workspace_write_no_prompt
    fallback_provider: codex

command_policy:
  allowed_without_approval:
    - docker compose build
    - docker compose run --rm dev pytest
    - docker compose run --rm dev ruff check .
    - docker compose run --rm dev agentic generate-stories
    - docker compose run --rm dev agentic prepare-story
    - docker compose run --rm dev agentic build-context
    - docker compose run --rm dev agentic codex-task create
    - docker compose run --rm dev agentic workflow-run
    - docker compose run --rm dev agentic review-bundle
    - docker compose run --rm dev agentic quality-gate
    - docker compose run --rm dev agentic test-layers
    - docker compose run --rm dev agentic finalize-story
    - docker compose run --rm dev agentic artifact-policy
    - docker compose run --rm dev agentic public-readiness
    - docker compose run --rm dev agentic runtime-config validate
    - docker compose run --rm dev agentic project-status

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
  enabled: false
  provider: local_openai_compatible
  base_url: http://host.docker.internal:1234/v1
  model: qwen3-coder-30b-a3b-instruct
  api_key_env: LOCAL_MODEL_API_KEY
  timeout_seconds: 120
  max_output_tokens: 4096
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
- Model: `gpt-5.4-mini`
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
