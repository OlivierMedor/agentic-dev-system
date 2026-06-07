# Interview Talking Points

## 30-Second Project Pitch

`agentic-dev-system` is a local-first workflow system for AI-assisted software
development. It turns blueprint ideas into story workspaces, agent prompt packs,
review bundles, quality gates, and manual cloud review handoffs. The main idea
is to make agentic coding auditable and safe: automation can prepare evidence,
but humans still approve merges and release decisions.

## 2-Minute Project Explanation

This project solves a practical problem I saw with agentic coding: the work can
move fast, but the process often lives in chat logs instead of a repository. I
built a Python CLI and documentation system that makes the workflow explicit.

A story starts in `blueprints/blueprint.yaml` with acceptance criteria and a
test plan. The CLI generates a story workspace under `stories/`, prepares agent
assignments and prompt packs, records phase reports, creates review bundles,
runs quality gates, and prepares cloud review packets for manual review. Docker
and GitHub Actions keep checks repeatable, while pytest and Ruff enforce
correctness and style.

The important design choice is that the system does not automate trust. It does
not call cloud models automatically, merge PRs, deploy, or approve itself. It
organizes the work so a human reviewer can see what was requested, what changed,
what passed, and what still needs judgment.

## Technical Deep Dive Explanation

The repository is organized around a file-backed workflow:

- `src/agentic_dev/` contains the Python CLI implementation.
- `blueprints/blueprint.yaml` defines story scope and acceptance criteria.
- `stories/` contains generated workspaces, runbooks, prompt packs, status, and
  reports.
- `tests/` validates CLI behavior, workflow phases, artifact policy, public
  readiness, and documentation.
- `docs/` explains how to operate and understand the project.
- Docker provides a consistent development runtime.
- GitHub Actions validates pull requests using the same core checks.

The CLI favors deterministic local commands over hidden automation. Commands
such as `generate-stories`, `workflow-run`, `review-bundle`, `artifact-policy`,
`public-readiness`, and `project-status` create or verify files that a reviewer
can inspect. This makes the system easier to debug than a purely chat-driven
agent workflow.

## How To Explain LangGraph In This Project

LangGraph is used as a workflow orchestration layer for safe local phases. I use
it to model phase transitions for workflow preview and workflow run, not to let
an agent autonomously decide what to execute.

The interview framing is: "LangGraph gives the workflow a graph-shaped control
model, while the repository still keeps execution explicit, local, and
reviewable."

## How To Explain Docker And CI/CD

Docker gives every contributor and CI runner the same development environment.
The expected commands run inside the `dev` service, so pytest, Ruff, and the
`agentic` CLI behave consistently.

GitHub Actions is used as the CI/CD quality layer. In this project, CI/CD means
build and validation rather than deployment. The workflow builds the container,
runs tests, runs linting, checks artifact policy, and verifies workflow hygiene
before a pull request is considered ready.

## How To Explain Safety Controls

The safety controls are intentionally conservative:

- Generated review bundles and cloud review packets are not committed.
- `.env` files and private local guidance are blocked by policy.
- Cloud review packets are prepared for manual handoff, but the system does not
  call models automatically.
- Quality gates summarize readiness but do not approve the work.
- Merge decisions remain human decisions.

The key interview point is that the system separates automation from authority.

## How To Explain What You Personally Built And Learned

I built the project as a professional workflow tool, not just a demo. The work
included Python CLI design, test coverage, Dockerized validation, GitHub Actions
CI, YAML-based story configuration, LangGraph-backed workflow phases, artifact
policy checks, public-readiness checks, and extensive documentation.

The main lesson was that agentic coding needs product engineering discipline:
small scoped stories, clear acceptance criteria, durable evidence, repeatable
checks, and explicit human approval.

## Questions An Interviewer May Ask

### Why not let the agent call cloud models and merge automatically?

Suggested answer: Because those are trust boundaries. The project is designed to
prepare evidence and reduce manual coordination, not to remove human ownership.
Cloud review and merge decisions can affect quality, privacy, and repository
state, so they stay manual.

### What makes this more than a collection of scripts?

Suggested answer: The commands are tied together by a story lifecycle. A
blueprint becomes a workspace, the workspace gets prompt packs and reports, the
reports feed review bundles and quality gates, and CI validates the repository.
The value is the workflow structure and reviewability, not just individual
commands.

### How do you know the workflow is safe for a public repository?

Suggested answer: The repo has artifact policy and public-readiness checks that
block generated artifacts, private guidance, secrets, and local runtime files.
The README and docs also describe what the system intentionally does not
automate.

### Where does LangGraph add value?

Suggested answer: It gives the workflow phases a deterministic graph structure.
That helps model preparation, finalization, and review-prep phases clearly while
keeping actual execution explicit and local.

### What would you improve next?

Suggested answer: I would improve review bundle summaries, add more safe demo
projects, expand contributor-facing docs, and keep tightening policy checks so
public repository hygiene remains automatic.
