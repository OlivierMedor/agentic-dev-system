# Minimal Demo Project

This is a tiny public-safe project for trying the agentic-dev-system workflow.
The sample blueprint asks for a simple task tracker CLI using mock data.

The demo does not require cloud models, secrets, deployment, real APIs, a
database, wallets, or private strategy logic.

From the repository root:

```powershell
docker compose run --rm dev agentic generate-stories --project examples/minimal_project
docker compose run --rm dev agentic workflow-run --project examples/minimal_project --story story_001_task_tracker_cli --phase prepare --execute
```

See `docs/demo_walkthrough.md` in the repository root for the full walkthrough.
