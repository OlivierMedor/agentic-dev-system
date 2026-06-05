# Agentic Development System

This repo contains a small reusable CLI for preparing a project to use an agentic development workflow.

## What it does

The CLI can initialize a target project, generate story workspaces from a blueprint, and create review bundles.

- `.agentic/`
- `blueprints/`
- `stories/`
- `src/`
- `tests/`
- `docs/`

It also creates the first setup story, basic project rules, quality gates, and starter instructions for the agent roles used by the workflow.
Agent runtime queues live under `.agentic/`, including improvement, maintenance,
feature, and support queues.
Projects can also define per-agent runtime behavior in `.agentic/agent_runtime.yaml`.

For the beginner-friendly end-to-end path from blueprint to human PR merge decision, see
`docs/golden_path.md`.

## Runtime config

The runtime config is a project-level YAML file at `.agentic/agent_runtime.yaml`.
It defines:

- which provider each agent should use
- which model name is expected
- which approval mode each agent should run under
- which fallback provider to use when the preferred runtime is unavailable
- which routine commands are allowed without repeated approval
- which risky commands must always require human approval

The default config includes all core agents, a `cloud_reviewer` with
`provider: manual_cloud_model`, and support for the future
`local_model_optional` provider type.

## Story sizing

User stories should be narrow enough to have clear acceptance criteria and a focused code change, but large enough to justify the full agent workflow: Research, Planner, Developer, Test, Docs, Security/Quality, and Reviewer. If only one agent has meaningful work, the story is probably too small. If the story touches many unrelated features or modules, it is probably too large.

## Why this exists

The goal is to make agent-assisted development repeatable. A project can start from a blueprint, organize work into stories, collect agent reports, and prepare review bundles for human or cloud review.

## Try it on a sandbox project

Run this from the repo root:

```powershell
docker compose run --rm dev agentic init
```

This initializes the current project folder inside the container. Use `--project /sandbox-product` when you want to initialize the separate sandbox project mounted at `/sandbox-product`.

## Generate story workspaces

Run this from the repo root to create story folders from `blueprints/blueprint.yaml`:

```powershell
docker compose run --rm dev agentic generate-stories
```

Use `--project` to target another project folder or `--blueprint` to use a different blueprint file.

## Assign agents to a story

Run this from the repo root to create an execution map for a story:

```powershell
docker compose run --rm dev agentic assign-agents --story story_004_agent_assignment
```

The command writes `stories/<story>/agent_plan.yaml`. That file is the story's execution map: it lists the core agent team, their execution order, each agent's instruction file, and each expected report output.

Use `--force` when you intentionally want to regenerate an existing `agent_plan.yaml`.

## Generate prompt packs

Run this from the repo root to create Codex-ready prompts for each assigned agent in a story:

```powershell
docker compose run --rm dev agentic generate-prompts --story story_006_agent_prompt_packs
```

The command reads the story file, agent plan, test plan, monitoring plan, project rules, and quality gates. It writes one prompt per assigned agent into `stories/<story>/prompt_pack/`.

Use `--force` when you intentionally want to overwrite existing prompt files.
When `.agentic/agent_runtime.yaml` is present, the generated prompt files also include the
runtime config content and a short per-agent runtime expectation summary with provider, model,
approval mode, and fallback provider.

## Inspect runtime config

Print the current project runtime config:

```powershell
docker compose run --rm dev agentic runtime-config show
```

Validate that the runtime config has the required agents, known provider types, known approval
modes, and human-approval coverage for risky commands:

```powershell
docker compose run --rm dev agentic runtime-config validate
```

## Prepare a story

Run this from the repo root to prepare a story for agent execution:

```powershell
docker compose run --rm dev agentic prepare-story --story story_007_prepare_story_command
```

The command validates that `stories/<story>/` exists, creates `agent_plan.yaml` when missing,
generates prompt files in `stories/<story>/prompt_pack/`, writes `story_runbook.md`, writes
`reports/prepare_story_report.md`, and updates `status.yaml` to `prepared` with
`ready_for_review: false`.

Use `--force` when you intentionally want to refresh an existing `agent_plan.yaml` and overwrite
existing prompt files. The command does not execute agents, run cloud models, create a review
bundle, or run the quality gate.

## Ask for the next story step

Run this from the repo root when you want a beginner-friendly recommendation for one story:

```powershell
docker compose run --rm dev agentic next-step --story story_026_story_next_step_advisor
```

The command validates that `stories/<story>/` exists, inspects story status, `agent_plan.yaml`,
`prompt_pack/`, reports, review bundle files, quality gate results, finalize results, cloud review
packets and results, workflow-run results, merge-readiness results, and remote dev validation
evidence. It writes `stories/<story>/reports/next_step_report.md` and prints the next recommended
workflow action.

Typical recommendations include `workflow-run --phase prepare --execute` when planning artifacts
are missing, running the generated prompts with the configured agent runtime when required agent
reports are missing, `workflow-run --phase local-finalize --execute` when required local
finalization evidence is missing or stale, `workflow-run --phase cloud-review-prep --execute`
when finalize-story is ready and the cloud review export is missing, `record-cloud-review`,
`merge-readiness`, `remote-dev-packet`, or human PR/CI review when the story is ready for the
human owner. If a support ticket blocks the story, workflow-run records unsafe safety flags, or a
result records
`REQUEST_CHANGES`, `DEV_FAILED`, `NOT_RUN`, or `request_changes`, the advisor tells you to resolve
that state before continuing.

`next-step` only recommends a safe next action. It does not execute the recommendation, call cloud
models, call GitHub APIs, commit, push, merge, deploy, or recommend automatic merge or deployment.
Human final approval is always required before merge.

## Preview a workflow route with LangGraph

Run this from the repo root when you want to see the next story route as a LangGraph preview:

```powershell
docker compose run --rm dev agentic workflow-preview --story story_027_langgraph_workflow_preview
```

`workflow-preview` is the first LangGraph integration in this project. It uses a small
`StateGraph` to collect story state, determine the next action, and write preview output. The graph
reuses next-step style recommendation logic, then writes
`stories/<story>/reports/workflow_preview_result.yaml` and
`stories/<story>/reports/workflow_preview_report.md`.

This command is a preview graph only. LangGraph is not yet executing agents through the configured
agent runtime, calling cloud models, running shell commands, calling GitHub APIs, committing,
pushing, merging, or deploying. Human final approval is always required before merge, and this
command never recommends automatic merge or automatic deployment.

See `docs/langgraph_workflow.md` for how this preview maps to future orchestration.

## Run safe local workflow steps with LangGraph

Run this from the repo root when you want LangGraph to plan safe local workflow steps for a story:

```powershell
docker compose run --rm dev agentic workflow-run --story story_028_langgraph_safe_workflow_runner
```

By default, `workflow-run` is a dry run. It writes
`stories/<story>/reports/workflow_run_result.yaml` and
`stories/<story>/reports/workflow_run_report.md`, records the graph nodes visited, and explains
which safe local steps would run.

Add `--execute` only when you want to run the hardcoded safe steps for the selected phase:

```powershell
docker compose run --rm dev agentic workflow-run --story story_028_langgraph_safe_workflow_runner --execute
```

Use the `prepare` phase to set up a story workspace through the safe runner:

```powershell
docker compose run --rm dev agentic workflow-run --story story_030_workflow_run_prepare_phase --phase prepare --execute
```

Without `--execute`, the prepare phase writes only the workflow-run plan. With `--execute`, it runs
only `prepare-story` and `workflow-preview`. This creates or refreshes the agent plan, prompt pack,
runbook, prepare report, status, and route preview without executing agents or generated prompts.

For normal story finalization, `workflow-run --phase local-finalize --execute` is the preferred safe
local path after the required agent reports are present and before cloud review packet creation.
`next-step` can recommend this command when local finalization evidence is missing or stale.

`local-finalize` runs only these deterministic local steps: `test-layers`, `finalize-story`,
`review-bundle`, and `workflow-preview`. The runner does not execute agents through the configured
agent runtime or run generated agent prompts, call cloud models, call GitHub APIs, commit, push,
merge, deploy, run destructive commands, or run arbitrary commands from user input. Human final
approval is still required before merge.

Use the `cloud-review-prep` phase after `finalize-story` is ready and before manual cloud review:

```powershell
docker compose run --rm dev agentic workflow-run --story story_031_workflow_run_cloud_review_prep --phase cloud-review-prep --execute
```

Without `--execute`, the cloud-review-prep phase writes only the workflow-run plan. With
`--execute`, it first verifies that `reports/finalize_story_result.yaml` exists and records
`ready_for_review: true`. If that readiness guard fails, it records `REQUEST_CHANGES` and does not
create misleading cloud review evidence. When ready, it runs only `cloud-review-packet` and
`workflow-preview`. This creates or refreshes `cloud_review_packet/cloud_review_export.md` and route
preview evidence, but it does not call the cloud model. A human still sends
`cloud_review_export.md` to the main cloud model manually and records the returned decision with
`record-cloud-review`.

## Create a review bundle

Run this from the repo root to collect review files for a story:

```powershell
docker compose run --rm dev agentic review-bundle --story story_003_generate_stories_from_blueprint
```

The command writes Git status, recent commits, unstaged changes, staged changes, test output, lint output, a file tree, and a short handoff into the story's `review_bundle/` folder. It also records untracked file lists and safe text snapshots for untracked files so reviewers can see newly created files before they are staged.

## Run a quality gate

Run this from the repo root to decide whether a story is ready for human or cloud review:

```powershell
docker compose run --rm dev agentic quality-gate --story story_005_quality_gate
```

The command checks that required story files, agent reports, review bundle files, passing pytest output, passing Ruff output, and local reviewer approval are present. It writes `stories/<story>/reports/quality_gate_result.yaml` and `stories/<story>/reports/quality_gate_report.md` with either `READY_FOR_REVIEW` or `REQUEST_CHANGES`.

## Validate test layers

Run this from the repo root to check that a story test plan addresses every standard testing
layer:

```powershell
docker compose run --rm dev agentic test-layers --story story_014_test_layer_support
```

Story test plans that use `test_layers_version: 1` must address `unit_tests`,
`integration_tests`, `mock_e2e_tests`, `live_read_only_checks`, and
`remote_dev_smoke_tests`. Each layer declares whether it is required, which action was taken or
planned, how often it should run, and the evidence or reason.

Actual tests live in project-level test folders such as `tests/`; `stories/<story>/test_plan.yaml`
declares the coverage plan for review. Not every story needs a new test in every layer, but every
story using the schema must address every layer. If a layer does not apply, use
`not_applicable_with_reason` or `scheduled_later_with_reason` and explain why.

The command writes `stories/<story>/reports/test_layer_result.yaml` and
`stories/<story>/reports/test_layer_report.md`. When a test layer result exists, the quality gate
requires it to have `status: PASSED`. When `test_plan.yaml` uses `test_layers_version: 1`, the
quality gate requests changes if the test layer result is missing.

See `docs/test_layers.md` for the schema and layer definitions.

## Mock E2E testing

Mock E2E tests exercise the full local workflow with temporary projects, fake data, and local
doubles instead of live APIs, cloud models, browser tooling, deployed environments, or a real Git
repository. Project-level mock E2E tests live in `tests/e2e/`; story `test_plan.yaml` files declare
whether mock E2E coverage is required.

See `docs/e2e_testing.md` for the test layer definitions and the recommended mock workflow pattern.

## Finalize a story

Run this from the repo root after agent work and local review are complete:

```powershell
docker compose run --rm dev agentic finalize-story --story story_008_finalize_story_command
```

The command validates that `stories/<story>/` exists, creates or refreshes the review bundle,
validates test layers when `test_plan.yaml` uses `test_layers_version: 1`, runs the quality gate,
regenerates the review bundle so final evidence is captured, writes
`stories/<story>/reports/finalize_story_result.yaml`, writes
`stories/<story>/reports/finalize_story_report.md`, and updates `status.yaml`.

If the quality gate returns `READY_FOR_REVIEW`, `status.yaml` is updated to
`status: ready_for_review` with `ready_for_review: true`. If the quality gate returns
`REQUEST_CHANGES`, `status.yaml` is updated to `status: request_changes` with
`ready_for_review: false`. The command does not commit, push, merge, deploy, or call cloud
models.

## Create a cloud review packet

Run this from the repo root to prepare a cloud-model-ready packet for a completed story:

```powershell
docker compose run --rm dev agentic cloud-review-packet --story story_010_cloud_review_packet
```

For the normal story workflow, prefer
`agentic workflow-run --story <story> --phase cloud-review-prep --execute`; it wraps this packet
command with the finalize readiness guard and refreshes the workflow preview.

The command validates that `stories/<story>/` and `story.md` exist, then writes
`cloud_review_prompt.md`, `cloud_review_context.md`, `cloud_review_checklist.md`,
`cloud_review_result_template.md`, and `cloud_review_export.md` into
`stories/<story>/cloud_review_packet/`. The context includes story content plus available quality
gate, finalize, review bundle, Git status, diff stat, and untracked-file evidence. Missing
optional evidence is listed in the context instead of causing failure.

Use `cloud_review_export.md` as the single file to paste or upload to the main cloud model.

Use `--force` when you intentionally want to overwrite existing cloud review packet files. The
command does not call cloud models, commit, push, merge, or deploy.

## Record a cloud review result

After the main cloud model returns its answer, save that answer to a local Markdown file and record
the decision:

```powershell
docker compose run --rm dev agentic record-cloud-review --story story_010_cloud_review_packet --result-file docs/cloud_review_answer.md
```

The result file must contain exactly one accepted decision, preferably on a line such as
`Decision: APPROVE`. Accepted decisions are `APPROVE`, `APPROVE_WITH_NOTES`, and
`REQUEST_CHANGES`.

The command writes `stories/<story>/reports/cloud_review_result.yaml` and
`stories/<story>/reports/cloud_review_report.md`, then updates `status.yaml` with the cloud review
decision. `APPROVE` and `APPROVE_WITH_NOTES` mark the story ready for a human merge decision;
`REQUEST_CHANGES` marks the story as needing changes. The command does not call cloud models,
commit, push, merge, or deploy, and cloud review is not automatic merge approval.

## Check merge readiness

Run this from the repo root after cloud review has been recorded:

```powershell
docker compose run --rm dev agentic merge-readiness --story story_017_merge_readiness_gate
```

The command checks local evidence from `reports/quality_gate_result.yaml`,
`reports/finalize_story_result.yaml`, optional `reports/test_layer_result.yaml`, and
`reports/cloud_review_result.yaml`. When present, it also reads
`reports/remote_dev_validation_result.yaml`. It writes
`stories/<story>/reports/merge_readiness_result.yaml` and
`stories/<story>/reports/merge_readiness_report.md`, then updates `status.yaml` while preserving
the existing `story_id`.

When local gates pass and cloud review is `APPROVE`, the result is
`READY_FOR_HUMAN_MERGE_DECISION`. When local gates pass and cloud review is
`APPROVE_WITH_NOTES`, the result is `READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION`. Missing evidence,
failed local gates, a non-passing test layer result, or `REQUEST_CHANGES` from cloud review keeps
the result at `REQUEST_CHANGES`.

Remote dev validation is optional when no result has been recorded, and merge-readiness adds an
informational note instead of failing. If a remote dev validation result exists, it becomes part of
the gate: `DEV_VALIDATED` passes, `DEV_VALIDATED_WITH_NOTES` passes with notes,
`DEV_FAILED` blocks as `REQUEST_CHANGES`, and `NOT_RUN` or an unknown status also blocks as
`REQUEST_CHANGES`. The merge-readiness result includes `remote_dev_validation_status` so the human
owner can see whether remote/dev-like validation was missing, passed, passed with notes, failed, or
not run.

This command does not read GitHub Actions status, call cloud models, commit, push, merge, or
deploy. The human owner must still review the PR and confirm GitHub Actions are passing before
merging.

The final merge-readiness workflow is:

1. Run `finalize-story`.
2. Run `workflow-run --phase cloud-review-prep --execute`.
3. Paste or upload `stories/<story>/cloud_review_packet/cloud_review_export.md` to the main cloud model.
4. Save the cloud model answer to a local Markdown file.
5. Run `record-cloud-review --story <story> --result-file <path>`.
6. Optionally run remote dev validation and record the result when remote/dev-like evidence is
   needed.
7. Run `merge-readiness --story <story>`.
8. Have the human owner review the PR, GitHub Actions, and any remote dev validation evidence.
9. Have the human owner decide whether to merge.

## Run remote dev validation

Use remote dev validation when a story needs evidence from a remote or dev-like environment before
the human owner decides whether to merge or release.

First, finalize the story and complete cloud review or merge readiness when applicable. Then create
the remote-dev packet from the repo root:

```powershell
docker compose run --rm dev agentic remote-dev-packet --story story_024_remote_dev_validation_bundle
```

The command validates `stories/<story>/`, reads the story content and available local evidence, and
writes `stories/<story>/remote_dev_validation/remote_dev_packet.md` plus
`stories/<story>/remote_dev_validation/remote_dev_result_template.yaml`. The packet explains which
manual evidence to collect: deployment URL or environment name, branch or commit, Docker/build or
deployment result, smoke checks, applicable integration or mock E2E checks, log review, environment
variable checklist without secret values, database migration status if applicable, rollback notes,
and known risks.

After the remote/dev-like deployment and checks are performed manually or by future CI, save the
completed YAML result and record it:

```powershell
docker compose run --rm dev agentic record-remote-dev --story story_024_remote_dev_validation_bundle --result-file docs/remote_dev_result.yaml
```

Accepted `validation_status` values are `DEV_VALIDATED`, `DEV_VALIDATED_WITH_NOTES`, `DEV_FAILED`,
and `NOT_RUN`. Recording the result writes `reports/remote_dev_validation_result.yaml` and
`reports/remote_dev_validation_report.md`, then updates `status.yaml` with the matching
`remote_dev_*` status while preserving `story_id`.

Remote dev validation is manual evidence, not automatic deployment. The packet command only creates
instructions and a result template, and the record command only stores the completed result. Neither
command provisions an environment or calls external deployment services.

The remote dev validation workflow is:

1. Run `finalize-story`.
2. Run cloud review and `merge-readiness` if applicable.
3. Run `remote-dev-packet --story <story>`.
4. Run remote dev deployment and checks manually or through future CI.
5. Save the completed result YAML.
6. Run `record-remote-dev --story <story> --result-file <path>`.
7. Rerun `merge-readiness --story <story>` so the recorded remote dev status is reflected in the
   merge-readiness result.
8. Have the human owner review the PR and remote-dev evidence before merge or release.

These commands do not deploy, commit, push, merge, call GitHub APIs, or call cloud models. Runtime
files under `stories/<story>/remote_dev_validation/` are ignored by Git except `.gitkeep`.

## Run a post-story improvement scan

After a story is completed, create an improvement scan packet so a research agent, local agent, or
manual cloud model can suggest focused future improvements without expanding the completed story:

```powershell
docker compose run --rm dev agentic improvement-scan create --story story_021_post_story_improvement_scan
```

The command validates that `stories/<story>/` exists and writes
`stories/<story>/improvements/improvement_scan_packet.md` plus
`stories/<story>/improvements/improvement_suggestions_template.yaml`. The packet includes story
content, available reports, test-layer and finalize evidence, local review evidence, and review
bundle handoff context. It instructs reviewers to suggest improvements only within the completed
story's scope, avoid unrelated features, avoid expanding the completed story, and use the
suggestions template format.

After the reviewer returns suggestions, save them as YAML using the generated template shape and
record them into the pending improvement queue:

```powershell
docker compose run --rm dev agentic improvement-scan record --story story_021_post_story_improvement_scan --suggestions-file stories/story_021_post_story_improvement_scan/improvements/improvement_suggestions.yaml
```

The record command validates the suggestions YAML, creates one pending item per suggestion under
`.agentic/improvement_queue/pending/`, and writes
`stories/<story>/improvements/improvement_record_report.md`. It does not promote queue items to
stories, implement suggestions, call cloud models, or call internet search.

The post-story improvement workflow is:

1. Run `finalize-story`.
2. Run `improvement-scan create --story <story>`.
3. Send `improvement_scan_packet.md` to the research, cloud, or local reviewer.
4. Save the returned suggestions YAML.
5. Run `improvement-scan record --story <story> --suggestions-file <path>`.
6. Review the improvement queue later.

## Run a reactive maintenance scan

When tests, logs, CI, remote dev, or an external integration fails, create a maintenance scan packet
instead of guessing at a fix or expanding the active story:

```powershell
docker compose run --rm dev agentic maintenance-scan create --story story_022_reactive_maintenance_scan
```

Use `--logs-path <file-or-folder>` to include local log evidence in the packet. Use `--force` only
when you intentionally want to overwrite an existing maintenance packet and template.

The command validates that `stories/<story>/` exists and writes
`stories/<story>/maintenance/maintenance_scan_packet.md` plus
`stories/<story>/maintenance/maintenance_findings_template.yaml`. The packet includes story
content, monitoring and test plans, status, available test-layer, quality-gate, finalize, local
review, review bundle, pytest, and Ruff evidence, plus optional logs. It instructs reviewers to
identify broken behavior, regressions, failing checks, missing evidence, or external dependency
failures; it also tells them not to implement fixes, not to expand scope, and to use the findings
template format.

After the cloud or local reviewer analyzes the packet, save the findings YAML and record it into
the pending maintenance queue:

```powershell
docker compose run --rm dev agentic maintenance-scan record --story story_022_reactive_maintenance_scan --findings-file stories/story_022_reactive_maintenance_scan/maintenance/maintenance_findings.yaml
```

The record command validates the findings YAML, creates one pending item per finding under
`.agentic/maintenance_queue/pending/`, and writes
`stories/<story>/maintenance/maintenance_record_report.md`. It does not promote queue items to
stories, implement fixes, call cloud models, or call internet search.

The reactive maintenance workflow is:

1. A failure appears in tests, logs, CI, remote dev, or an external integration.
2. Run `maintenance-scan create --story <story>`.
3. Have a cloud or local reviewer analyze the packet.
4. Save the returned findings YAML.
5. Run `maintenance-scan record --story <story> --findings-file <path>`.
6. Review the maintenance queue later.
7. Promote an approved maintenance item to a repair story when it is ready for planned work.

## Run a project feature discovery scan

Periodically create a project-level feature discovery packet to ask what new capabilities would
improve the whole project. This is different from post-story improvement scans and maintenance
scans: suggestions are for new features, not small story follow-ups or repairs.

```powershell
docker compose run --rm dev agentic feature-scan create
```

Use `--focus "<area>"` to steer the scan toward a theme such as `agent runtime`, `cloud review`,
or `portfolio polish`. Use `--force` only when you intentionally want to overwrite the existing
feature scan packet and template.

The command writes `.agentic/feature_scan/feature_scan_packet.md` and
`.agentic/feature_scan/feature_suggestions_template.yaml`. The packet includes blueprint context,
project status, story statuses, queue counts, README context, existing feature queue items, and
docs when present. It asks the reviewer to separate project-derived observations from
external/internet-derived observations, use internet research only when available, avoid invented
sources, and include URLs only for sources actually used.

After the cloud, research, or local reviewer returns suggestions, save the YAML and record it into
the pending feature queue:

```powershell
docker compose run --rm dev agentic feature-scan record --suggestions-file .agentic/feature_scan/feature_suggestions.yaml
```

The record command validates the suggestions YAML, creates one pending item per suggestion under
`.agentic/feature_queue/pending/`, and writes
`.agentic/feature_scan/feature_record_report.md`. It does not promote queue items to stories,
implement features, call cloud models, or call internet search.

The project feature discovery workflow is:

1. Run `feature-scan create`.
2. Send `feature_scan_packet.md` to a cloud, research, or local reviewer.
3. Let the reviewer optionally perform internet research.
4. Save the returned suggestions YAML.
5. Run `feature-scan record --suggestions-file <path>`.
6. Review the feature queue later.
7. Approve and promote selected features to stories when they are ready for planned work.

## Check project status

Run this from the repo root to see a lightweight dashboard for all story workspaces:

```powershell
docker compose run --rm dev agentic project-status
```

The command reads `stories/*/status.yaml` and common workflow evidence, including agent plans,
prompt packs, test-layer results, quality-gate results, finalize-story results, cloud-review
results, workflow-run results, remote dev validation results, merge-readiness results, local review
reports, agent reports, review bundles, cloud review packets, blocking support tickets, and queue
counts for improvement, maintenance, and feature queues. It prints a readable terminal summary and
writes `reports/project_status_report.md`. When workflow-run or remote dev validation has not been
recorded for a story, the dashboard shows it as `not recorded`.

To inspect one story only:

```powershell
docker compose run --rm dev agentic project-status --story story_018_project_status_command
```

Use `--project` to target another project folder. The command does not modify story statuses, call
cloud models, call GitHub APIs, commit, push, merge, or deploy.

## Use improvement, maintenance, and feature queues

Use the generic queue commands to capture future work without expanding the current story scope.
Queue items are YAML files under `.agentic/improvement_queue/`, `.agentic/maintenance_queue/`, or
`.agentic/feature_queue/`. Each queue has `pending`, `approved`, `rejected`, `parked`, and
`closed` folders.

Create an item:

```powershell
docker compose run --rm dev agentic queue create --type improvement --title "Simplify review bundle output" --source-story story_019_queue_management --category cli --priority medium --details "Make the handoff easier to scan."
```

The command writes a structured YAML item to the selected queue's `pending` folder. Item IDs use
the queue prefix, for example `IMP-20260601-120000`, `MAINT-20260601-120000`, or
`FEATURE-20260601-120000`.

List queue items:

```powershell
docker compose run --rm dev agentic queue list
docker compose run --rm dev agentic queue list --type feature --status pending
```

Show one item:

```powershell
docker compose run --rm dev agentic queue show --item IMP-20260601-120000
```

Record a decision and move the item:

```powershell
docker compose run --rm dev agentic queue set-status --item IMP-20260601-120000 --status approved --decision-note "Accepted for future planning."
```

Promote an approved queue item into a story:

```powershell
docker compose run --rm dev agentic queue promote-to-story --item IMP-20260601-120000
```

The command finds the item across improvement, maintenance, and feature queues unless `--type` is
provided. It reads `blueprints/blueprint.yaml`, picks the next available `STORY-###` number from
the blueprint and existing story folders, creates a safe slug from the queue item title, appends a
story entry, creates the story workspace, writes
`stories/<new_story>/reports/promotion_report.md`, writes `reports/queue_promotion_report.md`, and
records `promoted_story_id` and `promoted_story_slug` back into the queue item YAML.

By default, only approved items can be promoted. Use `--allow-pending` only for an explicit manual
override:

```powershell
docker compose run --rm dev agentic queue promote-to-story --item IMP-20260601-120000 --allow-pending
```

To move the queue item after promotion, add either `--close-after-promotion` or
`--park-after-promotion`.

Queue promotion does not execute the new story, call cloud models, notify humans, run agents,
commit, push, merge, or deploy.

## Use the support queue

Run this from the repo root when an agent is blocked and needs a structured answer:

```powershell
docker compose run --rm dev agentic support-ticket create --story story_012_agent_support_queue --agent developer_agent --blocker-type requirements --question "Should the ticket answer command move or copy the file?"
```

The command writes a YAML ticket into `.agentic/support_queue/pending/` and, when the matching
story folder exists, updates `stories/<story>/status.yaml` to `status: blocked` with
`ready_for_review: false` and `blocked_by: <ticket_id>`.

List the queue at any time:

```powershell
docker compose run --rm dev agentic support-ticket list
```

Create a cloud-model-ready support packet without calling any APIs:

```powershell
docker compose run --rm dev agentic support-ticket cloud-packet --ticket SUPPORT-20260530-120000
```

The packet is written next to the ticket as Markdown and instructs the cloud model to return one
of `ANSWER`, `NEEDS_HUMAN`, or `REQUEST_MORE_CONTEXT` while using only the ticket context.

Record a response from a file and move the ticket into `.agentic/support_queue/answered/`:

```powershell
docker compose run --rm dev agentic support-ticket answer --ticket SUPPORT-20260530-120000 --answer-file docs/support_answer.md
```

Close a ticket when no further queue work is needed:

```powershell
docker compose run --rm dev agentic support-ticket close --ticket SUPPORT-20260530-120000
```

The support queue creates runtime YAML and Markdown files only. It does not call cloud APIs,
notify humans, resume agents automatically, or trigger Codex execution.

## Check generated artifact policy

Run this from the repo root to verify generated review artifacts and environment files are not
tracked by Git:

```powershell
docker compose run --rm dev agentic artifact-policy
```

The command uses `git ls-files` and fails if tracked files include generated review bundle files,
generated cloud review packet files, support queue runtime YAML or Markdown files, feature scan
runtime YAML or Markdown files,
`review_to_chatgpt/`, zip files, `.env`, or `.env.*` files. It allows `.gitkeep` inside generated
artifact folders and `.env.example`.

## Local checks

```powershell
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic artifact-policy
docker compose run --rm dev agentic test-layers --story story_014_test_layer_support
```

## Continuous integration

GitHub Actions runs the `CI` workflow on pull requests targeting `main`, pushes to `main`, and pushes to `story/**` branches. The workflow builds the Docker Compose environment, runs pytest and Ruff inside the `dev` container, runs `agentic generate-stories`, fails if generated story files are missing or stale, and runs `agentic artifact-policy`.

See `docs/ci_cd.md` for the full CI behavior and failure-handling notes.
