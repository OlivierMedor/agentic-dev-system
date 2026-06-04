# STORY-030: Add workflow-run prepare phase

## Goal

Extend the LangGraph safe workflow runner with a prepare phase that runs safe story setup steps.

## Why This Matters

The system already has workflow-run local-finalize. The next safe phase is preparation: assigning agents, generating prompt packs, and previewing the workflow route. This reduces manual setup while still avoiding agent execution, cloud model calls, GitHub APIs, merge, push, or deployment.


## Acceptance Criteria

- Extend workflow-run to support --phase prepare.
- workflow-run prepare requires --story.
- workflow-run prepare defaults --project to the current working directory.
- workflow-run prepare requires --execute before running safe steps.
- Without --execute, workflow-run prepare writes a plan but does not run steps.
- With --execute, workflow-run prepare runs prepare-story and workflow-preview.
- workflow-run prepare records graph nodes visited.
- workflow-run prepare writes reports/workflow_run_result.yaml.
- workflow-run prepare writes reports/workflow_run_report.md.
- workflow-run prepare records planned steps and executed steps.
- workflow-run prepare does not execute agents.
- workflow-run prepare does not run generated prompts.
- workflow-run prepare does not call cloud models.
- workflow-run prepare does not call GitHub APIs.
- workflow-run prepare does not commit, push, merge, deploy, or run destructive commands.
- next-step recommends workflow-run prepare when agent_plan.yaml or prompt_pack is missing.
- README documents the prepare phase.
- docs/langgraph_workflow.md explains prepare phase versus local-finalize phase.
- Tests verify dry-run behavior, execute behavior, safe step sequence, and next-step integration.

## Not In Scope

- No automatic agent execution.
- No cloud model calls.
- No GitHub API calls.
- No automatic merge.
- No deployment.
- No LangGraph checkpointing or persistence yet.
- No human-in-the-loop pause/resume yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- workflow-run prepare dry-run works.
- workflow-run prepare execute mode works.
- finalize-story marks this story ready for review.
