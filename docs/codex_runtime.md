# Codex Runtime Connector

Codex is the primary configured runtime for code-changing work in this project.
Role context packets keep each agent handoff focused, and Codex task files turn
those packets into copy/paste-ready instructions.

For the manual operator flow that runs those files safely one role at a time,
see `docs/codex_task_execution.md`.
For the runtime tier policy, see `docs/runtime_config.md`.

## Command

```powershell
docker compose run --rm dev agentic codex-task create --story STORY_SLUG
```

Useful options:

- `--agent AGENT_ID` creates one task file.
- `--all` creates a task file for every role context packet.
- Omitting both `--agent` and `--all` defaults to all packets.
- `--project PATH` points at another project folder.
- `--force` overwrites existing task files.
- `--model MODEL_NAME` writes a task-level model recommendation.

Without `--model`, recommendations come from `.agentic/agent_runtime.yaml`.
Blueprints define story scope; they are not the source of truth for provider or
model assignment.

The command reads role context packets from:

```text
stories/STORY_SLUG/reports/role_context/AGENT_ID_context.md
```

It writes Codex task files to:

```text
stories/STORY_SLUG/reports/codex_tasks/AGENT_ID_codex_task.md
```

It also writes:

```text
stories/STORY_SLUG/reports/codex_task_result.yaml
stories/STORY_SLUG/reports/codex_task_report.md
```

If role context is missing, build it first:

```powershell
docker compose run --rm dev agentic build-context --story STORY_SLUG --all --force
```

## What The Task File Contains

Each task file includes:

- Agent identity.
- Story slug.
- Model recommendation from `.agentic/agent_runtime.yaml`, or the `--model`
  override.
- Recommended execution order context, including this agent's position and
  neighboring roles.
- Safety rules.
- Full role context packet content.
- Exact role objective.
- Required output report path.
- Validation commands.
- A do-not-do list.

The model recommendation is only written into the task file. The command does
not switch the active Codex model.

Default model tiers are:

```text
research_agent           gpt-5.4-mini (codex)
planner_agent            gpt-5.4 (codex)
developer_agent          gpt-5.4 (codex)
test_agent               gpt-5.4 (codex)
docs_agent               gpt-5.4-mini (codex)
security_quality_agent   gpt-5.5 (codex)
local_reviewer_agent     gpt-5.5 (codex)
cloud_reviewer           main_cloud_model (manual_cloud_model)
local_model_helper       gemma-4-26b (local_model_optional), prompt_mode micro
```

`gpt-5.4` is the normal worker tier for planning, implementation, and tests.
`gpt-5.4-mini` is used for lighter research, documentation, reporting, and
summarization. `gpt-5.5` is reserved for high-risk security, final local review,
DeFi, risk-sensitive work, and final judgment. Gemma remains optional for
micro-mode local draft help only.

Recommended execution order comes from `agent_plan.yaml` when `execution_order`
is present. If it is missing, the command uses the standard order:

```text
research_agent
planner_agent
developer_agent
test_agent
docs_agent
security_quality_agent
local_reviewer_agent
```

## Safety Boundary

`agentic codex-task create` is a local file-generation command. It does not:

- Invoke Codex automatically.
- Call cloud models.
- Execute agents.
- Call GitHub APIs.
- Commit, push, merge, or deploy.

Generated files under `reports/codex_tasks/` are runtime artifacts. They are
ignored by Git and blocked by artifact-policy except for `.gitkeep`.

## Human Review

The human owner still reviews pull requests and merges manually. Codex task
files are an operator handoff, not an approval or merge decision.

Future versions may add controlled Codex execution, but this connector only
prepares task files.
