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
- Runs `docker compose run --rm dev agentic artifact-policy`.

## Why Docker is used

Docker keeps CI aligned with the local development environment. The GitHub runner builds the same Compose service and runs checks inside the `dev` container, reducing differences between local machines and CI.

GitHub Actions also runs Git inside that Docker container while the checked-out repository is mounted at `/app`. Because Git can reject mounted repositories when the container user does not own the files, the Docker image marks `/app` as a safe directory so Git commands used in CI continue to work without trusting every repository on the system.

## Why generated stories are checked

Story workspaces are generated from the blueprint. CI runs `agentic generate-stories` as an idempotency and sanity check so pull requests cannot pass while generated story files are missing or stale. If generation changes the working tree, the workflow prints the changed paths and exits with a failure.

## Why generated artifacts are blocked

Review bundles, cloud review packets, role context packets, Codex task files, runtime queue item
files, private operator guidance, `review_to_chatgpt/`, zip files, and local environment files are
generated, private, or machine-specific artifacts. CI runs `agentic artifact-policy` so pull
requests fail when any of those files are tracked by Git. The policy allows `.gitkeep` files inside
generated artifact folders and `.env.example` as a safe template.

## When CI fails

Use the failing GitHub Actions step to choose the local command to run:

```powershell
docker compose build
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic generate-stories
docker compose run --rm dev agentic artifact-policy
git status --short
```

Commit any intended generated story files or source changes before pushing again. Remove generated
review artifacts, runtime queue item files, private operator guidance, zip files, and
environment-specific files from Git tracking before pushing. Do not commit secrets, `.env` files,
private keys, or environment-specific credentials.
