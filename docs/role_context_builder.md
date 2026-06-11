# Role Context Builder

`agentic build-context` creates deterministic context packets for assigned story
agents. Prompt packs tell an agent what role it is playing. Context packets tell
that agent what information it needs for that role.

```text
story.md + agent_plan.yaml + plans/reports/evidence
  -> role-context builder
  -> developer_agent_context.md
  -> test_agent_context.md
  -> docs_agent_context.md
  -> local_reviewer_agent_context.md
```

## Prompt Pack Vs Context Packet

Prompt packs live under `stories/STORY_SLUG/prompt_pack/`. They are role
instructions and task framing.

Role context packets live under
`stories/STORY_SLUG/reports/role_context/`. They are runtime artifacts that
collect the smallest complete local context for a specific assigned agent.

The command does not run prompts, call local models, call cloud models, call
GitHub APIs, commit, merge, or deploy.

## Shared Premise Vs Role-Specific Context

Every packet gets a shared premise:

- `story.md`
- `status.yaml` when present
- `agent_plan.yaml`
- the assigned agent instruction file
- `.agentic/rules.yaml` when present
- `.agentic/agent_runtime.yaml` when present

The role-specific section then narrows the packet. Developer packets emphasize
goal, acceptance criteria, boundaries, and implementation notes. Test packets
emphasize independent tests and test-layer expectations. Docs packets emphasize
README and docs references. Reviewer and security packets emphasize evidence,
quality gates, generated artifacts, and safety boundaries.

## Why This Reduces Token Waste

Giving every role the whole repository forces each agent to filter irrelevant
files before doing useful work. Role context packets move that filtering into a
deterministic local command. The agent receives the story premise, its own
instruction, and the role evidence it is expected to inspect.

This keeps context smaller while preserving traceability: each packet lists
included files, skipped files, estimated character count, and warnings.

## Runtime Connector Preparation

The builder prepares for a future Codex runtime connector by separating prompt
selection from context selection. A connector can receive:

- a prompt pack file for role behavior
- a role context packet for local evidence
- safety metadata that confirms no models or agents were executed by the
  builder

This keeps runtime execution optional and reviewable.

## Usage

Build packets for every assigned agent:

```powershell
docker compose run --rm dev agentic build-context --story STORY_SLUG --all --force
```

Build one assigned agent:

```powershell
docker compose run --rm dev agentic build-context --story STORY_SLUG --agent developer_agent
```

If neither `--all` nor `--agent` is provided, the command defaults to all
assigned agents. Existing packets are not overwritten unless `--force` is used.

Outputs:

- `stories/STORY_SLUG/reports/role_context/AGENT_ID_context.md`
- `stories/STORY_SLUG/reports/role_context_result.yaml`
- `stories/STORY_SLUG/reports/role_context_report.md`

Generated role context packet files are runtime artifacts. They must not be
committed except for `reports/role_context/.gitkeep`.
