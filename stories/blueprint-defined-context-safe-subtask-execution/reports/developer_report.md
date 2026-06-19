# Developer Report

## Files Changed

- `src/agentic_dev/subtask_execution.py`
- `src/agentic_dev/local_execution.py`
- `tests/test_subtask_execution.py`
- `tests/test_local_execution.py`
- `README.md`
- `docs/command_map.md`
- `docs/local_models.md`
- `docs/runtime_config.md`

## What Changed

Implemented blueprint-defined sub-task parsing, dependency validation,
deterministic ordering, required-context assembly, conservative context
estimation, context-fit blocking, dependency-aware local execution, persistent
sub-task audit state, handoff summaries, resume behavior, and final requirement
coverage validation.

The implementation extends `agentic local-execute` only when the matched
blueprint story declares `subtasks`. Blueprints without sub-tasks continue to
use the Story 060 role execution path.

## Safety Notes

- Oversized tasks are blocked before local model invocation.
- Required context is assembled completely and is never silently trimmed.
- Local agents cannot redecompose cloud-authored tasks.
- Story 060 writable-path, resolved-path, and symlink protections are reused.
- No cloud, Codex, GitHub, merge, deploy, or hidden fallback path was added.
