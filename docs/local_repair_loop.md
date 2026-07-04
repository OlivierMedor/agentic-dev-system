# Local Repair Loop

`agentic local-repair-loop` is the local-only repair orchestrator for story work
that needs a second pass after a model failure, a Ruff failure, or a pytest
failure. It is designed to reduce the manual back-and-forth that previously had
to happen around rejected outputs, handwritten repair prompts, and manually
routed lint and test failures.

## What It Does

The repair loop:

1. Reads the current target file.
1. Loads the story contract from `stories/STORY_SLUG/story.md` when present.
1. Falls back to the matching story entry in `blueprints/stories/*.yaml` when
   `story.md` is missing.
1. Continues with a clear warning when neither source exists, but still keeps
   clear pytest assertion failures local-repairable.
1. Classifies the available failure evidence when one is provided.
1. Builds a repair prompt that includes the story contract, current file
   content, exact failure output, required API strings, and repair policy.
1. Runs the configured local model only when `--execute` is used.
1. Validates the returned output before applying anything.
1. Applies only accepted full-file output.
1. Reruns Ruff and/or pytest when requested or when the target/test paths make
   those checks relevant.
1. Writes per-attempt evidence and a final result report under
   `stories/STORY_SLUG/reports/`.
1. Stops at the configured retry budget and writes a manual support report
   instead of automatically escalating to cloud or Codex.

## Default Model

Qwen remains the simple default local repair path. The project runtime config can
point the local OpenAI-compatible adapter at Qwen, and the repair loop uses that
configured local runtime. No automatic cloud model call is added, and Codex is
not enabled as the default repair path.

## Why The Prompt Includes Current File, Failure, And Contract

Repair prompts are more reliable when the model sees:

- the exact file it is supposed to repair,
- the story contract that defines the intended behavior,
- the exact failure output that triggered the retry, and
- the public API strings that must stay present.

That keeps the retry loop focused on the actual regression instead of asking the
model to rediscover the whole task from scratch.

## Cloud Policy

Cloud escalation stays manual-only. The repair loop never calls a cloud model
automatically, never calls Codex automatically, and never writes wallet,
trading, private-key, signing, deployment, or live DeFi logic.

If the retry budget is exhausted or the acceptance criteria are too unclear for
local repair, the loop writes a manual support report under the story reports
directory. A human can then decide whether to clarify the task or route the
issue through the existing manual cloud process.

## Failure Classification

Clear `pytest` assertion failures against a source target are classified as
developer-repairable local failures, not as unclear acceptance criteria. That
means a failure output that contains assertion text, a source-file target, and
one or more focused test paths stays on the local repair path even when no
`story.md` file exists yet.

This is the intended behavior for small smoke tests and simple implementation
behavior regressions.

## Domain Safety

The validator only rejects specific unsafe execution phrases. Harmless phrases
such as these are allowed:

- `trading symbol`
- `symbol normalization`
- `market symbol`

The validator still rejects actual unsafe behavior such as:

- wallet or private-key handling
- signing logic
- order placement or submission
- trade execution
- live exchange APIs
- deployment logic
- network calls for trading execution

## Example

```powershell
docker compose run --rm dev agentic local-repair-loop `
  --story story_069_local_repair_loop_orchestrator `
  --target src/agentic_dev/local_repair_loop.py `
  --failure-output stories/story_069_local_repair_loop_orchestrator/reports/ruff_output.txt `
  --required-api normalize_funding_records `
  --required-api FundingVenue `
  --execute
```

Dry-run mode writes the prompt and plan report without modifying the target
file.
