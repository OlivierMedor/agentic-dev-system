# STORY-019: Add queue management commands

## Goal

Create commands for managing improvement, maintenance, and feature queue items.

## Why This Matters

The system needs a structured way to capture future improvements, maintenance issues, and new feature ideas without expanding the current story scope. These queues let agents propose work, while the human owner and cloud model decide what becomes a future story.

## Acceptance Criteria

- Add queue create command.
- Add queue list command.
- Add queue show command.
- Add queue set-status command.
- Supported queue types are improvement, maintenance, and feature.
- queue create writes a structured YAML item into the selected queue pending folder.
- queue items include id, queue_type, title, source_story, category, priority, status, details, created_at, and next_action.
- improvement items use prefix IMP.
- maintenance items use prefix MAINT.
- feature items use prefix FEATURE.
- queue list shows pending, approved, rejected, parked, and closed items.
- queue show prints one item clearly.
- queue set-status moves an item between pending, approved, rejected, parked, and closed.
- queue set-status records a decision note.
- project-status includes queue counts for improvement, maintenance, and feature queues.
- README documents the queue workflow.
- Tests verify queue creation, listing, showing, status changes, invalid queue types, and project-status queue counts.

## Not In Scope

- No automatic story creation from approved queue items yet.
- No internet research agent yet.
- No automatic Maintenance Monitor Agent yet.
- No cloud API calls.
- No LangGraph yet.
- No web dashboard.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- queue commands work on tmp_path in tests.
- project-status shows queue counts.
- finalize-story marks this story ready for review.
