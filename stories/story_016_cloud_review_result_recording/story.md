# STORY-016: Add cloud review export and result recording

## Goal

Create a one-file cloud review export and a command that records the main cloud model's review decision back into the story reports.

## Why This Matters

The system needs a clean handoff to the main cloud model and a structured way to store the model's review decision before merge. This closes the loop between local quality gates, cloud review, and human approval.

## Acceptance Criteria

- Update cloud-review-packet to create cloud_review_export.md.
- cloud_review_export.md combines prompt, context, checklist, result template, and key review evidence into one file.
- Add a record-cloud-review command.
- record-cloud-review requires --story and --result-file.
- record-cloud-review defaults --project to the current working directory.
- record-cloud-review validates that the story folder exists.
- record-cloud-review validates that the result file exists.
- record-cloud-review extracts a decision from the result file.
- Accepted decisions are APPROVE, APPROVE_WITH_NOTES, and REQUEST_CHANGES.
- record-cloud-review writes reports/cloud_review_result.yaml.
- record-cloud-review writes reports/cloud_review_report.md.
- APPROVE updates status.yaml to cloud_review_approved.
- APPROVE_WITH_NOTES updates status.yaml to cloud_review_approved_with_notes.
- REQUEST_CHANGES updates status.yaml to request_changes.
- record-cloud-review preserves story_id in status.yaml.
- The command does not call cloud models automatically.
- The command does not commit, push, merge, or deploy.
- Tests verify cloud review export generation and result recording.
- README documents the cloud review workflow.

## Not In Scope

- No automatic OpenAI API calls.
- No automatic ChatGPT upload.
- No GitHub PR bot comments.
- No automatic merge.
- No deployment.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- cloud-review-packet creates cloud_review_export.md.
- record-cloud-review is tested with sample result files.
- finalize-story marks this story ready for review.
