# STORY-042: Local OpenAI-Compatible Runtime Adapter

## Goal

Add local model runtime support so agentic-dev-system can validate and call local OpenAI-compatible model servers such as LM Studio or Ollama.

## Why This Matters

Local models can reduce cloud costs and support low-risk drafting while keeping code application, review, merge, deployment, and cloud review decisions under human or configured runtime control.

## Acceptance Criteria

- Add Story 042 to blueprints/blueprint.yaml.
- Add src/agentic_dev/local_model_runtime.py.
- Add agentic local-model validate.
- Add agentic local-model dry-run.
- Add agentic local-agent run-prompt.
- Commands default --project to the current working directory.
- local-model validate reads .agentic/agent_runtime.yaml and validates local_model_runtime when present.
- local-model validate requires provider local_openai_compatible, base_url, model, timeout_seconds, and boolean enabled.
- local-model dry-run sends a simple request to the configured local OpenAI-compatible endpoint.
- local-model dry-run saves reports/local_model_dry_run_report.md.
- local-agent run-prompt reads --prompt-file and writes raw model output to --output-file.
- local-agent run-prompt saves output only and does not apply code changes automatically.
- Add local model runtime examples to .agentic/agent_runtime.yaml.
- Add docs/local_models.md and link it from README.md.
- Tests use mocks or fakes and do not require a real model.

## Not In Scope

- No automatic source edits from local model output.
- No shell command execution from model output.
- No automatic commit, push, merge, deploy, or GitHub API calls.
- No replacement of Codex as the coding runtime yet.
- No cloud model calls.
- No secret exposure.

## Definition of Done

- docker compose build passes.
- pytest passes.
- ruff passes.
- artifact-policy passes.
- public-readiness passes.
- runtime-config validate passes.
- project-status runs.
- Story 042 prepare workflow-run passes.
- Story 042 local-finalize workflow-run passes.
- Story 042 cloud-review-prep workflow-run passes.
- Review bundle is generated for Story 042 but generated bundle files are not committed.
- Story reports are written for development, testing, and local review.
