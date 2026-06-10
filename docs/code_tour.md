# Code Tour

This tour explains the repository from the outside in. It is written for a
beginner who wants to know where a feature lives before changing it.

Think of the project like a small workshop:

- `blueprints/` are the architect plans.
- `stories/` are job folders for each approved piece of work.
- `src/agentic_dev/` is the factory machinery.
- `tests/` are the inspectors.
- `docs/` is the user manual.
- `.agentic/` is the project rules and control panel.

## Big Picture Flow

```text
User command
  |
  v
src/agentic_dev/cli.py
  |
  v
feature module
  |
  v
reports / story files
  |
  v
tests verify behavior
```

Most commands start in `src/agentic_dev/cli.py`. The CLI parses the command,
calls a focused module such as `quality_gate.py` or `review_bundle.py`, and that
module writes reports or story files. Tests then check that the command behaves
as expected.

## `.agentic/`

`.agentic/` is the project rules and control panel. It holds local runtime
configuration and queue folders used by the workflow.

Important examples:

- `.agentic/agent_runtime.yaml` describes the configured agent runtime.
- `.agentic/support_queue/` stores local support tickets for blocked work.
- `.agentic/improvement_queue/`, `.agentic/maintenance_queue/`, and
  `.agentic/feature_queue/` store local queue state.

Runtime queue files are local artifacts. They should not be committed unless the
repository policy explicitly allows a placeholder such as `.gitkeep`.

## `.github/workflows/`

`.github/workflows/` contains GitHub Actions automation. The main workflow is
the remote inspector that checks changes in a clean GitHub runner.

Look here when you need to know what CI runs for a pull request.

## `blueprints/`

`blueprints/` are the architect plans. The public blueprint file,
`blueprints/blueprint.yaml`, lists approved stories with goals, acceptance
criteria, test plans, and monitoring notes.

`agentic generate-stories` reads the blueprint and creates matching folders
under `stories/`.

Private operator guidance may exist locally in
`blueprints/agentic-architecture.md`. That file is intentionally ignored and
blocked from being tracked.

## `docs/`

`docs/` is the user manual. These files explain how to operate and understand
the system without reading all of the Python code.

Useful starting points:

- `docs/golden_path.md` explains the normal workflow.
- `docs/system_map.md` shows system diagrams.
- `docs/command_map.md` maps commands to code and tests.
- `docs/public_readiness.md` explains what must stay out of Git.

## `src/agentic_dev/`

`src/agentic_dev/` is the factory machinery. It contains the Python package that
implements the `agentic` command.

Important pieces:

- `cli.py` is the front door for every command.
- `story_generator.py` creates story workspaces from the blueprint.
- `prepare_story.py`, `workflow_run.py`, and `finalize_story.py` move stories
  through local workflow phases.
- `review_bundle.py`, `quality_gate.py`, and `merge_readiness.py` collect and
  check review evidence.
- Queue modules such as `support_queue.py` and `queue_management.py` manage
  local follow-up work.

If you are changing command behavior, start with `cli.py`, then follow the
import to the feature module.

## `stories/`

`stories/` are job folders. Each story folder keeps the plan, generated agent
instructions, reports, and status for one piece of work.

A typical story contains:

- `story.md` for the request.
- `status.yaml` for current state.
- `test_plan.yaml` and `monitoring_plan.yaml` for verification expectations.
- `agent_plan.yaml`, `instructions/`, and `prompt_pack/` for agent handoff.
- `reports/` for developer, test, finalize, and review evidence.
- `review_bundle/`, `cloud_review_packet/`, and `remote_dev_validation/` as
  generated artifact folders that normally keep only `.gitkeep` tracked.

## `tests/`

`tests/` are the inspectors. They verify command behavior, generated files,
documentation links, safety policies, and workflow decisions.

Most feature modules have a matching test file:

- `src/agentic_dev/quality_gate.py` is checked by `tests/test_quality_gate.py`.
- `src/agentic_dev/workflow_run.py` is checked by `tests/test_workflow_run.py`.
- `src/agentic_dev/public_readiness.py` is checked by
  `tests/test_public_readiness.py`.

When adding or changing a feature, look for the matching test file first.

## `Dockerfile` / `compose.yml`

`Dockerfile` and `compose.yml` define the local development environment. They
make commands repeatable by running Python, pytest, Ruff, and the `agentic` CLI
inside the same container setup.

Most validation commands use this shape:

```powershell
docker compose run --rm dev COMMAND
```

## `README.md`

`README.md` is the front page. It explains what the project is, why it exists,
how to run the core workflow, and where to find deeper docs.

Keep it concise. Put detailed explanations in `docs/` and link to them from the
README.

## `pyproject.toml`

`pyproject.toml` is the Python project configuration. It defines packaging,
dependencies, CLI entry points, pytest settings, and Ruff settings.

Look here when you need to understand how `agentic` is installed or how tests
and linting are configured.
