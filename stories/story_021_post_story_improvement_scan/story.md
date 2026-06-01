# STORY-021: Add post-story improvement scan

## Goal

Create commands that let the system generate an improvement scan packet for a completed story and record structured improvement suggestions into the improvement queue.

## Why This Matters

After a story is completed, the Research Agent or cloud model should be able to suggest focused improvements within that story's scope. These suggestions should go into the improvement queue for human/cloud review instead of expanding the current story.

## Acceptance Criteria

- Add improvement-scan create command.
- Add improvement-scan record command.
- improvement-scan create requires --story.
- improvement-scan create defaults --project to the current working directory.
- improvement-scan create validates that the story folder exists.
- improvement-scan create writes stories/<story>/improvements/improvement_scan_packet.md.
- improvement-scan create writes stories/<story>/improvements/improvement_suggestions_template.yaml.
- The packet includes story content, reports, test layer result, finalize result, local review report, and review bundle handoff when present.
- The packet instructs the reviewer to suggest improvements only within the completed story's scope.
- The packet instructs the reviewer not to propose unrelated features.
- improvement-scan record requires --story and --suggestions-file.
- improvement-scan record validates suggestion YAML.
- improvement-scan record creates improvement queue items under .agentic/improvement_queue/pending.
- Each recorded improvement item includes source_story, title, category, priority, details, expected_benefit, suggested_acceptance_criteria, and next_action.
- improvement-scan record writes stories/<story>/improvements/improvement_record_report.md.
- Tests verify packet creation, template creation, suggestion validation, and queue item creation.
- README documents the post-story improvement workflow.

## Not In Scope

- No automatic cloud model call.
- No internet research yet.
- No automatic story creation from suggestions.
- No automatic implementation of improvements.
- No LangGraph yet.
- No web dashboard.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- improvement-scan create works.
- improvement-scan record works with a sample suggestions file.
- finalize-story marks this story ready for review.
