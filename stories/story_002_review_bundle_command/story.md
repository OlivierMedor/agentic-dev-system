# STORY-002: Review Bundle Command

## Goal

Create a reusable command that generates a review bundle for a specific story.

## Why This Matters

The review bundle is the evidence packet used by a human reviewer and a strong cloud model to decide whether a story is ready for review, merge, or further changes.

## Acceptance Criteria

- Add a command named `agentic review-bundle`.
- The command accepts:
  - `--project`
  - `--story`
- The command creates or updates:
  - `stories/<story>/review_bundle/handoff.md`
  - `stories/<story>/review_bundle/git_status.txt`
  - `stories/<story>/review_bundle/git_log.txt`
  - `stories/<story>/review_bundle/git_diff_stat.txt`
  - `stories/<story>/review_bundle/git_diff.patch`
  - `stories/<story>/review_bundle/pytest_output.txt`
  - `stories/<story>/review_bundle/ruff_output.txt`
  - `stories/<story>/review_bundle/file_tree.txt`
- All generated files use UTF-8.
- The command does not create a zip file.
- The command excludes noisy folders like `.git`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, and `.venv` from the file tree.
- Tests are added for the review bundle logic.
- README is updated with usage instructions.

## Not In Scope

- No cloud upload.
- No automatic GitHub PR creation.
- No deployment validation bundle yet.
- No LangGraph yet.
- No Postgres yet.

## Definition of Done

- `pytest` passes.
- `ruff check .` passes.
- `agentic review-bundle --project /app --story story_002_review_bundle_command` creates the expected review bundle files.
- The handoff file clearly summarizes the review status.