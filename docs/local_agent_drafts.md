# Local Agent Drafts

Local agent drafts send story context to the configured local
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
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-agent draft --story story_045_local_agent_draft_runner --agent docs_agent --model-label gemma-4-26b --prompt-mode slim --force
```

Supported agents:

- `developer_agent`
- `test_agent`
- `docs_agent`
- `reviewer_agent`
- `maintenance_agent`

Prompt modes:

- `--prompt-mode slim` is the default. It builds a local-model-friendly context
  packet from `story.md`, status/test/monitoring/agent plans when present, the
  matching agent instruction file, safety rules, and the expected draft output
  path.
- `--prompt-mode full` uses the existing story `prompt_pack` file for the
  selected agent.
- `--prompt-file <path>` uses that file directly and records
  `prompt_mode: custom` in metadata.

Full-mode prompt files:

- `developer_agent`: `prompt_pack/03_developer_agent_prompt.md`
- `test_agent`: `prompt_pack/04_test_agent_prompt.md`
- `docs_agent`: `prompt_pack/05_docs_agent_prompt.md`
- `reviewer_agent`: `prompt_pack/07_local_reviewer_agent_prompt.md`
- `maintenance_agent`: `prompt_pack/07_local_reviewer_agent_prompt.md`

Use `--output-file` to override the saved draft path. Existing output,
metadata, raw response JSON, and slim context packets are not overwritten unless
`--force` is used.

The command writes:

- `stories/<story>/reports/local_agent_drafts/<agent>_<model-label>_draft.md`
- `stories/<story>/reports/local_agent_drafts/<agent>_<model-label>_draft.yaml`
- `stories/<story>/reports/local_agent_drafts/<agent>_<model-label>_raw_response.json`
- `stories/<story>/reports/local_agent_context/<agent>_<model-label>_context.md`
  in slim mode

The metadata YAML records the story, agent, model label, configured model,
prompt mode, prompt file for full/custom mode, context file for slim mode,
context character count, source files used, output file, raw response file,
prompt character count, response character count, finish reason, warnings,
status, and safety flags showing that no source edits, shell execution, cloud
calls, GitHub API calls, commits, merges, or deployments were performed.

See `docs/local_agent_context_packets.md` for the slim context packet format and
local-model troubleshooting notes.

## Empty Responses

Empty or whitespace-only model content is treated as a failure, not a saved
draft. In that case the command writes metadata with
`status: empty_model_response`, saves the raw response JSON for debugging, and
exits with an error instead of silently accepting an empty Markdown file.

Common causes include:

- A model/server mismatch.
- The configured model name does not match the model loaded by the server.
- The prompt too large failure mode, where the prompt exceeds the loaded model
  or server settings.
- The prompt is too large for the loaded model or server settings.
- The local server returns an unsupported response shape.
- The model refuses to produce final content.
- A model refuses to produce final content.
- The response contains only hidden/internal reasoning and no final answer.

Inspect the raw response JSON and `.agentic/agent_runtime.yaml` before rerunning.

## Truncated Responses

When the local server returns `finish_reason: length`, visible output may be
truncated.

If visible content is empty, the command fails with
`status: empty_model_response`, saves metadata and raw response JSON, and exits
nonzero.

If visible content is non-empty, the command saves the draft with
`status: draft_saved_with_warning`, records `model output may be truncated`, and
sets the next action to review the draft carefully or retry with a slim prompt
or higher output token limit.

## Prompt Safety

Local-agent prompts should request plain ASCII output. Avoid emoji/checkmark
symbols, unnecessary nested Markdown code fences, and invented headings. Use the
requested headings exactly.

## Review Boundary

Human/Codex must review drafts before applying changes. High-risk DeFi,
security, money movement, correctness-critical logic, merge readiness, and
release decisions still need human/cloud review. Local drafts are evidence and
working notes, not authority.
