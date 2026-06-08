# Local Model Scorecard

This folder holds public-safe prompts and the manual scoring template for comparing local OpenAI-compatible models on the same bounded agent-style tasks.

Runtime model responses belong under `results/` and must remain untracked.
Human scores belong in `scorecard_scores.yaml` and must remain untracked by
default. Generated role recommendation reports belong under `reports/` and must
also remain untracked by default.

Safety boundaries:

- Scorecard output is saved only.
- Model output must not be applied to source files automatically.
- Shell commands from model output must not be executed.
- Cloud models, GitHub APIs, commit, push, merge, and deploy actions are not used.
- Secrets must not be included in prompts or reports.
- Prompt responses should prefer plain ASCII.
- Avoid emoji/checkmark symbols and unnecessary whole-response code fences.
