# STORY-017: Add merge readiness gate

## Goal

Create a command that checks whether a story is ready for the human owner to make the final merge decision after local gates and cloud review.

## Why This Matters

The system needs a final local checkpoint after cloud review is recorded. It should clearly say whether the story is ready for human merge approval, ready with notes, or still needs changes. The command must not merge automatically.

## Acceptance Criteria

- Add a merge-readiness command.
- merge-readiness requires --story.
- merge-readiness defaults --project to the current working directory.
- merge-readiness validates that the story folder exists.
- merge-readiness reads reports/quality_gate_result.yaml if present.
- merge-readiness reads reports/finalize_story_result.yaml if present.
- merge-readiness reads reports/test_layer_result.yaml if present.
- merge-readiness reads reports/cloud_review_result.yaml if present.
- merge-readiness returns READY_FOR_HUMAN_MERGE_DECISION when local gates pass and cloud review decision is APPROVE.
- merge-readiness returns READY_WITH_NOTES_FOR_HUMAN_MERGE_DECISION when local gates pass and cloud review decision is APPROVE_WITH_NOTES.
- merge-readiness returns REQUEST_CHANGES when cloud review decision is REQUEST_CHANGES or required evidence is missing.
- merge-readiness writes reports/merge_readiness_result.yaml.
- merge-readiness writes reports/merge_readiness_report.md.
- merge-readiness updates status.yaml safely.
- merge-readiness preserves story_id in status.yaml.
- merge-readiness does not commit, push, merge, deploy, or call cloud models.
- README documents the final merge-readiness workflow.
- Tests verify merge-readiness behavior for approve, approve with notes, request changes, and missing evidence.

## Not In Scope

- No automatic GitHub merge.
- No automatic GitHub PR approval.
- No deployment.
- No production release bundle.
- No remote dev validation.
- No cloud API call.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- merge-readiness works with sample cloud review results.
- finalize-story marks this story ready for review.
