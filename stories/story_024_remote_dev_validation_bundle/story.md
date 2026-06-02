# STORY-024: Add remote dev validation bundle

## Goal

Create commands that prepare remote-dev validation instructions and record remote-dev validation results for a story.

## Why This Matters

Local tests and code review are not the same as proving the system works in a remote/dev-like environment. The system needs a structured way to collect deployment URL, logs, smoke test results, integration test results, environment checks, and validation outcomes before a human decides whether work is safe to move forward.

## Acceptance Criteria

- Add remote-dev-packet command.
- Add record-remote-dev command.
- remote-dev-packet requires --story.
- remote-dev-packet defaults --project to the current working directory.
- remote-dev-packet validates that the story folder exists.
- remote-dev-packet creates stories/<story>/remote_dev_validation/remote_dev_packet.md.
- remote-dev-packet creates stories/<story>/remote_dev_validation/remote_dev_result_template.yaml.
- The packet includes story content, test plan, monitoring plan, quality gate result, finalize result, cloud review result if present, and merge readiness result if present.
- The packet explains what remote dev evidence should be collected.
- The packet includes smoke test, integration test, log review, environment variable checklist, rollback notes, and known-risk sections.
- record-remote-dev requires --story and --result-file.
- record-remote-dev validates the result file.
- Accepted validation statuses are DEV_VALIDATED, DEV_VALIDATED_WITH_NOTES, DEV_FAILED, and NOT_RUN.
- record-remote-dev writes reports/remote_dev_validation_result.yaml.
- record-remote-dev writes reports/remote_dev_validation_report.md.
- DEV_VALIDATED updates status.yaml to remote_dev_validated.
- DEV_VALIDATED_WITH_NOTES updates status.yaml to remote_dev_validated_with_notes.
- DEV_FAILED updates status.yaml to remote_dev_failed.
- NOT_RUN updates status.yaml to remote_dev_not_run.
- record-remote-dev preserves story_id in status.yaml.
- The command does not deploy, commit, push, merge, or call cloud models.
- Runtime remote_dev_validation packet files are ignored by Git and blocked by artifact policy.
- Tests verify packet creation, template creation, result validation, status updates, and artifact policy behavior.
- README documents the remote dev validation workflow.

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
- remote-dev-packet works.
- record-remote-dev works with sample validation files.
- finalize-story marks this story ready for review.
