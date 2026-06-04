# STORY-029: Integrate workflow-run into project status and next-step

## Goal

Update project-status and next-step so they understand workflow_run_result.yaml and recommend workflow-run for safe local finalization when appropriate.

## Why This Matters

The system now has a LangGraph safe workflow runner. The dashboard and next-step advisor should use workflow-run evidence so the user can see whether a story's safe local workflow was executed and what should happen next.

## Acceptance Criteria

- project-status reads reports/workflow_run_result.yaml when present.
- project-status displays workflow-run phase, status, executed flag, and safety flags.
- project-status includes workflow-run status in reports/project_status_report.md.
- next-step reads reports/workflow_run_result.yaml when present.
- next-step recommends workflow-run local-finalize when required local finalization evidence is missing or stale.
- next-step recommends cloud-review-packet after workflow-run local-finalize completes and finalize-story is ready.
- next-step does not require workflow-run when manual finalize evidence is already valid.
- next-step does not recommend automatic merge or deployment.
- README documents how workflow-run fits into the normal story lifecycle.
- docs/langgraph_workflow.md is updated to show preview versus workflow-run versus future orchestration.
- Tests verify project-status and next-step behavior with workflow_run_result.yaml.

## Not In Scope

- No new LangGraph phases.
- No automatic agent execution.
- No cloud model calls.
- No GitHub API calls.
- No automatic merge.
- No deployment.
- No LangGraph checkpointing yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- project-status shows workflow-run status.
- next-step recommends the correct safe next action.
- finalize-story marks this story ready for review.
