# Developer Report

## Summary

Implemented a disabled-by-default automatic Codex runtime adapter for
`run-story --execute`.

Cloud review requested changes after Docker smoke testing showed that `codex`
is not available inside the current `dev` container. The adapter already
blocked safely with `BLOCKED_CODEX_COMMAND_NOT_FOUND`; this follow-up clarifies
the user-facing setup guidance for Docker users.

## Changes

- Added `codex_runtime` config defaults and validation.
- Added sequential Codex task execution with stdout, stderr, exit code, timeout,
  and expected-report verification.
- Wired enabled Codex runtime execution into the Story 055 runner path before
  the local model fallback.
- Updated artifact/public-readiness policies for per-role Codex runtime output
  logs.
- Updated runtime docs for the new opt-in adapter.
- Improved the missing Codex command summary, stderr artifact, story-runner
  next action, and runtime report text so they explain that the command is
  missing from the current runtime environment.
- Documented that Story 056 adds the adapter, not Codex installation inside
  Docker; Docker users must install, mount, or configure Codex in the `dev`
  container before enabling `codex_runtime`.
- Added regression coverage for missing-command guidance, Docker/dev-container
  wording, unchanged `BLOCKED_CODEX_COMMAND_NOT_FOUND` behavior, and unchanged
  no-merge/push/deploy/PR safety flags.

## Safety

The adapter uses a fixed allowlisted command shape and `shell=False`. It does
not add merge, push, deploy, PR, force-push, or GitHub API behavior.

When `codex` is absent, the adapter now reports this as a runtime setup
problem, not a story implementation failure, and tells operators to keep
`codex_runtime.enabled: false` until Codex is available in the runtime.
