# STORY-031: Add workflow-run cloud review prep phase

## Goal

Extend the LangGraph safe workflow runner with a cloud-review-prep phase that prepares cloud review evidence without calling cloud models.

## Why This Matters

The system already has safe prepare and local-finalize phases. The next safe phase is cloud review preparation: creating a cloud review packet and refreshing workflow preview evidence. This reduces manual steps while still avoiding automatic cloud model calls, GitHub API calls, merge, push, or deployment.


## Acceptance Criteria

- Extend workflow-run to support --phase cloud-review-prep.
- workflow-run cloud-review-prep requires --story.
- workflow-run cloud-review-prep defaults --project to the current working directory.
- workflow-run cloud-review-prep requires --execute before running safe steps.
- Without --execute, workflow-run cloud-review-prep writes a plan but does not run steps.
- With --execute, workflow-run cloud-review-prep runs cloud-review-packet and workflow-preview.
- cloud-review-prep should check whether finalize-story result is ready_for_review true before execution.
- If finalize-story is missing or not ready, cloud-review-prep should return REQUEST_CHANGES or a clear failed status instead of creating misleading cloud review evidence.
- workflow-run cloud-review-prep records graph nodes visited.
- workflow-run cloud-review-prep writes reports/workflow_run_result.yaml.
- workflow-run cloud-review-prep writes reports/workflow_run_report.md.
- workflow-run cloud-review-prep records planned steps and executed steps.
- workflow-run cloud-review-prep does not execute agents.
- workflow-run cloud-review-prep does not call cloud models.
- workflow-run cloud-review-prep does not call GitHub APIs.
- workflow-run cloud-review-prep does not commit, push, merge, deploy, or run destructive commands.
- next-step recommends workflow-run cloud-review-prep when finalize-story is ready and cloud_review_export.md is missing.
- README documents the cloud-review-prep phase.
- docs/langgraph_workflow.md explains prepare, local-finalize, and cloud-review-prep phases.
- Tests verify dry-run behavior, execute behavior, safe step sequence, readiness guard, and next-step integration.

## Not In Scope

- No automatic cloud model calls.
- No record-cloud-review automation.
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
- workflow-run cloud-review-prep dry-run works.
- workflow-run cloud-review-prep execute mode works after local-finalize is ready.
- finalize-story marks this story ready for review.
