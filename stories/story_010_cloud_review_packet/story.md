# STORY-010: Add cloud review packet command

## Goal

Create a command that prepares a cloud-model-ready review packet for a completed story.

## Why This Matters

The strong cloud model needs a clean, structured packet that summarizes the story, evidence, quality gate result, changed files, risks, and specific review questions before a human approves merge.

## Acceptance Criteria

- Add a cloud-review-packet command.
- The command requires --story.
- The command defaults --project to the current working directory.
- The command validates that the story folder exists.
- The command creates a cloud_review_packet folder inside the story folder.
- The command creates cloud_review_prompt.md.
- The command creates cloud_review_context.md.
- The command creates cloud_review_checklist.md.
- The command creates cloud_review_result_template.md.
- The prompt tells the cloud model to review architecture, correctness, tests, maintainability, security, scope control, and merge readiness.
- The prompt tells the cloud model not to invent missing facts.
- The prompt tells the cloud model to return APPROVE, APPROVE_WITH_NOTES, or REQUEST_CHANGES.
- The context includes story content, quality gate result, finalize result if present, review bundle handoff if present, and Git status if present.
- The command does not call cloud models automatically.
- The command does not commit, push, merge, or deploy.

## Not In Scope

- No automatic cloud API calls.
- No automatic PR comments.
- No GitHub bot integration.
- No remote dev validation.
- No production deployment.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- cloud-review-packet creates all expected files.
- finalize-story returns ready_for_review.
