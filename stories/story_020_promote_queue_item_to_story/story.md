# STORY-020: Promote approved queue item to story

## Goal

Create a command that turns an approved improvement, maintenance, or feature queue item into a new story entry and story workspace.

## Why This Matters

Queue items should not become work automatically. Once the human owner and/or cloud model approve a queue item, the system needs a controlled way to promote it into the blueprint and generate a proper story workspace.

## Acceptance Criteria

- Add queue promote-to-story command.
- promote-to-story requires --item.
- promote-to-story defaults --project to the current working directory.
- promote-to-story finds queue items in improvement, maintenance, and feature queues.
- By default, only approved queue items can be promoted.
- The command accepts optional --allow-pending for manual override.
- The command creates a new story entry in blueprints/blueprint.yaml.
- The command generates a story id using the next available STORY number.
- The command generates a safe slug from the queue item title.
- The command creates a story workspace using existing story generation logic.
- The generated story includes acceptance criteria, not-in-scope, definition of done, test plan, and monitoring plan.
- The command writes a promotion report.
- The command records promoted_story_id and promoted_story_slug back into the queue item.
- The command can optionally move the queue item to closed or parked after promotion.
- Tests verify promotion behavior for improvement, maintenance, and feature queue items.
- README documents the promote-to-story workflow.

## Not In Scope

- No automatic cloud model approval.
- No automatic story execution.
- No automatic merge.
- No internet research agent yet.
- No Maintenance Monitor Agent yet.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- promote-to-story creates a valid story from an approved queue item.
- finalize-story marks this story ready for review.
