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
secret values, or call cloud models.

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
- Local model output is not applied to source files automatically.
- Model responses are never executed as shell commands.
- The CLI does not commit, push, merge, deploy, or call GitHub APIs from local
  model output.
- Cloud models are not called by these commands.
- Human or configured runtime review still decides what to apply.
