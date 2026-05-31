# STORY-013: Add dynamic agent runtime config

## Goal

Create a project-level runtime config that defines which provider/model each agent should use and what commands are allowed without repeated human approval.

## Why This Matters

The system should support different execution modes for different agents. Some agents may use Codex, some may use local models, and final review may use a manual cloud model. The project should also define safe command policies so agents do not ask for approval on routine checks but still require approval for risky actions.

## Acceptance Criteria

- Add .agentic/agent_runtime.yaml to initialized projects.
- Add an agentic runtime-config validate command.
- Add an agentic runtime-config show command.
- Runtime config defines agent providers, models, approval modes, and fallback providers.
- Runtime config defines commands allowed without approval.
- Runtime config defines commands requiring human approval.
- Runtime config includes cloud_reviewer as manual_cloud_model.
- Runtime config includes local_model_optional as a supported future provider type.
- Prompt pack generation includes runtime config content when present.
- Tests verify runtime config creation, validation, and prompt-pack inclusion.
- README explains how runtime config works.

## Not In Scope

- No actual local model installation.
- No automatic Codex execution.
- No automatic cloud API calls.
- No LangGraph yet.
- No direct enforcement of command policies by Codex yet.
- No remote deployment.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes on the current repo.
- generate-prompts includes runtime config guidance.
- finalize-story marks this story ready for review.
