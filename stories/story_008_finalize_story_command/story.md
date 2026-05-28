# STORY-008: Add finalize-story command

## Goal

Create a command that finalizes a story by generating a review bundle, running the quality gate, regenerating the review bundle, writing a finalize report, and updating story status.

## Why This Matters

The system should reduce manual final review steps after agent work is completed. One command should collect evidence, run the quality gate, record the result, and mark the story ready for human/cloud review or request changes.

## Acceptance Criteria

- Add a finalize-story command.
- The command requires --story.
- The command defaults --project to the current working directory.
- The command accepts optional --force.
- The command validates that the story folder exists.
- The command creates or refreshes the review bundle.
- The command runs the quality gate.
- The command regenerates the review bundle after the quality gate so final evidence is captured.
- The command writes reports/finalize_story_report.md.
- The command writes reports/finalize_story_result.yaml.
- If the quality gate returns READY_FOR_REVIEW, the command updates status.yaml to ready_for_review true.
- If the quality gate returns REQUEST_CHANGES, the command updates status.yaml to request_changes and ready_for_review false.
- The command does not commit, push, merge, deploy, or call cloud models.

## Not In Scope

- No automatic Git commits.
- No automatic GitHub PR creation.
- No cloud model review yet.
- No remote dev validation yet.
- No production deployment.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- finalize-story creates review bundle evidence.
- finalize-story creates quality gate outputs.
- finalize-story creates finalize report files.
- finalize-story updates status.yaml safely.
