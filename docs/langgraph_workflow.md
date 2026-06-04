# LangGraph Workflow Preview

LangGraph is being introduced after the project workflow rules became explicit. The current system
already knows how to prepare stories, generate agent prompts, collect reports, run local gates,
package cloud review context, record manual review decisions, and keep human approval as the final
merge requirement. Adding graph orchestration before those rules were clear would have made the
automation harder to reason about.

`next-step` is the GPS-style guidance command. It reads story evidence and recommends the next safe
workflow action without executing that action.

`workflow-preview` is the first graph-based route preview. It uses a LangGraph `StateGraph` with
three nodes:

- `collect_story_state` reads the story folder, status, prompt pack, reports, review bundle, and
  recorded workflow results.
- `determine_next_action` reuses the existing next-step recommendation logic.
- `write_preview` writes `reports/workflow_preview_result.yaml` and
  `reports/workflow_preview_report.md`.

This story does not use LangGraph persistence, checkpointing, or human-in-the-loop pause/resume.
The preview graph does not execute agents through the configured agent runtime, call cloud models,
run shell commands, call GitHub APIs, commit, push, merge, or deploy.

Future LangGraph workflows can build on this shape to orchestrate `prepare-story`, configured agent
runtime execution, `finalize-story`, cloud review packet creation, cloud review result recording,
merge readiness, remote-dev evidence routing, and support queue pauses. Those later workflows still
need explicit safety boundaries: human final approval is always required before merge, and automatic
deployment should not be inferred from a route recommendation.
