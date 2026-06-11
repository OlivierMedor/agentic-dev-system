# System Map

This map shows how the local workflow fits together. It is public-facing and
omits private operator instructions, private prompts, secrets, and generated
runtime artifacts.

At a high level, the system turns blueprint entries into story workspaces, uses
safe local workflow phases to prepare and finalize evidence, then leaves cloud
review and merge decisions under human control.

For a beginner-friendly repository tour, see `docs/code_tour.md`. For a
command-to-code lookup table, see `docs/command_map.md`. For the manual Codex
task-file flow, see `docs/codex_task_execution.md`.

## Blueprint To Story Flow

```text
Blueprint
  |
  v
blueprints/blueprint.yaml
  |
  v
agentic generate-stories
  |
  v
stories/story_###_slug/
  |
  v
agentic workflow-run --phase prepare --execute
  |
  v
configured agent runtime
  |
  v
agentic workflow-run --phase local-finalize --execute
  |
  v
agentic workflow-run --phase cloud-review-prep --execute
  |
  v
human/cloud review
  |
  v
human merge decision
```

The blueprint is the planning source. `generate-stories` turns approved entries
into story folders. `workflow-run` then handles deterministic local setup and
finalization steps. Agent execution, cloud review, and merge remain manual or
operator-controlled; the CLI prepares evidence and records results.

## Story Workspace Structure

```text
stories/story_034_public_launch_prep/
|-- story.md
|-- status.yaml
|-- test_plan.yaml
|-- monitoring_plan.yaml
|-- agent_plan.yaml
|-- story_runbook.md
|-- instructions/
|   |-- developer_agent.md
|   |-- test_agent.md
|   `-- local_reviewer_agent.md
|-- prompt_pack/
|   |-- 03_developer_agent_prompt.md
|   |-- 04_test_agent_prompt.md
|   `-- 07_local_reviewer_agent_prompt.md
|-- reports/
|   |-- developer_report.md
|   |-- test_report.md
|   `-- local_review_report.md
|-- review_bundle/
|   `-- .gitkeep
|-- cloud_review_packet/
|   `-- .gitkeep
`-- remote_dev_validation/
    `-- .gitkeep
```

Committed story files describe scope, plans, prompts, and reports. Generated
review bundles, cloud review packets, and remote dev validation packets are
local artifacts and must stay untracked except for `.gitkeep`.

## Agent Prompt Pack Flow

```text
story.md
  |
  +--> agent_plan.yaml
  |
  +--> test_plan.yaml
  |
  +--> monitoring_plan.yaml
  |
  +--> .agentic/agent_runtime.yaml
          |
          v
agentic prepare-story
          |
          v
stories/STORY_SLUG/prompt_pack/
          |
          v
operator runs configured agents
          |
          v
stories/STORY_SLUG/reports/
```

Prompt packs are generated local instructions for the assigned agent roles. The
CLI writes the prompts, but it does not execute agents automatically.

## Manual Codex Task Flow

```text
story workspace
  |
  v
agentic build-context
  |
  v
reports/role_context/*.md
  |
  v
agentic codex-task create
  |
  v
reports/codex_tasks/*.md
  |
  v
operator opens one task file in Codex
  |
  v
role writes reports/
  |
  v
agentic workflow-run --phase local-finalize --execute
```

`build-context` and `codex-task create` generate local runtime artifacts. The
operator decides which Codex role pass to run next; the CLI does not invoke
Codex, run all roles, commit, push, merge, deploy, or call cloud models.

## Review Bundle, Quality Gate, And Finalize Flow

```text
agent reports
  |
  v
agentic workflow-run --phase local-finalize --execute
  |
  +--> agentic test-layers
  |
  +--> agentic finalize-story
  |       |
  |       +--> agentic review-bundle
  |       |
  |       +--> agentic quality-gate
  |       |
  |       `--> reports/finalize_story_result.yaml
  |
  +--> agentic review-bundle
  |
  `--> agentic workflow-preview
```

`finalize-story` records whether local evidence is ready for review. The quality
gate checks story files, reports, test-layer evidence, local review approval,
pytest evidence, Ruff evidence, and review bundle evidence.

## Cloud Review And Merge Readiness Flow

```text
finalize-story ready_for_review: true
  |
  v
agentic workflow-run --phase cloud-review-prep --execute
  |
  v
stories/STORY_SLUG/cloud_review_packet/cloud_review_export.md
  |
  v
human sends export to cloud model manually
  |
  v
agentic record-cloud-review --result-file OUTPUT_FILE
  |
  v
agentic merge-readiness
  |
  v
human owner reviews PR, CI, evidence, and decides whether to merge
```

Cloud review is a manual handoff. The system creates the packet and records the
returned decision; it does not call a cloud model or approve a merge.

## Queue Loops

```text
support blocker
  |
  v
agentic support-ticket create
  |
  v
.agentic/support_queue/pending/
  |
  v
human or manual cloud answer
  |
  v
agentic support-ticket answer
  |
  v
story resumes
```

```text
post-story improvement
  |
  v
agentic improvement-scan create
  |
  v
review suggestions
  |
  v
agentic improvement-scan record
  |
  v
.agentic/improvement_queue/pending/
  |
  v
approve and promote later
```

```text
failure from tests, logs, CI, or integrations
  |
  v
agentic maintenance-scan create
  |
  v
review findings
  |
  v
agentic maintenance-scan record
  |
  v
.agentic/maintenance_queue/pending/
  |
  v
repair story later
```

```text
new capability idea
  |
  v
agentic feature-scan create
  |
  v
review suggestions
  |
  v
agentic feature-scan record
  |
  v
.agentic/feature_queue/pending/
  |
  v
approve and promote later
```

Runtime queue files are local state and must not be tracked.

## LangGraph Workflow-Run Phases

```text
workflow-run --phase prepare
  |
  +--> prepare-story
  |
  +--> micro-readiness
  |
  `--> workflow-preview
```

```text
workflow-run --phase local-finalize
  |
  +--> test-layers
  |
  +--> finalize-story
  |
  +--> review-bundle
  |
  `--> workflow-preview
```

```text
workflow-run --phase cloud-review-prep
  |
  +--> check finalize_story_result.yaml
  |
  +--> cloud-review-packet
  |
  `--> workflow-preview
```

All phases require `--execute` before they run local steps. Without it, the
runner writes a dry-run plan. The runner uses a hardcoded allowlist and does not
run generated prompts, arbitrary story commands, cloud models, GitHub APIs,
commits, pushes, merges, deployments, or destructive commands.
