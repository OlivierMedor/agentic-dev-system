# Local Model Scorecard

Public benchmarks are useful, but they are not enough for assigning models to
agent roles. A leaderboard can show general coding or reasoning strength, while
this project needs to know how a model behaves on the actual work pattern:
story-scoped prompts, structured output, bounded safety rules, review evidence,
and low-risk local drafting.

The local model scorecard creates the same public-safe agent-style prompts every
time, runs them against one configured local OpenAI-compatible model when you ask
it to, saves the raw responses, and gives the human owner a manual scoring
template. It does not choose a winner automatically.

## Benchmark Vs Scorecard

Public benchmarks compare models on broad standardized tasks. They are good for
shortlisting models such as Qwen3 Coder, Devstral, Qwen2.5 Coder, and Gemma.

The local scorecard compares those models on this repository's workflow. It
checks whether the model follows role instructions, stays inside safety
boundaries, produces useful drafts, avoids unsupported claims, and returns
output a human can score consistently.

Use both:

- Benchmarks help decide which models are worth trying.
- The local scorecard helps decide which local model is fit for each agent role.

## Setup

Configure `.agentic/agent_runtime.yaml` with a local OpenAI-compatible endpoint.
LM Studio commonly serves `http://host.docker.internal:1234/v1`. Ollama commonly
serves `http://host.docker.internal:11434/v1`.

Set `local_model_runtime.enabled: true` only when the local server is running and
the target model is loaded.

## Commands

Create or refresh the scorecard prompts and scoring template:

```powershell
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-model scorecard-create --force
```

Run the prompts against the currently configured local model and save the
responses under `.agentic/local_model_scorecard/results/<model-label>/`:

```powershell
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-model scorecard-run --model-label qwen3-coder-30b
```

Create the manual report:

```powershell
docker compose run --rm dev agentic local-model scorecard-report
```

To compare Qwen3 Coder, Devstral, Qwen2.5 Coder, and Gemma, load one model at a
time in LM Studio or Ollama, update `local_model_runtime.model` if needed, then
run `scorecard-run` with a clear label:

```powershell
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-model scorecard-run --model-label qwen3-coder-30b
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-model scorecard-run --model-label devstral
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-model scorecard-run --model-label qwen2-5-coder
docker compose run --rm -e LOCAL_MODEL_API_KEY=lm-studio dev agentic local-model scorecard-run --model-label gemma
```

Then scaffold a local human scoring file from the saved responses:

```powershell
docker compose run --rm dev agentic local-model scorecard-scaffold-scores
```

Fill in `.agentic/local_model_scorecard/scorecard_scores.yaml` manually using
the saved responses. Leave incomplete rows blank until a human reviewer has
scored them. The scoring file is a local artifact and should not be committed by
default.

After scoring, generate advisory role recommendations:

```powershell
docker compose run --rm dev agentic local-model scorecard-recommend
```

The command writes generated reports under `reports/` and does not update
`.agentic/agent_runtime.yaml`.

## Scoring

Score each model and role manually across these dimensions:

- instruction_following
- correctness
- hallucination_control
- code_quality
- test_quality
- safety_compliance
- clarity
- speed_notes
- overall_fit_for_role
- reviewer_notes

Recommended role mapping is manual. The scoring scaffold uses these role ids:

- developer_agent
- test_agent
- docs_agent
- reviewer_agent
- maintenance_agent

`scorecard-recommend` ranks complete human-scored entries by
`overall_fit_for_role` first, then by `safety_compliance`,
`hallucination_control`, `correctness`, and `instruction_following`. It ignores
incomplete rows and reports them as warnings. Do not claim a winner until
comparable model runs have been scored by the human owner. A model can be good
for docs and weak for code review, or useful for test ideas but too loose for
implementation planning.

See `docs/local_model_role_assignment.md` for the full role assignment process.

## Safety Boundaries

Local models should start with low-risk tasks: documentation drafts, summaries,
test ideas, triage checklists, and review questions. Scorecard output is saved
only and must not be applied to source code automatically.

The scorecard:

- must not run shell commands from model output
- must not call cloud models
- must not commit, push, merge, deploy, or call GitHub APIs
- must not expose secrets
- must not approve high-risk changes automatically
- should prefer plain ASCII in prompt responses
- should avoid emoji/checkmark symbols because Windows and PowerShell logs may
  show encoding artifacts such as "âœ“"
- should use requested headings exactly
- should avoid wrapping entire responses in unnecessary nested Markdown code
  fences

For high-risk DeFi/security logic, cloud/human review is still needed even when
a local model performs well on the scorecard. Use local models to reduce cost and
speed up low-risk drafts; keep security-sensitive correctness, merge readiness,
and release decisions under human and configured review control.
