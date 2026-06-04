# STORY-027: Add LangGraph workflow preview

## Goal

Add a first LangGraph-based workflow preview that inspects a story and explains the next workflow route without executing agents automatically.

## Why This Matters

The system already has many workflow commands and a next-step advisor. LangGraph can later orchestrate these steps automatically, but first we should introduce it safely as a preview graph that reads state, routes decisions, and explains the next action without making changes beyond reports.

## Acceptance Criteria

- Add langgraph as a project dependency.
- Add a workflow-preview command.
- workflow-preview requires --story.
- workflow-preview defaults --project to the current working directory.
- workflow-preview validates that the story folder exists.
- workflow-preview uses LangGraph StateGraph to process story workflow state.
- workflow-preview reuses next-step style logic where practical.
- workflow-preview writes reports/workflow_preview_result.yaml.
- workflow-preview writes reports/workflow_preview_report.md.
- workflow-preview prints a beginner-friendly route summary to the terminal.
- workflow-preview does not execute agents.
- workflow-preview does not call cloud models.
- workflow-preview does not commit, push, merge, deploy, or call GitHub APIs.
- The workflow graph includes nodes for collecting story state, determining next action, and writing preview output.
- README documents why LangGraph is being introduced.
- Add docs/langgraph_workflow.md explaining how this preview maps to future orchestration.
- Tests verify graph construction, workflow preview output, and no automatic execution behavior.

## Not In Scope

- No automatic agent execution.
- No LangGraph persistence/checkpointing yet.
- No LangGraph human-in-the-loop pause/resume yet.
- No cloud model calls.
- No LangSmith/Langfuse tracing yet.
- No web dashboard.
- No deployment.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- workflow-preview creates result and report files.
- finalize-story marks this story ready for review.
