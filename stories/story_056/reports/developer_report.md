# Developer Report

## Summary

Implemented a disabled-by-default automatic Codex runtime adapter for
`run-story --execute`.

## Changes

- Added `codex_runtime` config defaults and validation.
- Added sequential Codex task execution with stdout, stderr, exit code, timeout,
  and expected-report verification.
- Wired enabled Codex runtime execution into the Story 055 runner path before
  the local model fallback.
- Updated artifact/public-readiness policies for per-role Codex runtime output
  logs.
- Updated runtime docs for the new opt-in adapter.

## Safety

The adapter uses a fixed allowlisted command shape and `shell=False`. It does
not add merge, push, deploy, PR, force-push, or GitHub API behavior.
