# Story Sizing

User stories should be narrow enough to have clear acceptance criteria and a
focused code change, but large enough to justify the full agent workflow:
Research, Planner, Developer, Test, Docs, Security/Quality, and Reviewer.

If only one agent has meaningful work, the story is probably too small. If the
story touches many unrelated features or modules, it is probably too large.

## Good Story Shape

A useful story has:

- one clear goal
- acceptance criteria that describe observable outcomes
- explicit not-in-scope boundaries
- a Definition of Done that names the required checks and evidence
- enough work for the standard agents to contribute meaningfully

The story should be narrow enough that a reviewer can understand what changed
without reconstructing multiple unrelated initiatives.

## Full Workflow Justification

The full workflow is intentionally heavier than a quick one-file edit. A story
should justify research, planning, development, testing, documentation,
security/quality review, and local review.

That does not mean every agent writes a large report. It means each agent has a
real responsibility that improves the confidence of the story.

## Micro-Summarizable Agent Tasks

Micro mode is about each agent's assignment, not the whole story. A story is a
better fit for local-model micro prompts when each agent task can be summarized
with:

- story slug
- agent id
- agent responsibility
- story goal
- top acceptance criteria
- expected output
- safety rules
- final-visible-answer instruction

If an assigned agent needs a long prompt full of unrelated context to know what
to do, the story is probably too broad for micro-mode work.

Run:

```powershell
docker compose run --rm dev agentic micro-readiness --story STORY_SLUG
```

See `docs/micro_readiness.md` for status meanings and report outputs.

## When To Split

Split the story when:

- the acceptance criteria mix separate features or workflows
- the story needs changes across many unrelated modules
- not-in-scope boundaries are hard to write
- several agents cannot receive short, clear micro prompts
- the story goal uses vague wording such as broad cleanup or general improvement

If a story cannot be summarized per agent, split it before relying on micro-mode
local-agent tasks.
