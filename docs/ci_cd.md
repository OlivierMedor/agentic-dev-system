# CI/CD

This project uses GitHub Actions to run the same Docker-based quality checks that developers run locally. The workflow is defined in `.github/workflows/ci.yml` and is named `CI`.

## When CI runs

CI runs on:

- Pull requests targeting `main`.
- Pushes to `main`.
- Pushes to branches under `story/**`.

The workflow does not deploy, configure branch protection, call cloud review services, or require project-specific secrets.

## What CI checks

The `quality` job runs on `ubuntu-latest` and performs these checks:

- Checks out the repository with `actions/checkout`.
- Prints Docker and Docker Compose versions for troubleshooting.
- Builds the Docker Compose environment with `docker compose build`.
- Runs tests inside the dev container with `docker compose run --rm dev pytest`.
- Runs Ruff inside the dev container with `docker compose run --rm dev ruff check .`.
- Runs `docker compose run --rm dev agentic generate-stories`.
- Fails if `git status --short` reports generated story files or other working tree changes after story generation.

## Why Docker is used

Docker keeps CI aligned with the local development environment. The GitHub runner builds the same Compose service and runs checks inside the `dev` container, reducing differences between local machines and CI.

## Why generated stories are checked

Story workspaces are generated from the blueprint. CI runs `agentic generate-stories` as an idempotency and sanity check so pull requests cannot pass while generated story files are missing or stale. If generation changes the working tree, the workflow prints the changed paths and exits with a failure.

## When CI fails

Use the failing GitHub Actions step to choose the local command to run:

```powershell
docker compose build
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic generate-stories
git status --short
```

Commit any intended generated story files or source changes before pushing again. Do not commit secrets, `.env` files, private keys, or environment-specific credentials.
