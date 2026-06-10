# Local Agent Context Packets

Local agent context packets are bounded work orders for local models. They are
created by `agentic local-agent draft --prompt-mode slim` or
`agentic local-agent draft --prompt-mode micro`.
Slim packets are still one-page work orders; micro packets are shorter
final-answer-focused work orders.

Full `prompt_pack` files are Codex-oriented and can be too large or too
instruction-heavy for local models. Gemma can fail this way by returning
`reasoning_content` but no visible `message.content`, especially when the prompt
is too large for the loaded model or server settings. Devstral and other models
may return visible output but stop with `finish_reason: length`, which means the
draft may be truncated.

## Prompt Modes

- `full` uses the Codex-style story `prompt_pack` file. It is useful for
  debugging or stronger local models, but it is usually too heavy for fragile
  local reasoning models.
- `slim` is the default. It builds a smaller story-local context packet from
  planning files, the matching agent instruction, safety rules, and the expected
  output path.
- `micro` is the smallest mode. It is final-answer-focused and intended for
  local models such as Gemma when even slim mode spends output budget in
  hidden reasoning and returns no visible content.

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

## What Micro Mode Includes

Micro mode writes the same context packet path, but it keeps the packet much
smaller than slim mode. It includes only:

- Story slug.
- Agent id.
- Agent role or responsibility.
- One short story goal.
- Up to five top acceptance criteria.
- Expected output path.
- A save-only safety boundary.
- A final visible answer instruction:
  `Return only the final visible answer in message.content. Do not put the answer only in reasoning_content. Do not include hidden reasoning. If you cannot complete the task, return a short visible explanation.`

Micro mode records `prompt_mode: micro`, `context_character_count`, and
`source_files_used` in draft metadata. If the generated micro packet exceeds the
target size, metadata records a warning.

Micro mode excludes review bundles, cloud review packets, remote dev validation
packets, raw model responses, previous local-agent drafts, unrelated story
files, large reports, and long prompt packs.

## Usage

```powershell
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-agent draft --story story_047_local_agent_prompt_slimming --agent docs_agent --model-label gemma-4-26b --prompt-mode slim --force
```

Use slim mode for local models by default. Use full mode only for debugging or
for stronger models that can reliably handle full story prompt packs:

```powershell
docker compose run --rm dev agentic local-agent draft --story STORY_SLUG --agent docs_agent --model-label gemma-4-26b --prompt-mode full
```

Use micro mode when Gemma or another local reasoning model returns populated
`reasoning_content` but empty visible `message.content`:

```powershell
docker compose run --rm dev agentic local-agent draft --story STORY_SLUG --agent docs_agent --model-label gemma-4-26b --prompt-mode micro
```

Use `--prompt-file PROMPT_FILE` for a custom prompt. In that case the metadata
records `prompt_mode: custom`.

## Truncation Warnings

When the local server returns `finish_reason: length`, the draft may be
incomplete.

If visible content is empty, the command fails with
`status: empty_model_response` and saves the raw response JSON for debugging.
The CLI does not use `reasoning_content` as the final draft by default.

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
