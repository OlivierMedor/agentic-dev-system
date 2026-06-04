# LangGraph Workflow

LangGraph is being introduced after the project workflow rules became explicit. The current system
already knows how to prepare stories, generate agent prompts, collect reports, run local gates,
package cloud review context, record manual review decisions, and keep human approval as the final
merge requirement. Adding graph orchestration before those rules were clear would have made the
automation harder to reason about.

`next-step` is the GPS-style guidance command. It reads story evidence and recommends the next safe
workflow action without executing that action.

## Preview, run, and future orchestration

`workflow-preview` is a graph-based route explanation. It reads story evidence, reuses the
next-step recommendation rules, writes preview artifacts, and does not execute workflow steps.

`workflow-run` is graph-based safe local execution. The current runner supports only the
`local-finalize` phase, and execution requires `--execute`. It runs a hardcoded allowlist of local
finalization steps and records `reports/workflow_run_result.yaml` plus
`reports/workflow_run_report.md`.

Future workflow orchestration is a later capability. It may add configured agent runtime execution,
checkpointing, and human/cloud pause points, but those capabilities are outside the current runner.

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

`workflow-run` is the first safe execution graph. It also uses a LangGraph `StateGraph`, but it is
not an agent runner. Without `--execute`, it behaves as a dry run: it writes
`reports/workflow_run_result.yaml` and `reports/workflow_run_report.md`, records graph nodes
visited, and explains which safe local steps would run.

When `--execute` is provided, `workflow-run --phase local-finalize` runs only the hardcoded safe
local sequence:

- `test-layers`
- `finalize-story`
- `review-bundle`
- `workflow-preview`

Those steps are deterministic local checks and report-generation commands already present in the
CLI. The runner does not read commands from story files, prompt packs, user input, or generated
agent instructions. It records command-style results for each safe step and writes safety flags
showing that no agents, cloud models, GitHub APIs, commits, merges, pushes, deployments, or
destructive commands were run.

The difference is:

- `workflow-preview` only recommends the next route. It never executes workflow steps.
- `workflow-run` can execute a narrow allowlist of safe local steps, but only when `--execute` is
  provided.

Future LangGraph workflows can build on this shape to orchestrate more of the lifecycle, including
human-in-the-loop pauses, checkpointing, and possibly configured agent execution. Those capabilities
are not part of the current runner. Later workflows still need explicit safety boundaries: human
final approval is always required before merge, and automatic deployment should not be inferred
from a route recommendation.
