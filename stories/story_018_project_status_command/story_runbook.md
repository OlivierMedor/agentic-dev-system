# Story Runbook

## Story

`story_018_project_status_command` is prepared for agent execution.

## Assigned Agents

- Research Agent (`research_agent`): reports/research_report.md
- Planner Agent (`planner_agent`): reports/planner_report.md
- Developer Agent (`developer_agent`): reports/developer_report.md
- Test Agent (`test_agent`): reports/test_report.md
- Docs Agent (`docs_agent`): reports/docs_report.md
- Security/Quality Agent (`security_quality_agent`): reports/security_quality_report.md
- Local Reviewer Agent (`local_reviewer_agent`): reports/local_review_report.md

## Prompt Files

Prompt files are in `/app/stories/story_018_project_status_command/prompt_pack`.

## Recommended Execution Order

1. Research Agent
2. Planner Agent
3. Developer Agent
4. Test Agent
5. Docs Agent
6. Security/Quality Agent
7. Local Reviewer Agent

## After Agent Work

Run these commands after the assigned agents finish their work:

```powershell
docker compose run --rm dev pytest
docker compose run --rm dev ruff check .
docker compose run --rm dev agentic review-bundle --story story_018_project_status_command
docker compose run --rm dev agentic quality-gate --story story_018_project_status_command
```
