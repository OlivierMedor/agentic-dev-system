# STORY-028: Add LangGraph safe workflow runner

## Goal

Create a LangGraph-based safe local workflow runner that can execute deterministic local validation steps for a story.

## Why This Matters

The system now has a LangGraph workflow preview. The next step is a safe runner that can execute approved local checks like test-layers, finalize-story, review-bundle, and workflow-preview without running agents, cloud models, GitHub APIs, merges, pushes, or deployments.

## Acceptance Criteria

- Add a workflow-run command.
- workflow-run requires --story.
- workflow-run defaults --project to the current working directory.
- workflow-run supports --phase local-finalize.
- workflow-run requires --execute before running any commands.
- Without --execute, workflow-run writes a plan but does not run workflow steps.
- With --execute, workflow-run runs safe local workflow steps only.
- The local-finalize phase runs test-layers, finalize-story, review-bundle, and workflow-preview.
- workflow-run uses LangGraph StateGraph.
- workflow-run records graph nodes visited.
- workflow-run writes reports/workflow_run_result.yaml.
- workflow-run writes reports/workflow_run_report.md.
- workflow-run records whether it executed steps.
- workflow-run records command results for each safe step.
- workflow-run does not execute agents.
- workflow-run does not call cloud models.
- workflow-run does not call GitHub APIs.
- workflow-run does not commit, push, merge, deploy, or run destructive commands.
- README documents the safe workflow runner.
- docs/langgraph_workflow.md explains how preview differs from safe workflow execution.
- Tests verify dry-run behavior, execute behavior, safe command sequence, and safety flags.

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
- workflow-run dry-run works.
- workflow-run local-finalize execute mode works.
- finalize-story marks this story ready for review.
