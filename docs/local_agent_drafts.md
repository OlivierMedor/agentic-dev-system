# Local Agent Drafts

Local agent drafts send one story prompt-pack file to the configured local
OpenAI-compatible model and save the model response as a draft report. The
command is intentionally save-only: it does not edit source files, execute model
output, call cloud models, call GitHub APIs, commit, push, merge, or deploy.

Use drafts when a local model can help produce first-pass documentation, test
ideas, review notes, maintenance triage, or developer implementation notes for a
specific story. Human/Codex review must decide what, if anything, to apply.

## Why Save-Only First

Local models can be useful but they are not trusted to change this repository
directly. Saving output first creates an inspectable artifact and keeps the
coding runtime, review decision, merge decision, and deployment decision under
human/Codex control.

Local agent draft outputs are runtime artifacts. They belong under
`stories/<story>/reports/local_agent_drafts/` and must remain untracked except
for optional `.gitkeep` files.

## Load A Model In LM Studio

1. Open LM Studio.
2. Download or select a model such as Gemma, Devstral, or Qwen.
3. Load one model into memory.
4. Start the local server with an OpenAI-compatible endpoint, commonly
   `http://localhost:1234/v1` on the host.
5. In Docker, configure `.agentic/agent_runtime.yaml` with
   `http://host.docker.internal:1234/v1`.

Gemma is a good first choice for docs, test, reviewer, and maintenance drafts.
Devstral is preferred for developer drafts when the prompt is code-heavy. Qwen
is useful as a fallback or comparison model.

## Runtime Config

Set `local_model_runtime.enabled: true` only when LM Studio or another local
OpenAI-compatible server is running and the selected model is loaded:

```yaml
local_model_runtime:
  enabled: true
  provider: local_openai_compatible
  base_url: http://host.docker.internal:1234/v1
  model: gemma-4-26b
  api_key_env: LOCAL_MODEL_API_KEY
  timeout_seconds: 120
  max_output_tokens: 4096
  temperature: 0.2
```

## Run A Draft

```powershell
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-agent draft --story <story> --agent docs_agent --model-label gemma-4-26b
```

Supported agents:

- `developer_agent`
- `test_agent`
- `docs_agent`
- `reviewer_agent`
- `maintenance_agent`

Default prompt files:

- `developer_agent`: `prompt_pack/03_developer_agent_prompt.md`
- `test_agent`: `prompt_pack/04_test_agent_prompt.md`
- `docs_agent`: `prompt_pack/05_docs_agent_prompt.md`
- `reviewer_agent`: `prompt_pack/07_local_reviewer_agent_prompt.md`
- `maintenance_agent`: `prompt_pack/07_local_reviewer_agent_prompt.md`

Use `--prompt-file` to override the prompt path and `--output-file` to override
the saved draft path. Existing output is not overwritten unless `--force` is
used.

The command writes:

- `stories/<story>/reports/local_agent_drafts/<agent>_<model-label>_draft.md`
- `stories/<story>/reports/local_agent_drafts/<agent>_<model-label>_draft.yaml`

The metadata YAML records the story, agent, model label, configured model,
prompt file, output file, status, and safety flags showing that no source edits,
shell execution, cloud calls, GitHub API calls, commits, merges, or deployments
were performed.

## Prompt Safety

Local-agent prompts should request plain ASCII output. Avoid emoji/checkmark
symbols, unnecessary nested Markdown code fences, and invented headings. Use the
requested headings exactly.

## Review Boundary

Human/Codex must review drafts before applying changes. High-risk DeFi,
security, money movement, correctness-critical logic, merge readiness, and
release decisions still need human/cloud review. Local drafts are evidence and
working notes, not authority.
