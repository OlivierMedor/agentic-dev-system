# Micro Readiness

Micro readiness checks whether a story is focused enough for agent-specific
micro prompts.

Micro mode is the smallest local-agent prompt style. It gives a local model only
the story slug, one agent's responsibility, the story goal, the top acceptance
criteria, expected output, safety rules, and final-visible-answer instructions.
It is useful when a local reasoning model can handle small direct prompts but
struggles with long story context.

Small local-model prompts help because they reduce distraction, lower the chance
of truncated output, and make it easier for a human reviewer to see what the
model was asked to do. Limiting context is not always bad. For micro work, the
point is to give the model the exact task it owns, not the whole repository or
every story artifact.

## Story Versus Agent Task

The whole story does not need to fit inside one micro prompt. A good story can
still justify the full workflow: research, planning, development, testing, docs,
security/quality review, and local review.

The micro-readiness question is narrower:

```text
Can each assigned agent's responsibility be summarized clearly in a short prompt?
```

If the answer is no, the story may be too broad, too vague, or too large for
agent-specific micro-mode tasks.

## Run The Check

The normal prepare workflow now runs micro-readiness automatically:

```powershell
docker compose run --rm dev agentic workflow-run --story STORY_SLUG --phase prepare --execute
```

That prepare phase runs `prepare-story`, `micro-readiness`, and
`workflow-preview`. Use the standalone command when you want to refresh only the
sizing report:

```powershell
docker compose run --rm dev agentic micro-readiness --story STORY_SLUG
```

Optional arguments:

```powershell
docker compose run --rm dev agentic micro-readiness --story STORY_SLUG --target-chars 1800
docker compose run --rm dev agentic micro-readiness --project C:\path\to\project --story STORY_SLUG
```

The command reads `story.md`, `agent_plan.yaml` when present, and files in
`instructions/` when present. It does not call local models, cloud models, or
agents, and it does not apply model output to source files.

It writes:

- `stories/STORY_SLUG/reports/micro_readiness_result.yaml`
- `stories/STORY_SLUG/reports/micro_readiness_report.md`

## Statuses

`READY_FOR_MICRO` means the story has the required shape, no sizing warnings, and
all assigned agent prompt estimates fit the target.

`MICRO_READY_WITH_WARNINGS` means the story can probably proceed, but the report
found issues to review, such as a missing `agent_plan.yaml`, missing
not-in-scope boundaries, vague goal wording, or one oversized agent estimate.

`TOO_LARGE_FOR_MICRO` means the story likely needs to be split or narrowed before
micro-mode work is useful. Common causes are more than 15 acceptance criteria,
several oversized agent estimates, many unrelated modules, or several signs that
the story combines separate concerns.

`NEEDS_REVIEW` means required planning information is missing or invalid, such as
a missing `story.md` or invalid `agent_plan.yaml`.

## What It Checks

The check looks at:

- story goal length and vague wording
- acceptance criteria count
- not-in-scope clarity
- Definition of Done clarity
- whether `agent_plan.yaml` exists
- whether each assigned agent has a responsibility
- estimated micro prompt size per assigned agent
- signs the story touches many unrelated modules
- signs the story should be split

The result is advisory. Human judgment still decides whether the story is worth
running through the full workflow.

Warnings are guidance, not automatic failure. A story with
`MICRO_READY_WITH_WARNINGS` can continue through the normal workflow, but the
operator should read the warning text before choosing a local prompt mode or
runtime.

## When To Split A Story

Split or narrow the story when `TOO_LARGE_FOR_MICRO` points to several
oversized agent estimates, too many acceptance criteria, broad module reach, or
multiple unrelated workflow areas. A good split gives each new story a single
clear goal, explicit not-in-scope boundaries, and agent responsibilities that
can be summarized without pulling in unrelated context.

Do not split just because one warning exists. Use the warning as a prompt to
check whether the story is still cohesive.

## Micro Mode Versus Stronger Runtime

Use micro mode when each agent has a focused responsibility and a short prompt
can state the goal, top acceptance criteria, expected output, and safety rules.
This is often the best first choice for smaller local models that struggle with
long prompt packs.

Use slim mode or a stronger configured agent runtime when the story is cohesive
but the agent needs more context than micro mode can provide. If the story is
not cohesive, prefer splitting it before relying on a stronger model.
