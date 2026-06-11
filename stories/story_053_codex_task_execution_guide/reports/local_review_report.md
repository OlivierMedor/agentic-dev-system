# Local Review Report

## Story

story_053_codex_task_execution_guide

## Decision

Decision: READY_FOR_REVIEW

## Review Notes

The change matches Story 053 scope. It adds beginner-friendly manual guidance
for generated Codex task files and updates the existing operator docs with short
cross-links. It does not add automatic Codex execution, call Codex from
`agentic`, call cloud models, run generated task files, merge, deploy, or change
runtime behavior.

The guide clearly says Codex task files are instructions, not automatic
execution; Developer should run before Test; Local Reviewer should run last;
human approval is required before merge; and generated `codex_tasks` and
`role_context` files should not be committed.

## Validation Reviewed

- `docker compose build`: passed.
- `docker compose run --rm dev pytest`: passed, 483 tests.
- `docker compose run --rm dev ruff check .`: passed.
- `docker compose run --rm -v C:\dev\agentic-dev-system\.git:/git -e GIT_DIR=/git/worktrees/agentic-story053 -e GIT_WORK_TREE=/app dev agentic artifact-policy`: passed.
- `docker compose run --rm -v C:\dev\agentic-dev-system\.git:/git -e GIT_DIR=/git/worktrees/agentic-story053 -e GIT_WORK_TREE=/app dev agentic public-readiness`: passed.
- `docker compose run --rm dev agentic runtime-config validate`: passed.
- `docker compose run --rm dev agentic project-status`: ran successfully.
- Story 053 `generate-stories`, prepare, `build-context`, and `codex-task create` completed successfully.
- Story 053 `workflow-run --phase local-finalize --execute`: passed with `ready_for_review: true`.
- Story 053 `workflow-run --phase cloud-review-prep --execute`: passed without calling cloud models.
- Story 053 `review-bundle`: passed with pytest and Ruff evidence.

## Worktree Note

The direct Docker artifact-policy and public-readiness commands could not read
the Windows worktree `.git` pointer from inside the container. Rerunning those
commands with the shared Git metadata mounted made the same worktree visible to
Git inside Docker and both checks passed.

The generated review bundle is intentionally uncommitted. Because this branch
uses a secondary Windows worktree, the Dockerized Git evidence can show broad
line-ending/worktree noise even though host `git status --short` is scoped to
the Story 053 files.
