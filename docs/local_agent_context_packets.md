# Local Agent Context Packets

Local agent context packets are slim, one-page work orders for local models.
They are created by `agentic local-agent draft --prompt-mode slim`, which is
the default mode for local-agent drafts.

Full `prompt_pack` files are Codex-oriented and can be too large or too
instruction-heavy for local models. Gemma can fail this way by returning
`reasoning_content` but no visible `message.content`, especially when the prompt
is too large for the loaded model or server settings. Devstral and other models
may return visible output but stop with `finish_reason: length`, which means the
draft may be truncated.

## What Slim Mode Includes

Slim mode builds the draft prompt from story-local planning files only:

- Story name.
- Agent role.
- `story.md`.
- `status.yaml` when present.
- `test_plan.yaml` when present.
- `monitoring_plan.yaml` when present.
- `agent_plan.yaml` when present.
- Matching `instructions/AGENT_ID.md` when present.
- Short safety rules.
- The expected draft output file path.

Slim mode does not include review bundles, cloud review packets, unrelated story
files, generated draft outputs, raw model responses, or other runtime artifacts.

The context packet is saved to:

```text
stories/STORY_SLUG/reports/local_agent_context/AGENT_ID_MODEL_LABEL_context.md
```

For example:

```text
stories/story_047_local_agent_prompt_slimming/reports/local_agent_context/docs_agent_gemma-4-26b_context.md
```

The draft metadata records `prompt_mode: slim`, the `context_file`,
`context_character_count`, and `source_files_used`.

## Usage

```powershell
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-agent draft --story story_047_local_agent_prompt_slimming --agent docs_agent --model-label gemma-4-26b --prompt-mode slim --force
```

Use slim mode for local models by default. Use full mode only for debugging or
for stronger models that can reliably handle full story prompt packs:

```powershell
docker compose run --rm dev agentic local-agent draft --story STORY_SLUG --agent docs_agent --model-label gemma-4-26b --prompt-mode full
```

Use `--prompt-file PROMPT_FILE` for a custom prompt. In that case the metadata
records `prompt_mode: custom`.

## Truncation Warnings

When the local server returns `finish_reason: length`, the draft may be
incomplete.

If visible content is empty, the command fails with
`status: empty_model_response` and saves the raw response JSON for debugging.

If visible content is non-empty, the command saves the draft with
`status: draft_saved_with_warning`, records the warning
`model output may be truncated`, and tells the operator to review carefully or
retry with a slim prompt or higher output token limit.

## Review Boundary

Local drafts are not applied to source files. The CLI does not execute model
output and does not execute model output as commands. It does not call cloud
models, call GitHub APIs, commit, push, merge, or deploy.
Human/Codex review is still required before applying any draft content.

Context packets and draft outputs are runtime artifacts. They must remain
untracked except for optional `.gitkeep` files.
