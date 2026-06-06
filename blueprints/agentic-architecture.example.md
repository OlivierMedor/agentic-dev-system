# Agentic Architecture Example

This file is a safe public example for documenting how an operator wants to run this repository.

Keep the real local guidance in `blueprints/agentic-architecture.md`. That private file is ignored
by Git and must not be committed.

## Repository Role

This repository provides a local CLI for an agentic development workflow. It can generate story
workspaces, prepare prompt packs, run deterministic local checks, collect review evidence, and
produce status reports.

## Safe Operating Boundaries

- Do not call cloud models automatically.
- Do not commit secrets or `.env` files.
- Do not commit generated review bundles, cloud review packets, or remote dev validation packets.
- Do not merge, deploy, or approve pull requests automatically.
- Keep generated runtime queue files out of Git.

## Typical Story Flow

1. Update `blueprints/blueprint.yaml`.
2. Run `agentic generate-stories`.
3. Run `agentic workflow-run --story <story> --phase prepare --execute`.
4. Complete the story work.
5. Run local validation and finalization.
6. Prepare review evidence for a human owner.
7. Have the human owner make the final merge decision.

## Local Customization Notes

Add only public-safe notes here. Do not include:

- Private local paths.
- Tokens, API keys, account names, or secret values.
- Customer or unpublished project details.
- Private operator instructions.
- Generated runtime artifacts.
