# Finalize Story Report

## Story

story_060

## What finalize-story did

- Created or refreshed the review bundle at `/workspace/stories/story_060/review_bundle`.
- Ran test layer validation when `test_plan.yaml` used `test_layers_version: 1`.
- Ran the quality gate and wrote `/workspace/stories/story_060/reports/quality_gate_result.yaml`.
- Regenerated the review bundle after the quality gate so final evidence is captured.
- Wrote finalize result data to `/workspace/stories/story_060/reports/finalize_story_result.yaml`.
- Updated `status.yaml` without committing, pushing, merging, deploying, or calling cloud models.

## Quality gate result

- Quality gate status: READY_FOR_REVIEW
- Test layer result: /workspace/stories/story_060/reports/test_layer_result.yaml
- Ready for review: True
- pytest in final review bundle passed: True
- Ruff in final review bundle passed: True

## Story status update

- status: ready_for_review
- ready_for_review: true

## Next recommended action

Send the story to a human or cloud reviewer.

Human or cloud review is still required before merge.

## Notes

- force: true
