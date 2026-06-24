# Finalize Story Report

## Story

evidence-derived-local-execution-recording

## What finalize-story did

- Created or refreshed the review bundle at `/app/stories/evidence-derived-local-execution-recording/review_bundle`.
- Ran test layer validation when `test_plan.yaml` used `test_layers_version: 1`.
- Ran the quality gate and wrote `/app/stories/evidence-derived-local-execution-recording/reports/quality_gate_result.yaml`.
- Regenerated the review bundle after the quality gate so final evidence is captured.
- Wrote finalize result data to `/app/stories/evidence-derived-local-execution-recording/reports/finalize_story_result.yaml`.
- Updated `status.yaml` without committing, pushing, merging, deploying, or calling cloud models.

## Quality gate result

- Quality gate status: REQUEST_CHANGES
- Test layer result: /app/stories/evidence-derived-local-execution-recording/reports/test_layer_result.yaml
- Ready for review: False
- pytest in final review bundle passed: True
- Ruff in final review bundle passed: True

## Story status update

- status: request_changes
- ready_for_review: false

## Next recommended action

Fix the failed checks, regenerate any missing reports, then run the quality gate again.

Human or cloud review is still required before merge.

## Notes

- force: false
