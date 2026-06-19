# Local Models

Local models are language models that run on your own machine through a local
server, usually with an OpenAI-compatible HTTP API. For this project, that means
tools such as LM Studio or Ollama can expose a `/v1/chat/completions` endpoint
that `agentic-dev-system` can validate and call.

The goal is cost control and faster low-risk iteration. Local models can draft
documentation, summarize reports, compare implementation ideas, or produce test
drafts without sending every prompt to a paid cloud model. They are not a full
replacement for the configured coding runtime, human review, or cloud review on
high-risk work.

## Installed Vs Loaded

An installed model is present on disk. A loaded model is currently active in the
local runtime and ready to answer requests. A model can be installed but not
loaded, and in that state the CLI can validate configuration but the dry run
will fail until the local server loads the model.

## LM Studio And Ollama

LM Studio is a desktop app that can download models, load one into memory, and
serve an OpenAI-compatible API. A common local endpoint is:

```text
http://host.docker.internal:1234/v1
```

Ollama is a local model runner often used from the command line or background
service. Its OpenAI-compatible endpoint is commonly:

```text
http://host.docker.internal:11434/v1
```

Both tools run on the host machine, not inside this project's Docker container.
That keeps large model files, GPU access, and runtime memory outside the dev
container. From inside Docker, `host.docker.internal` is the hostname used to
reach services running on the host.

## Runtime Config

Add or update `.agentic/agent_runtime.yaml`:

```yaml
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

Set `enabled: true` only when a local server is running and the selected model
is loaded. `api_key_env` names an environment variable; the CLI does not record
or print its value.

## Commands

Validate the local runtime section:

```powershell
docker compose run --rm dev agentic local-model validate
```

Inspect resolved local-execution models without running them:

```powershell
docker compose run --rm dev agentic local-execute --story STORY_SLUG --dry-run
```

Run or resume blueprint-selected local roles with local models only:

```powershell
docker compose run --rm dev agentic local-execute --story STORY_SLUG
docker compose run --rm dev agentic local-execute --story STORY_SLUG --resume
```

For stories whose blueprint declares `subtasks:`, the same command executes
dependency-ready sub-tasks instead of the legacy role sequence. A dry run shows
each task ID, role, resolved model, estimated input tokens, usable input budget,
and readiness.

Example sub-task shape:

```yaml
subtasks:
  - id: define-subtask-schema
    title: Define blueprint sub-task schema
    role: developer
    depends_on: []
    requirement_ids:
      - AC-001
    required_context:
      files:
        - src/agentic_dev/local_execution.py
      summaries:
        - Preserve Story 060 behavior for blueprints without subtasks.
      prior_task_outputs: []
      architecture_decisions:
        - No cloud or Codex implementation fallback.
    writable_paths:
      - src/**
      - tests/**
      - stories/story_061/reports/**
    expected_outputs:
      - Schema helpers and tests.
    validation:
      - Unit tests pass.
    context_budget:
      max_input_tokens: 24000
      reserved_output_tokens: 4000
      required_context_must_fit: true
      allow_required_context_trimming: false
      oversized_task_policy: reject_for_cloud_redecomposition
```

The local runner assembles the full required prompt before calling a model. It
does not trim mandatory instructions or required context. It estimates input
size deterministically, reserves output capacity, and blocks any oversized task
with `cloud_redecomposition_required` before model invocation. Local agents are
not allowed to decompose oversized cloud-planned tasks; the cloud planner must
produce smaller blueprint tasks.

Completed sub-tasks persist concise handoff summaries. Downstream tasks may
consume only the dependency outputs and summaries declared in
`required_context.prior_task_outputs`, not unrestricted raw chat history.

Story 062 adds `agentic demo-subtasks` as an end-to-end operator demo for that same path. The default `--mode fake` adapter is deterministic, requires no network or local runtime, and is safe for CI. `--mode local` reuses the same parser, dependency graph, context-fit gate, writable-path enforcement, state persistence, handoff persistence, resume logic, and final validation, but swaps in the configured local OpenAI-compatible runtime adapter. There is no cloud fallback and no Codex fallback.

Demo commands:

```powershell
docker compose run --rm dev agentic demo-subtasks --mode fake --scenario success
docker compose run --rm dev agentic demo-subtasks --mode fake --scenario oversized
docker compose run --rm dev agentic demo-subtasks --mode fake --scenario resume --keep-workspace
docker compose run --rm dev agentic demo-subtasks --mode fake --scenario dependency-failure
docker compose run --rm dev agentic demo-subtasks --mode local --scenario success
```

The demo creates a temporary Python project, writes all generated files inside that sandbox only, rejects absolute-path escapes, path traversal, and symlink escapes, and refuses unsafe multi-file responses before any partial write is applied. By default it cleans up the sandbox on success or failure. `--keep-workspace` preserves it and prints the preserved path for inspection. Custom `--workspace-root` values are accepted only under safe temp roots.

Run a simple local call and save `reports/local_model_dry_run_report.md`:

```powershell
docker compose run --rm dev agentic local-model dry-run
```

Send a prompt file to the local model and save the raw response:

```powershell
docker compose run --rm dev agentic local-agent run-prompt --prompt-file prompt.md --output-file reports/local_agent_output.md
```

`local-agent run-prompt` saves output only. It does not apply code changes,
execute model output, commit, push, merge, deploy, call GitHub APIs, expose
secret values, or call cloud models. It also saves a sibling
`*_raw_response.json` file so empty or unusual OpenAI-compatible responses can
be debugged. Empty or whitespace-only content is treated as a failure.

Send story context to the local model and save a draft report plus
metadata:

```powershell
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-agent draft --story story_045_local_agent_draft_runner --agent docs_agent --model-label gemma-4-26b --prompt-mode slim --force
```

`--prompt-mode slim` is the default for local-agent drafts. It saves a smaller
context packet under `stories/STORY_SLUG/reports/local_agent_context/` before
calling the local model. `--prompt-mode micro` saves the smallest
final-answer-focused context packet for Gemma or other fragile local reasoning
models that return `reasoning_content` but empty visible `message.content`.
Full `prompt_pack` files are Codex-style and often too large for local models;
use `--prompt-mode full` only for debugging or stronger models. If a response
returns `finish_reason: length`, the saved draft may be truncated and the
metadata records a warning. Empty visible content is treated as
`empty_model_response`, even when hidden reasoning is populated.

See `docs/local_agent_drafts.md` for the save-only draft workflow,
`docs/local_agent_context_packets.md` for slim and micro context packets, prompt-file
mapping, runtime artifact policy, and human/cloud review boundary for high-risk
logic.

Create repeatable local-agent scorecard prompts, run them against a configured
local model, and create a manual report:

```powershell
docker compose run --rm dev agentic local-model scorecard-create --force
docker compose run --rm dev agentic local-model scorecard-run --model-label qwen3-coder-30b
docker compose run --rm dev agentic local-model scorecard-report
docker compose run --rm dev agentic local-model scorecard-scaffold-scores
docker compose run --rm dev agentic local-model scorecard-recommend
```

See `docs/local_model_scorecard.md` for the scorecard workflow and manual
comparison process. See `docs/local_model_role_assignment.md` for manual scoring
and role assignment.

## Recommended Model Roles

- Qwen3-Coder-30B-A3B-Instruct: developer drafts and test drafts.
- Devstral Small 2: agentic coding comparison.
- Qwen2.5-Coder-32B-Instruct: stable fallback for coding tasks.
- Gemma 4 26B/31B: docs, review, summaries, and reasoning.

Start local models on low-risk tasks: documentation drafts, summary generation,
review checklists, and test ideas. For high-risk logic, security-sensitive
changes, architecture decisions, release decisions, and merge readiness, keep
human review and configured cloud/human review in the loop.

## Safety Boundaries

Local model support is intentionally bounded:

- Local models do not replace Codex as the coding runtime yet.
- `agentic local-execute` does not fall back to Codex or cloud code-generation models.
- `local-agent` draft and prompt commands do not apply source changes automatically.
- `agentic local-execute` applies only bounded writes that stay inside the
  role's configured writable paths and records a blocked execution if a role
  attempts to write outside them.
- For blueprint sub-tasks, the same writable-path and resolved-path checks are
  applied per task. Symlink escapes and unsafe multi-file outputs are blocked
  before any partial write is applied.
- Oversized sub-tasks are rejected before local model invocation and returned
  for cloud redecomposition.
- Required instructions and required context are never silently trimmed.
- Local agents may not improvise decomposition of cloud-authored sub-tasks.
- Model responses are never executed as shell commands.
- The CLI does not commit, push, merge, deploy, or call GitHub APIs from local
  model output.
- Cloud models are not called by these commands.
- Human or configured runtime review still decides what to apply.
