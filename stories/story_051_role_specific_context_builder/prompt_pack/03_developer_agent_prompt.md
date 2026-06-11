# Developer Agent Prompt

## Agent Identity

You are the Developer Agent for `story_051_role_specific_context_builder`.

## Story Name

`story_051_role_specific_context_builder`

## Story File Content

```markdown
# STORY-051: Role-Specific Context Builder

## Goal

Add a command that builds role-specific context packets for each assigned agent in a story so each agent receives the smallest complete context needed for its role instead of the whole repository.

## Why This Matters

Prompt packs tell agents what role they are playing. Context packets tell agents what information they need for that role. The workflow needs deterministic context packets before connecting assigned roles to future runtimes.

## Acceptance Criteria

- Add Story 051 to blueprints/blueprint.yaml.
- Add agentic build-context --story STORY_SLUG.
- Support --agent AGENT_ID, --all, optional --project, optional --force, and optional --target-chars defaulting to 8000.
- Add src/agentic_dev/role_context.py.
- Update src/agentic_dev/cli.py, README.md, docs/code_tour.md, and docs/command_map.md.
- Add docs/role_context_builder.md.
- Validate the story folder exists.
- Read agent_plan.yaml and build all assigned agents by default when neither --all nor --agent is provided.
- Do not overwrite existing context packets unless --force is used.
- Write packets to stories/STORY_SLUG/reports/role_context/AGENT_ID_context.md.
- Write stories/STORY_SLUG/reports/role_context_result.yaml and reports/role_context_report.md.
- Track included files, skipped files, estimated character count, and warnings.
- Shared context includes story.md, status.yaml when present, agent_plan.yaml, the specific agent instruction file, relevant .agentic/rules.yaml safety rules when present, and .agentic/agent_runtime.yaml runtime guidance when present.
- Role-specific packets follow the developer, test, docs, reviewer, security, research, and planner context rules described for this story.
- Each packet includes Agent identity, Story, Role responsibility, Shared premise, Role-specific context, Included files, Skipped files, Warnings, Expected output, Safety boundaries, and Suggested next command or handoff note.
- Result YAML includes story, agents_built, target_characters, status, context_packets, warnings, failed_checks, and false safety flags for cloud models, local models, executed agents, committed_or_merged, and deployed.
- Statuses include CONTEXT_READY, CONTEXT_READY_WITH_WARNINGS, and CONTEXT_FAILED.
- Generated role_context files are runtime artifacts and are blocked from tracking except .gitkeep.
- Do not call Codex, local models, cloud models, or execute agent prompts.
- Add tests for role context creation, all assigned agents, missing story, missing agent_plan, force overwrite, no overwrite without force, required role boundary text, reviewer evidence, excluded review/cloud packet content, result YAML, false safety flags, model/GitHub safety, and artifact-policy blocking generated role_context files.

## Not In Scope

- No Codex calls.
- No local model calls.
- No cloud model calls.
- No agent prompt execution.
- No automatic source edits from generated context.
- No automatic commit, push, merge, deploy, or GitHub API calls from the command.
- No committing generated review_bundle, cloud_review_packet, remote_dev_validation, local_agent_context, local_agent_drafts, or role_context packet files except allowed .gitkeep placeholders.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 051 generate-stories passes.
- Story 051 workflow-run prepare execute passes.
- Story 051 build-context command passes.
- Story 051 workflow-run local-finalize execute passes.
- Story 051 workflow-run cloud-review-prep execute passes.
- Review bundle is generated for Story 051 but generated bundle files are not committed.
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
  evidence_or_reason: Add deterministic tests for context packet generation, all-agent
    selection, validation errors, overwrite behavior, role boundary text, reviewer
    evidence inclusion, artifact exclusions, result YAML, safety flags, and artifact-policy
    blocking.
integration_tests:
  required: true
  action: add_or_update
  frequency: every_pull_request
  evidence_or_reason: CLI wiring is deterministic and covered through the command
    path without live models or GitHub API calls.
mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Existing workflow-run coverage exercises generated story workspaces;
    this command writes local reports only.
live_read_only_checks:
  required: false
  action: not_applicable_with_reason
  frequency: manual_only
  evidence_or_reason: The command reads local story files only and does not need live
    services.
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
- missing_agent_plan
- missing_instruction_file
- existing_context_without_force
- oversized_role_context_packet
- committed_role_context_packet
- review_bundle_content_leaked_to_developer_context
- cloud_review_packet_content_leaked_to_context
- local_model_call
- cloud_model_call
- codex_call
- agent_prompt_execution
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
