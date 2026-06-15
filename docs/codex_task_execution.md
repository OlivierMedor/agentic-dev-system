# Codex Task Execution Guide

This guide explains how generated Codex task files are used, either by a human
operator manually or by `agentic run-story --execute` when the automatic Codex
runtime adapter is explicitly enabled.

Codex task files are instructions. `agentic codex-task create` only writes task
files; it does not invoke Codex. Automatic execution is limited to the
allowlisted `codex_runtime` command template in `.agentic/agent_runtime.yaml`.

## What Codex Task Files Are

Codex task files are generated Markdown handoffs for Codex. Each file wraps one
role context packet with the agent identity, story slug, model recommendation,
execution order context, role objective, required report path, validation
commands, safety rules, and do-not-do list.

They live under:

```text
stories/STORY_SLUG/reports/codex_tasks/
```

Example files:

```text
developer_agent_codex_task.md
test_agent_codex_task.md
docs_agent_codex_task.md
security_quality_agent_codex_task.md
local_reviewer_agent_codex_task.md
```

These files are runtime artifacts. They are useful while running a story, but
they should not be committed. Regenerate them when the role context changes.
Generated `codex_tasks` files are ignored and blocked by artifact policy except
for `.gitkeep`.
Generated codex_tasks should not be committed.

## How They Differ From Other Files

Prompt packs live in `stories/STORY_SLUG/prompt_pack/`. They are broad
role-specific prompts created during story preparation. They help explain what
each assigned agent should do, but they are not tuned for a specific runtime
handoff.

Role context packets live in `stories/STORY_SLUG/reports/role_context/`. They
are focused context bundles for each role. They contain the smallest complete
story context the role needs.

Codex task files live in `stories/STORY_SLUG/reports/codex_tasks/`. They turn
role context packets into copy/paste-ready Codex instructions. They tell Codex
which single role to perform, what report to write, and which safety boundaries
to keep.

## Flow

```text
Story
  |
  v
build-context
  |
  v
role_context/*.md
  |
  v
codex-task create
  |
  v
codex_tasks/*.md
  |
  v
manual or configured automatic Codex role passes
  |
  v
reports/
  |
  v
workflow-run local-finalize
```

## Recommended Manual Flow

Run these commands from the repository root.

1. Generate or refresh stories:

```powershell
docker compose run --rm dev agentic generate-stories
```

2. Prepare the story:

```powershell
docker compose run --rm dev agentic workflow-run --story STORY_SLUG --phase prepare --execute
```

3. Build role contexts:

```powershell
docker compose run --rm dev agentic build-context --story STORY_SLUG --all --force
```

4. Create Codex task files:

```powershell
docker compose run --rm dev agentic codex-task create --story STORY_SLUG --all --force
```

5. Run Codex manually, role by role:

- Open `developer_agent_codex_task.md` in Codex.
- Let Codex do only Developer Agent work.
- Open `test_agent_codex_task.md` in Codex.
- Let Codex do only Test Agent work.
- Open `docs_agent_codex_task.md` if docs are needed.
- Open `security_quality_agent_codex_task.md` if safety review is needed.
- Open `local_reviewer_agent_codex_task.md` last.

6. Finalize locally:

```powershell
docker compose run --rm dev agentic workflow-run --story STORY_SLUG --phase local-finalize --execute
```

7. Prepare cloud review:

```powershell
docker compose run --rm dev agentic workflow-run --story STORY_SLUG --phase cloud-review-prep --execute
```

8. Human/cloud review and the merge decision remain manual.

## Automatic Run-Story Flow

When `.agentic/agent_runtime.yaml` contains an enabled safe Codex runtime:

```yaml
codex_runtime:
  enabled: true
  command: codex
  args:
    - exec
    - "-"
  stdin_from_task_file: true
  timeout_seconds: 1800
```

the one-command runner can execute the generated task files:

```powershell
docker compose run --rm dev agentic run-story --story STORY_SLUG --execute
```

The runner prepares the story, builds role context, creates Codex task files,
runs one role task at a time by feeding each task file to `codex exec -` through
stdin, records stdout/stderr/exit code under `reports/codex_runtime/`, verifies
each expected report exists, runs local finalize, runs the quality gate, and
stops before merge. Use this stdin shape unless `codex exec --help` confirms a
different supported file-input flag.

## Recommended Execution Order

Use this order unless the story's `agent_plan.yaml` says otherwise:

1. `research_agent`
2. `planner_agent`
3. `developer_agent`
4. `test_agent`
5. `docs_agent`
6. `security_quality_agent`
7. `local_reviewer_agent`

Not every story needs every role as a separate Codex session. Normal stories can
use one Codex session with clear role phases. High-risk stories can use separate
Codex sessions for better independence. DeFi, risk, and security stories should
use stronger separation between Developer, Test, Security/Quality, and Local
Reviewer passes.

## Running One Role At A Time

For each role pass:

1. Open only that role's `*_codex_task.md`.
2. Tell Codex to follow that task file and stay within that role.
3. Let Codex update only the files allowed by the role.
4. Confirm the role wrote its required report.
5. Review the diff before moving to the next role.

Do not run all task files blindly. Run Developer before Test. Run Local Reviewer
last.

## Role Boundaries

`research_agent` should clarify the problem, inspect relevant files, and write
research notes when needed. It should not implement, test, approve, merge, or
deploy.

`planner_agent` should turn the story into a scoped implementation plan. It
should not edit product code unless the task file explicitly allows a small
planning document change.

`developer_agent` should implement the requested product or documentation change
and write `reports/developer_report.md`. It should not write the main test pass,
approve its own work, merge, deploy, or commit secrets.

`test_agent` should add or update tests, run focused checks, and write
`reports/test_report.md`. It should not rewrite the implementation except for a
tiny fix needed to make tests runnable, and any such fix must be explained.

`docs_agent` should update user-facing or operator documentation and write a
docs report when the story needs one. It should not change runtime behavior.

`security_quality_agent` should inspect safety, scope, artifact handling,
secrets, and risky behavior. It should not approve the story or merge it.

`local_reviewer_agent` should run the final local review after the other roles
finish and write `reports/local_review_report.md`. It should mark
`Decision: READY_FOR_REVIEW` only when the required checks pass and the evidence
is complete.

## Reports To Write

At minimum, normal code or documentation stories should write:

- `stories/STORY_SLUG/reports/developer_report.md`
- `stories/STORY_SLUG/reports/test_report.md`
- `stories/STORY_SLUG/reports/local_review_report.md`

Add `docs_report.md`, `security_quality_report.md`, `research_report.md`, or
`planner_report.md` when those roles do separate material work.

## Checks After Codex Work

Run the checks required by the story. For the normal project workflow, use:

```powershell
docker compose build
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic artifact-policy
docker compose run --rm dev agentic public-readiness
docker compose run --rm dev agentic runtime-config validate
docker compose run --rm dev agentic project-status
```

Then run the story finalization commands:

```powershell
docker compose run --rm dev agentic workflow-run --story STORY_SLUG --phase local-finalize --execute
docker compose run --rm dev agentic workflow-run --story STORY_SLUG --phase cloud-review-prep --execute
docker compose run --rm dev agentic review-bundle --story STORY_SLUG
```

## Safety Rules

- Codex task files are instructions, not automatic execution.
- Codex is not invoked automatically by `agentic codex-task create`.
- Automatic Codex execution requires `codex_runtime.enabled: true`.
- Do not run all task files blindly.
- Run Developer before Test.
- Run Local Reviewer last.
- Human approval is required before merge.
- Do not let Codex merge, deploy, or commit secrets.
- Do not call cloud models from the local workflow unless a human separately
  performs a manual review handoff.
- Do not commit generated `codex_tasks` or `role_context` files.
- Do not commit generated `review_bundle`, `cloud_review_packet`,
  `local_agent_context`, or `local_agent_drafts` files.

## What The Human Still Approves

The human owner still approves the final diff, local evidence, PR, CI status,
cloud review result if used, merge-readiness evidence, and final merge decision.
Codex task files do not approve, merge, push, deploy, or replace human review.
