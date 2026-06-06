# Minimal Demo Walkthrough

## What The Demo Is

`examples/minimal_project/` is a tiny public-safe project used to practice the
agentic-dev-system workflow. Its blueprint asks for a fake task tracker CLI that
uses mock data.

The demo is intentionally small. The demo does not require cloud models,
secrets, or deployment. It also does not require real APIs, a database, wallets,
or private strategy logic.

## Why It Exists

The main repository has many real story workspaces, reports, and safeguards. The
minimal demo gives new users one compact place to see the same workflow without
needing to understand every command or historical story first.

Use it to learn how a blueprint becomes a generated story workspace, how the
prepare phase builds a prompt pack, and why final review evidence must be based
on real reports instead of assumed completion.

## Workflow Map

```text
Demo blueprint
  |
  v
generate-stories
  |
  v
story workspace
  |
  v
workflow-run prepare
  |
  v
prompt pack
  |
  v
workflow-run local-finalize
  |
  v
review evidence
```

This maps to the real workflow directly:

- `examples/minimal_project/blueprints/blueprint.yaml` is the demo blueprint.
- `generate-stories` turns blueprint stories into
  `stories/story_001_task_tracker_cli/`.
- `workflow-run --phase prepare --execute` creates agent assignments, runbooks,
  and prompt files.
- Agent reports are still expected before a real finalize step can honestly say
  the story is ready.
- `workflow-run --phase local-finalize --execute` collects review evidence only
  after the story workspace has the required reports.

## Run It Safely

Run commands from the repository root:

```powershell
docker compose build
docker compose run --rm dev agentic project-status
docker compose run --rm dev agentic generate-stories --project examples/minimal_project
docker compose run --rm dev agentic workflow-run --project examples/minimal_project --story story_001_task_tracker_cli --phase prepare --execute
```

The included demo blueprint creates the story folder
`examples/minimal_project/stories/story_001_task_tracker_cli/`.

The command below is part of the real workflow, but do not treat it as proof that
the toy story is complete unless the required agent reports have been written:

```powershell
docker compose run --rm dev agentic workflow-run --project examples/minimal_project --story story_001_task_tracker_cli --phase local-finalize --execute
```

If the current workspace has no developer, test, docs, security, and local review
reports for the generated demo story, local finalize can produce a
`REQUEST_CHANGES` result. That is correct. Do not fake completed reports just to
make the demo appear finished.

## What To Inspect Afterward

After `generate-stories`, inspect:

- `examples/minimal_project/stories/story_001_task_tracker_cli/story.md`
- `examples/minimal_project/stories/story_001_task_tracker_cli/test_plan.yaml`
- `examples/minimal_project/stories/story_001_task_tracker_cli/monitoring_plan.yaml`
- `examples/minimal_project/stories/story_001_task_tracker_cli/instructions/`

After the prepare phase, inspect:

- `examples/minimal_project/stories/story_001_task_tracker_cli/agent_plan.yaml`
- `examples/minimal_project/stories/story_001_task_tracker_cli/story_runbook.md`
- `examples/minimal_project/stories/story_001_task_tracker_cli/prompt_pack/`
- `examples/minimal_project/stories/story_001_task_tracker_cli/reports/prepare_story_report.md`

After local finalize, inspect:

- `examples/minimal_project/stories/story_001_task_tracker_cli/reports/finalize_story_report.md`
- `examples/minimal_project/stories/story_001_task_tracker_cli/reports/quality_gate_report.md`
- `examples/minimal_project/stories/story_001_task_tracker_cli/reports/local_review_report.md`

Generated review bundles, cloud review packets, remote dev validation artifacts,
runtime queue files, and `.env` files should stay out of Git.
