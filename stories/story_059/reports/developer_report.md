# Developer Report

## Summary

- Implemented Option B: explicit Docker-compatible Codex execution using
  `codex exec --sandbox danger-full-access -` only when
  `docker_isolation_acknowledged: true`.
- Kept `workspace-write` as the default safe runtime shape and kept
  `codex_runtime.enabled: false` by default.
- Updated docs to explain the `bwrap` nested-sandbox failure mode, the Docker
  isolation tradeoff, and the enablement steps.
- Follow-up doc cleanup removed duplicated and conflicting wording so all
  operator docs now describe the same two accepted runtime shapes consistently.

## Code Changes

- Updated `src/agentic_dev/runtime_config.py` to:
  - keep the exact `workspace-write` shape,
  - allow the exact Docker-compatible `danger-full-access` shape,
  - require `docker_isolation_acknowledged: true` for the Docker shape,
  - reject acknowledgement when the runtime is still using `workspace-write`.
- Updated `.agentic/agent_runtime.yaml` to keep the runtime disabled by default
  and add `docker_isolation_acknowledged: false`.
- Updated runtime docs in `README.md`, `docs/codex_runtime.md`,
  `docs/codex_docker_runtime.md`, and `docs/runtime_config.md`.

## Docker Smoke Evidence

- Verified inside Docker:
  - `which codex` -> `/usr/local/bin/codex`
  - `codex --version` -> `codex-cli 0.139.0`
  - `codex exec --help` shows `workspace-write` and `danger-full-access`.
- Ran a disposable smoke project with the acknowledged Docker-compatible config.
- First run reproduced a contract mismatch where Codex wrote to the project-root
  `reports/` folder instead of the story-scoped report path.
- Tightened the disposable task instructions to the exact story path and reran.
- Confirmed the runtime then passed and created the expected story report file.

## Story Workflow Evidence

- `docker compose run --rm dev agentic workflow-run --story story_059 --phase local-finalize --execute`
  completed and recorded:
  - `test-layers status: PASSED`
  - `finalize-story status: ready_for_review`
  - `review-bundle completed; pytest passed: True; ruff passed: True`
- `docker compose run --rm dev agentic merge-readiness --story story_059`
  returned `REQUEST_CHANGES` only because
  `reports/cloud_review_result.yaml` is intentionally still missing.

## Documentation Cleanup

- Cleaned wording in `README.md`, `docs/codex_runtime.md`,
  `docs/runtime_config.md`, and `docs/codex_docker_runtime.md`.
- Removed duplicated trailing wording and normalized the policy language to:
  - Default safe runtime: `codex exec --sandbox workspace-write -`
  - Docker-compatible fallback: `codex exec --sandbox danger-full-access -`
  - Required acknowledgement: `docker_isolation_acknowledged: true`

## Security Notes

- Docker-compatible `danger-full-access` remains disabled by default.
- It can read and write the mounted workspace and may access Codex auth or
  config state inside the container, including `CODEX_HOME`.
- The mode is documented for trusted repos and controlled local automation
  only.
- The runner still does not merge, push, force-push, deploy, open PRs, or call
  GitHub APIs.
