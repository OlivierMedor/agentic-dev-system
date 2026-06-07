# Skills Matrix

## Python

Where it appears: `src/agentic_dev/` implements the CLI modules, workflow
helpers, artifact policy checks, public-readiness checks, and story tooling.

Why it matters: Python keeps the workflow portable, testable, and easy to run in
Docker and CI.

How to talk about it in interviews: "I used Python to build a local developer
tool with clear modules, file-backed state, validation commands, and pytest
coverage."

## Docker

Where it appears: `Dockerfile` and `docker-compose.yml` define the repeatable
development runtime used by local validation and CI.

Why it matters: Docker reduces environment drift and makes the expected commands
consistent across machines.

How to talk about it in interviews: "I containerized the developer workflow so
the same test, lint, and CLI commands run locally and in CI."

## CI/CD

Where it appears: GitHub Actions uses `.github/workflows/ci.yml` to run build
and validation checks on pull requests and pushes.

Why it matters: CI/CD gives every change a clean validation path before review.
In this project, the pipeline focuses on quality checks rather than deployment.

How to talk about it in interviews: "I used CI/CD as a quality gate: build the
container, run tests, run linting, and check repository hygiene before merge."

## pytest

Where it appears: `tests/` contains coverage for CLI behavior, workflow phases,
artifact policy, public readiness, story generation, and documentation checks.

Why it matters: pytest makes the workflow behavior repeatable and catches stale
docs, broken commands, and unsafe artifact tracking.

How to talk about it in interviews: "I treated docs and workflow behavior as
testable product surfaces, not just manual instructions."

## Ruff

Where it appears: `pyproject.toml` configures Ruff, and validation runs `ruff
check .`.

Why it matters: Ruff keeps Python style and common correctness issues from
becoming review noise.

How to talk about it in interviews: "I used Ruff for fast, consistent linting so
reviewers can focus on behavior and architecture."

## Git/GitHub Workflow

Where it appears: The project uses story branches, pull requests, GitHub
Actions, and explicit artifact policy checks before review.

Why it matters: The workflow keeps each story isolated and reviewable, while
generated runtime files stay out of commits.

How to talk about it in interviews: "I used a branch-and-PR workflow with
automated checks, but kept merge approval as a human decision."

## YAML Schemas/Config

Where it appears: `blueprints/blueprint.yaml`, story status files, agent plans,
runtime config, and generated reports use YAML for structured local state.

Why it matters: YAML makes story scope, acceptance criteria, status, and config
easy to inspect and version.

How to talk about it in interviews: "I used YAML for human-readable workflow
state so agents and reviewers operate from the same source of truth."

## LangGraph

Where it appears: Workflow preview and workflow run phases use LangGraph-backed
state transitions in the CLI implementation and tests.

Why it matters: LangGraph provides deterministic structure for local workflow
phases without turning the system into an autonomous executor.

How to talk about it in interviews: "I used LangGraph to model safe workflow
phase transitions while keeping execution explicit and reviewable."

## Agentic Workflow Design

Where it appears: Blueprint stories, story workspaces, prompt packs, runbooks,
reports, review bundles, and quality gates define the agentic development
lifecycle.

Why it matters: Structured workflows reduce ambiguity and make AI-assisted work
auditable.

How to talk about it in interviews: "I designed the process so agent output is
not just code; it also includes scope, evidence, tests, reports, and review
handoffs."

## Code Review Automation

Where it appears: `review-bundle`, `quality-gate`, cloud review packet
preparation, and related tests gather review context and readiness signals.

Why it matters: Review automation reduces coordination overhead while leaving
judgment with humans.

How to talk about it in interviews: "I automated review preparation, not review
approval."

## Safety/Approval Gates

Where it appears: Artifact policy, public-readiness, runtime config validation,
quality gates, cloud review packet handoff, and README safety documentation.

Why it matters: Safety gates prevent generated artifacts, secrets, private
guidance, and local runtime files from entering public history.

How to talk about it in interviews: "The system separates what automation can
prepare from what only a human can approve."

## Documentation

Where it appears: `README.md`, `docs/`, story reports, runbooks, and public
guides explain the system for operators, contributors, and interviewers.

Why it matters: Documentation makes the project understandable without private
chat context and helps reviewers evaluate decisions quickly.

How to talk about it in interviews: "I documented the project like a product:
overview, workflows, safety model, command map, demo, release notes, and
portfolio narrative."
