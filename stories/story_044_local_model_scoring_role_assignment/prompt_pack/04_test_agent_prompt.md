# Test Agent Prompt

## Agent Identity

You are the Test Agent for `story_044_local_model_scoring_role_assignment`.

## Story Name

`story_044_local_model_scoring_role_assignment`

## Story File Content

```markdown
# STORY-044: Local Model Scoring and Role Assignment

## Goal

Add a formal way to record human scores for local model scorecard runs and generate recommended model assignments for agent roles.

## Why This Matters

Saved local model scorecard responses need a structured human scoring layer before any model is considered for role-specific local draft or report work.

## Acceptance Criteria

- Add Story 044 to blueprints/blueprint.yaml.
- Add scoring support to local model scorecard.
- Add docs/local_model_role_assignment.md.
- Update docs/local_model_scorecard.md.
- Update README.md if useful.
- Add agentic local-model scorecard-scaffold-scores.
- Add agentic local-model scorecard-recommend.
- scorecard-scaffold-scores accepts optional --project defaulting to the current working directory.
- scorecard-scaffold-scores reads .agentic/local_model_scorecard/results/ model folders if present.
- scorecard-scaffold-scores creates .agentic/local_model_scorecard/scorecard_scores.yaml.
- scorecard-scaffold-scores includes one scoring entry per model and role response found.
- scorecard-scaffold-scores does not overwrite scorecard_scores.yaml unless --force is used.
- Scores are blank/null by default.
- Score entries include model_label, role, response_file, instruction_following, correctness, hallucination_control, code_quality, test_quality, safety_compliance, clarity, overall_fit_for_role, speed_notes, and reviewer_notes.
- scorecard-recommend accepts optional --project defaulting to the current working directory.
- scorecard-recommend reads .agentic/local_model_scorecard/scorecard_scores.yaml.
- scorecard-recommend validates required scoring fields.
- scorecard-recommend ignores incomplete entries and reports them.
- scorecard-recommend computes role recommendations based on overall_fit_for_role first.
- scorecard-recommend uses safety_compliance, hallucination_control, correctness, and instruction_following as tie-breakers.
- scorecard-recommend writes reports/local_model_role_recommendations.md and reports/local_model_role_recommendations.yaml.
- scorecard-recommend does not automatically update .agentic/agent_runtime.yaml.
- scorecard-recommend does not claim a winner if scores are missing.
- Recommendation output includes best model per role, runner-up per role, scoring evidence summary, incomplete scoring warnings, safety recommendation, and a final note that the human owner controls runtime assignment.
- Supported roles are developer_agent, test_agent, docs_agent, reviewer_agent, and maintenance_agent.
- Local model prompts prefer plain ASCII, avoid emoji/checkmark symbols that can render poorly in Windows/PowerShell logs, avoid unnecessary nested whole-response Markdown code fences, and use requested headings exactly.
- Runtime scorecard result folders remain ignored.
- scorecard_scores.yaml and local_model_role_recommendations reports are ignored by Git and blocked by artifact-policy and public-readiness.
- Tests use fake result folders and manual YAML scores only.

## Not In Scope

- No automatic source edits from local model output.
- No shell command execution from model output.
- No cloud model calls.
- No automatic commit, push, merge, deploy, or GitHub API calls.
- No automatic changes to agent runtime defaults.
- No committing runtime scorecard result folders.
- No committing local scoring artifacts or recommendation reports by default.
- No secret exposure.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 044 prepare workflow-run passes.
- Story 044 local-finalize workflow-run passes.
- Story 044 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 044 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
```

## Agent Responsibility

Write independent tests based on the story acceptance criteria.

## Expected Output

reports/test_report.md

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
  evidence_or_reason: Add tests for scorecard-scaffold-scores creation and overwrite
    behavior, scorecard-recommend incomplete-score behavior, report creation from
    complete scores, overall-fit ranking, tie-breaker ranking, incomplete warnings,
    artifact/public-readiness blocking, docs existence and model/safety wording, and
    README/docs links.
integration_tests:
  required: true
  action: add_or_update
  frequency: every_pull_request
  evidence_or_reason: CLI tests cover scorecard-scaffold-scores default project behavior
    and scorecard-recommend report output using local fake files only.
mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Existing mock E2E workflow coverage exercises story workflow;
    recommendation logic is covered by focused unit tests.
live_read_only_checks:
  required: false
  action: not_applicable_with_reason
  frequency: manual_only
  evidence_or_reason: This story reads local files and human scores only; live model
    calls are not required.
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
- missing_scorecard_scores
- incomplete_score_entry
- invalid_score_field
- committed_scorecard_result
- committed_scorecard_scores
- committed_role_recommendation_report
- accidental_runtime_default_change
- cloud_model_call
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

Do not modify implementation code unless a tiny fix is required to make tests runnable, and explain any such fix.

Every story must address unit, integration, mock E2E, live read-only, and remote dev smoke test layers. You may add tests, update tests, confirm existing coverage, or explain why a layer is not applicable. Do not fake tests just to satisfy a layer; if a layer does not apply, provide a clear reason in test_plan.yaml or your report.

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
