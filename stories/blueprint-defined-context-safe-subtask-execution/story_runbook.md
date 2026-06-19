# Story Runbook

## Story

`blueprint-defined-context-safe-subtask-execution` is prepared for agent execution.

## Assigned Agents

- Developer Agent (`developer_agent`): reports/developer_report.md
- Test Agent (`test_agent`): reports/test_report.md
- Docs Agent (`docs_agent`): reports/docs_report.md
- Security/Quality Agent (`security_quality_agent`): reports/security_quality_report.md
- Local Reviewer Agent (`local_reviewer_agent`): reports/local_review_report.md

## Prompt Files

Prompt files are in `/app/stories/blueprint-defined-context-safe-subtask-execution/prompt_pack`.

## Recommended Execution Order

1. Developer Agent
2. Test Agent
3. Docs Agent
4. Security/Quality Agent
5. Local Reviewer Agent

## After Agent Work

Run these commands after the assigned agents finish their work:

```powershell
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic review-bundle --story blueprint-defined-context-safe-subtask-execution
docker compose run --rm dev agentic quality-gate --story blueprint-defined-context-safe-subtask-execution
```
