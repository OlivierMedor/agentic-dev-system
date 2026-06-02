# STORY-025: Integrate remote dev validation status

## Goal

Update project-status and merge-readiness so they understand remote dev validation results.

## Why This Matters

The system can now create and record remote dev validation evidence, but the dashboard and merge-readiness gate should also surface that evidence clearly. This helps the human owner see whether code has only passed local/cloud review or has also been validated in a remote/dev-like environment.

## Acceptance Criteria

- project-status reads reports/remote_dev_validation_result.yaml when present.
- project-status displays remote dev validation status for each story.
- project-status includes remote dev validation status in reports/project_status_report.md.
- merge-readiness reads reports/remote_dev_validation_result.yaml when present.
- merge-readiness does not fail when remote dev validation is missing.
- merge-readiness treats DEV_VALIDATED as passing remote dev validation.
- merge-readiness treats DEV_VALIDATED_WITH_NOTES as passing with notes.
- merge-readiness treats DEV_FAILED as REQUEST_CHANGES.
- merge-readiness treats NOT_RUN as REQUEST_CHANGES when a result file exists.
- merge-readiness result includes remote_dev_validation_status.
- merge-readiness report explains whether remote dev validation was present, missing, passed, passed with notes, failed, or not run.
- README documents how remote dev validation relates to project-status and merge-readiness.
- Tests verify project-status and merge-readiness behavior for remote dev validation results.

## Not In Scope

- No actual deployment.
- No remote environment provisioning.
- No production release bundle.
- No GitHub environment deployment.
- No cloud API calls.
- No automatic merge.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- project-status shows remote dev status.
- merge-readiness handles remote dev validation status correctly.
- finalize-story marks this story ready for review.
