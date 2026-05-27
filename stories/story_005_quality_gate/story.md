# STORY-005: Add quality gate command

## Goal

Create a command that checks whether a story is ready for human/cloud review.

## Why This Matters

The system needs a clear pass/fail gate before code is reviewed or merged.

## Acceptance Criteria

- Add a quality gate command.
- Check pytest result.
- Check ruff result.
- Check that a review bundle exists.
- Check that required story reports exist.

## Not In Scope

- No deployment validation yet.
- No production release bundle yet.

## Definition of Done

- pytest passes.
- ruff passes.
- quality gate produces READY_FOR_REVIEW or REQUEST_CHANGES.
