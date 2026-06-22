# STORY-066: Story 066 - Review Bundle Cleanliness and Host/Container Diff Normalization

## Goal

Make review bundles and cloud-review packets accurately distinguish committed PR changes, genuine uncommitted working-tree changes, normalization-only differences, generated review artifacts, ignored runtime artifacts, stale Git metadata, and incorrect base references.

## Why This Matters

Review evidence must remain trustworthy when Windows and Linux represent the same tracked content differently, when Docker bind mounts normalize line endings or file modes, and when generated review artifacts exist alongside the source tree.

## Acceptance Criteria

- Committed PR evidence is separate from working-tree evidence.
- The committed diff is generated only from merge-base(base, HEAD)..HEAD.
- The review bundle records repository root, branch, HEAD SHA, remote head SHA when available, requested base ref, resolved base SHA, merge-base SHA, and base freshness.
- A stale or missing base ref is detected and reported.
- Host and container Git identity are compared before evidence generation.
- Host and container HEAD mismatches fail generation.
- Host and container base SHA mismatches fail generation.
- Host and container merge-base mismatches fail generation.
- Wrong clone mounts are detected.
- Detached or ambiguous Git state is reported.
- Genuine staged changes are reported separately.
- Genuine unstaged tracked changes are reported separately.
- Genuine untracked non-ignored files are reported separately.
- Ignored files are summarized separately.
- Generated review artifacts are summarized separately.
- Normalization-only differences are classified separately.
- CRLF versus LF-only differences are classified separately.
- Final-newline-only differences are classified separately.
- UTF-8 BOM-only differences are classified separately.
- Git attribute normalization effects are classified separately.
- Docker bind-mount normalization artifacts are classified separately.
- File-mode-only differences are classified separately.
- Executable-bit-only differences are classified separately.
- Ambiguous mode differences fail strict mode.
- A true content change is never hidden by normalization classification.
- Binary file differences are summarized correctly.
- Rename detection is preserved in the committed diff.
- The review bundle reports the correct changed-file count.
- The review bundle reports the correct commit count in scope.
- The review bundle manifest is versioned.
- The review bundle manifest and patch are checksummed.
- The changed-file list and Git log are checksummed.
- The working-tree report and normalization report are checksummed.
- The cloud-review packet references bundle checksums.
- Review artifact directories are classified before and after generation.
- Generated review directories do not make the repository appear dirty.
- Tracked review artifacts fail policy checks.
- Tracked runtime artifacts fail policy checks.
- Strict clean mode fails on dirty or ambiguous evidence.
- Strict clean mode fails on stale base refs.
- Strict clean mode fails on host/container mismatches.
- Repeated review generation is idempotent.
- The system rejects a stale review bundle.
- The system rejects a packet built from an older bundle.
- The system reports when `.git` metadata is unavailable in the container.
- Windows behavior is covered.
- Linux behavior is covered.
- Docker bind-mount behavior is covered.
- Shell scripts remain LF-only.
- Story 063 behavior remains intact.
- Story 064 behavior remains intact.
- Story 065 behavior remains intact.
- No paid provider integration is introduced.

## Implementation Review Scope

- Review-state models for repository identity, committed diff, working tree, normalization, and artifacts
- Git base resolution, merge-base validation, shallow-clone handling, and stale-ref detection
- Host/container parity checks and actionable mismatch errors
- Line-ending, BOM, final-newline, and git-attribute normalization classification
- File-mode and executable-bit classification with platform-specific behavior
- Cleanliness classification for clean, generated-artifact-only, normalization-only, dirty, and ambiguous states
- Review bundle manifest versioning and checksums
- Cloud-review packet validation against bundle identity and freshness
- Repository-consistent review-bundle and cloud-review-packet commands with diagnostics
- Offline-only tests and documentation for Windows, Linux, and Docker bind mounts
- Backward compatibility for Stories 063, 064, and 065

## Historical Blueprint Notes

- Paid provider integrations.
- Provider network access or automatic provider selection.
- Automatic cloud execution or deployment.
- Automatic merges or local merge operations.
- Silent fallback to older merge bases.
- Hiding real content changes behind normalization classification.
- Story 064 application semantics changes.
- Story 065 batch orchestration semantics changes.

## Definition of Done

- The blueprint defines review-state models, Git identity parity, committed and working-tree separation, normalization classification, strict cleanliness, stale-bundle protection, packet integrity checks, and artifact classification.
- Acceptance criteria cover committed diff evidence, host/container parity, normalization-only differences, file modes, generated artifacts, stale base handling, and regression safety.
- The generated Story 066 workspace is created by agentic generate-stories and generation is idempotent across two runs.
- docker compose run --rm dev pytest passes.
- docker compose run --rm dev ruff check . passes.
- artifact-policy validation passes.
- runtime-config validation passes.
- hidden-Unicode hygiene validation passes.
- Public-readiness validation passes when applicable to the repository state.
- No paid cloud API calls are implemented.
- No provider network access is added.
- No Story 066 runtime implementation code is added in the blueprint branch.
