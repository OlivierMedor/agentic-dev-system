# STORY-022: Add reactive maintenance scan

## Goal

Create commands that generate a maintenance scan packet from story/test/log evidence and record structured maintenance findings into the maintenance queue.

## Why This Matters

When tests, logs, CI, remote dev, or external integrations fail, agents should not guess or silently change code. The system should create a structured maintenance ticket that can be reviewed by the cloud model and human owner before becoming repair work.

## Acceptance Criteria

- Add maintenance-scan create command.
- Add maintenance-scan record command.
- maintenance-scan create requires --story.
- maintenance-scan create defaults --project to the current working directory.
- maintenance-scan create creates stories/<story>/maintenance/maintenance_scan_packet.md.
- maintenance-scan create creates stories/<story>/maintenance/maintenance_findings_template.yaml.
- maintenance-scan packet includes story content, monitoring plan, test plan, review bundle handoff, pytest output, ruff output, quality gate result, finalize result, and optional log files when present.
- maintenance-scan packet instructs the reviewer to identify broken behavior, regressions, or external dependency failures.
- maintenance-scan packet instructs the reviewer not to implement fixes automatically.
- maintenance-scan record requires --story and --findings-file.
- maintenance-scan record validates findings YAML.
- maintenance-scan record creates maintenance queue items under .agentic/maintenance_queue/pending.
- Each maintenance item includes source_story, severity, source_type, problem, evidence, suspected_cause, recommended_action, suggested_acceptance_criteria, and next_action.
- Tests verify packet creation, findings validation, and maintenance queue item creation.
- README documents the reactive maintenance workflow.

## Not In Scope

- No automatic repair.
- No automatic cloud model call.
- No internet lookup yet.
- No scheduled log monitor yet.
- No remote dev validation environment yet.
- No production incident workflow yet.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- maintenance-scan create works.
- maintenance-scan record works with a sample findings file.
- finalize-story marks this story ready for review.
