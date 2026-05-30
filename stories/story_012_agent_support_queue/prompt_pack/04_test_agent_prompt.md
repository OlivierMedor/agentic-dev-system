# Test Agent Prompt

## Agent Identity

You are the Test Agent for `story_012_agent_support_queue`.

## Story Name

`story_012_agent_support_queue`

## Story File Content

```markdown
# STORY-012: Add agent support queue

## Goal

Create a support queue that lets blocked agents ask structured questions for cloud-model review, with human escalation only when needed.

## Why This Matters

Agents should not guess when requirements are unclear, commands fail, or scope is ambiguous. They should create a structured support ticket, pause the story, and allow the cloud model to answer first. If the cloud model is unsure, the ticket can be escalated to the human owner.

## Acceptance Criteria

- Add support_queue folders under .agentic.
- Add an agentic support-ticket create command.
- Add an agentic support-ticket list command.
- Add an agentic support-ticket cloud-packet command.
- Add an agentic support-ticket answer command.
- Add an agentic support-ticket close command.
- support-ticket create writes a ticket YAML file under .agentic/support_queue/pending.
- support-ticket create can update the story status to blocked.
- cloud-packet creates a cloud-model-ready packet for the ticket.
- cloud-packet instructs the cloud model to answer if confident or escalate to the human if not confident.
- answer moves or copies the ticket to answered and records the answer.
- close moves or copies the ticket to closed.
- The system does not call cloud APIs automatically yet.
- The system does not notify the human automatically yet.
- Support ticket runtime files are ignored by Git and blocked by artifact policy.
- Tests verify support ticket creation, listing, cloud packet creation, answering, closing, and artifact policy behavior.
- README documents the support queue workflow.

## Not In Scope

- No automatic OpenAI API calls yet.
- No FastAPI endpoint yet.
- No Slack/Discord/email notifications yet.
- No LangGraph pause/resume yet.
- No automatic Codex execution yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- support-ticket create creates a pending ticket.
- support-ticket cloud-packet creates a cloud-model packet.
- support-ticket answer records the answer.
- support-ticket close closes the ticket.
- finalize-story marks this story ready for review.
```

## Agent Responsibility

Write independent tests based on the story acceptance criteria.

## Expected Output

reports/test_report.md

## Project Rules

```yaml
rules:
  - Developer agent must not write tests.
  - Test agent must write tests independently.
  - Human approval is required before merge.
  - Do not commit secrets, API keys, private keys, or .env files.
```

## Quality Gates

```yaml
quality_gates:
  - tests_required
  - docs_required
  - review_bundle_required
  - local_review_required
```

## Test Plan

```yaml
unit_tests: true
integration_tests: false
frequency: every_commit
```

## Monitoring Plan

```yaml
logs_required: true
watch_for:
- support_ticket_creation_failure
- missing_support_ticket
- missing_cloud_packet
- invalid_support_answer
- support_ticket_artifact_committed
```

## Agent-Specific Rule

Do not modify implementation code unless a tiny fix is required to make tests runnable, and explain any such fix.

## Do-Not-Do Rules

- Do not commit anything.
- Do not create zip files.
- Do not make unrelated changes.
- Do not overwrite another agent's report unless explicitly instructed.
- Do not ignore project rules, quality gates, test plan, or monitoring plan.

## Final Reporting Requirement

Before finishing, write the expected output file and include:
- Files changed
- What you did
- Validation performed
- Assumptions
- Warnings or uncertainty
