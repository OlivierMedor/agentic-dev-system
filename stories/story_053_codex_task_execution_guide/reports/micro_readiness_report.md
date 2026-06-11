# Micro Readiness Report

## Story

story_053_codex_task_execution_guide

## Plain-English Explanation

Micro readiness asks whether each assigned agent can receive a short, clear micro prompt for its own responsibility. The whole story does not need to fit in one tiny prompt, but each agent task should be small enough to summarize without dragging in unrelated context.

## Story Sizing Verdict

TOO_LARGE_FOR_MICRO

## Per-Agent Micro Prompt Estimate

### research_agent

- Estimated characters: 1003
- Target characters: 2000
- Fits target: yes
- Expected output: reports/research_report.md
- Responsibility: Research story scope, risks, best practices, and useful references.
- Source files: story.md, agent_plan.yaml

### planner_agent

- Estimated characters: 988
- Target characters: 2000
- Fits target: yes
- Expected output: reports/planner_report.md
- Responsibility: Create a practical implementation plan for this story.
- Source files: story.md, agent_plan.yaml

### developer_agent

- Estimated characters: 998
- Target characters: 2000
- Fits target: yes
- Expected output: reports/developer_report.md
- Responsibility: Implement only the approved story scope. Do not write tests.
- Source files: story.md, agent_plan.yaml

### test_agent

- Estimated characters: 991
- Target characters: 2000
- Fits target: yes
- Expected output: reports/test_report.md
- Responsibility: Write independent tests based on the story acceptance criteria.
- Source files: story.md, agent_plan.yaml

### docs_agent

- Estimated characters: 971
- Target characters: 2000
- Fits target: yes
- Expected output: reports/docs_report.md
- Responsibility: Update documentation related to this story.
- Source files: story.md, agent_plan.yaml

### security_quality_agent

- Estimated characters: 1020
- Target characters: 2000
- Fits target: yes
- Expected output: reports/security_quality_report.md
- Responsibility: Check for secrets, unsafe behavior, bad patterns, and quality risks.
- Source files: story.md, agent_plan.yaml

### local_reviewer_agent

- Estimated characters: 1016
- Target characters: 2000
- Fits target: yes
- Expected output: reports/local_review_report.md
- Responsibility: Review all work and decide whether it is ready for cloud/human review.
- Source files: story.md, agent_plan.yaml

## Warnings

- None

## Failed Checks

- More than 15 acceptance criteria usually means the story is too large.
- Story appears to touch many unrelated modules or workflow areas.

## Recommended Action

Split or narrow the story before relying on agent-specific micro prompts.

## Split Examples

- Split by workflow area, such as CLI behavior first and documentation updates second.
- Split by agent responsibility when one agent needs a much larger prompt than the others.
- Split broad acceptance criteria into separate stories with their own not-in-scope boundaries.
- Move exploratory cleanup or unrelated module changes into a later story.
