# Golden Path Operator Guide

This guide explains the normal way to use `agentic-dev-system` from blueprint to
human PR merge decision. It is written for operators who are new to the project.

For a diagram-first map of the same system, see `docs/system_map.md`. Before
making the repository public, use `docs/public_launch_checklist.md`. Suggested
GitHub description, topics, and repository settings live in
`docs/repo_settings.md`.

The CLI examples show the command after `agentic`. In Docker, run them from the
repo root as:

```powershell
docker compose run --rm dev agentic COMMAND
```

## What the system is

`agentic-dev-system` is a local-first workflow tool for agent-assisted
development. It turns a product blueprint into story workspaces, prepares agent
prompts, records local evidence, prepares review packets, and tells the human
owner when a story has enough evidence for a merge decision.

It does not replace the human owner. It does not merge PRs, deploy, call cloud
models automatically, or approve its own work.

## What lives in the project repo

The project repo is the source of truth for planned work and reviewed code:

```text
project repo
|-- README.md
|-- blueprints/
|   `-- blueprint.yaml
|-- docs/
|-- stories/
|   `-- story_###_name/
|-- src/
|-- tests/
`-- .github/
```

Important repo files:

- `blueprints/blueprint.yaml` describes approved stories.
- `stories/STORY_SLUG/story.md` explains one story's goal and acceptance criteria.
- `stories/STORY_SLUG/test_plan.yaml` explains test coverage expectations.
- `stories/STORY_SLUG/monitoring_plan.yaml` explains what failures to watch for.
- `stories/STORY_SLUG/reports/` stores human-readable story reports.
- `src/` and `tests/` hold implementation and project tests.
- `docs/` holds operator and workflow documentation.

## What lives in .agentic/

`.agentic/` is local workflow configuration and runtime queue state:

```text
.agentic
|-- agent_runtime.yaml
|-- support_queue/
|-- improvement_queue/
|-- maintenance_queue/
`-- feature_queue/
```

`agent_runtime.yaml` describes expected agent providers, models, approval modes,
allowed routine commands, and commands that require human approval.

Queue folders hold structured YAML items. Runtime queue files are local workflow
state, not product source code.

## What stories are

A story is a small unit of approved work. Each story has its own folder under
`stories/`:

```text
stories/story_032_example/
|-- story.md
|-- status.yaml
|-- test_plan.yaml
|-- monitoring_plan.yaml
|-- agent_plan.yaml
|-- prompt_pack/
`-- reports/
```

The story folder answers these questions:

- What is this work trying to achieve?
- Which agents should work on it?
- Which tests and checks prove it is done?
- Which reports show what happened?
- Is it blocked, ready for review, or waiting for a human decision?

## What review bundles are

A review bundle is generated evidence for a story. It collects local context such
as Git status, diffs, test output, lint output, file tree, and a handoff summary.
Changed paths that are directories, submodules, missing, binary, or unreadable
are still recorded in the bundle with explicit metadata, but their contents are
not read as normal text files.

Review bundles live under:

```text
stories/STORY_SLUG/review_bundle/
```

They are useful for reviewers, but generated bundle files should not be
committed. Regenerate them when needed.

## What cloud review packets are

A cloud review packet is the manual handoff for the main cloud model. It packages
the story, review context, checklist, result template, and final export file.

Cloud review packets live under:

```text
stories/STORY_SLUG/cloud_review_packet/
```

The operator sends `cloud_review_export.md` to the main cloud model manually.
After the model returns a decision, the operator records that answer with
`agentic record-cloud-review`.

The packet command prepares evidence only. It does not call the cloud model.

## What workflow-run phases are

`agentic workflow-run` is the safe LangGraph runner for deterministic local
steps. Without `--execute`, it only writes a plan. With `--execute`, it runs a
small hardcoded allowlist for the selected phase.

```text
prepare
  runs: prepare-story, micro-readiness, workflow-preview
  use: set up a story workspace before agent work

local-finalize
  runs: test-layers, finalize-story, review-bundle, workflow-preview
  use: collect final local evidence after agent reports exist

cloud-review-prep
  runs: cloud-review-packet, workflow-preview
  use: prepare cloud review evidence after finalize-story is ready
```

The runner does not execute agents, run arbitrary story commands, call cloud
models, call GitHub APIs, commit, push, merge, or deploy.

The prepare phase also records micro-readiness. That result helps decide whether
generated prompts should be run in micro mode, slim mode, or with a stronger
configured agent runtime. Warnings are guidance for story sizing and local model
fit; they are not automatic merge, deploy, or workflow blockers.

## Manual Codex Task Files

After prepare, operators can build focused role context packets and create
Codex task files for manual role passes:

```powershell
agentic build-context --story STORY_SLUG --all --force
agentic codex-task create --story STORY_SLUG --all --force
```

Open one generated file from `stories/STORY_SLUG/reports/codex_tasks/` in Codex
at a time. Run Developer before Test, and run Local Reviewer last. Generated
`role_context` and `codex_tasks` files are runtime artifacts and should not be
committed. For the full beginner guide, see `docs/codex_task_execution.md`.

## Queue differences

Use queues to capture work without expanding the active story.

```text
support_queue
  For blockers and questions that stop the current story.
  Example: "Which requirement should this implementation follow?"

improvement_queue
  For follow-up polish or refinements found after a story.
  Example: "Make this report easier to scan."

maintenance_queue
  For repairs caused by failing tests, logs, CI, integrations, or remote checks.
  Example: "Fix the regression shown in this test output."

feature_queue
  For new capabilities that should be planned as future stories.
  Example: "Add a dashboard for queue status."
```

## Normal happy path

The normal path starts with a blueprint and ends with a human merge decision:

```text
blueprint
   |
   v
generate story workspaces
   |
   v
prepare story
   |
   v
agents do scoped work and write reports
   |
   v
local finalize and review bundle
   |
   v
cloud review packet
   |
   v
manual cloud review result recorded
   |
   v
merge-readiness check
   |
   v
human owner reviews PR, CI, evidence, and decides
```

Run these commands in order for the common path:

```powershell
agentic generate-stories
agentic workflow-run --story STORY_SLUG --phase prepare --execute
agentic next-step --story STORY_SLUG
agentic project-status
agentic workflow-run --story STORY_SLUG --phase local-finalize --execute
agentic workflow-run --story STORY_SLUG --phase cloud-review-prep --execute
agentic record-cloud-review --story STORY_SLUG --result-file OUTPUT_FILE
agentic merge-readiness --story STORY_SLUG
agentic artifact-policy
```

Use `agentic next-step --story STORY_SLUG` whenever you are unsure what should
happen next. Use `agentic project-status` to see the dashboard for all stories.

## Remote or dev-like validation

Some stories need evidence from a remote/dev-like environment before the human
owner decides. In that case, create a manual validation packet, run the remote
checks outside this CLI, then record the result:

```powershell
agentic remote-dev-packet --story STORY_SLUG
agentic record-remote-dev --story STORY_SLUG --result-file OUTPUT_FILE
agentic merge-readiness --story STORY_SLUG
```

Remote dev validation is evidence recording. These commands do not deploy or
call external deployment services.

## When a story is blocked

If an agent cannot continue because requirements are unclear, evidence is
missing, a command fails in a way that needs judgment, or scope is ambiguous:

1. Stop expanding the story.
2. Record the blocker in the support queue.
3. Keep `status.yaml` blocked until the answer is recorded.
4. Run `agentic next-step --story STORY_SLUG` after the blocker is answered.

Do not guess around a blocker just to reach finalization.

## When tests or logs fail

If tests, logs, CI, remote dev, or integrations fail:

1. Keep the story in request-changes or blocked state.
2. Read the failing output and fix only issues in the story scope.
3. Rerun the focused check first, then the required local checks.
4. If the failure points to broader repair work, record it in the maintenance
   queue instead of expanding the active story.
5. Rerun `agentic workflow-run --story STORY_SLUG --phase local-finalize --execute`
   after the fix and reports are ready.

## What not to commit

Do not commit:

- Secrets or `.env` files.
- Generated review bundle files under `stories/STORY_SLUG/review_bundle/`.
- Generated cloud review packet files under `stories/STORY_SLUG/cloud_review_packet/`.
- Generated remote dev validation files under `stories/STORY_SLUG/remote_dev_validation/`.
- Support queue runtime ticket files.
- Feature scan runtime files.
- Temporary files, zip files, or `review_to_chatgpt/`.
- Logs that contain secrets or machine-specific data.

Run this before staging or committing:

```powershell
agentic artifact-policy
```

## What the human owner must still approve

The human owner must still approve:

- The PR content and final diff.
- The GitHub Actions or CI result.
- The cloud review decision and any notes.
- Remote/dev-like validation evidence when needed.
- Whether `merge-readiness` evidence is enough to merge.
- The final PR merge decision.

`agentic merge-readiness` can say the story is ready for a human merge decision,
but it is not an automatic approval and it does not merge the PR.
