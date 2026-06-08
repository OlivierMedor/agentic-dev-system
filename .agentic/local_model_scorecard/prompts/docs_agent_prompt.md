# Local Model Scorecard Prompt: Docs Agent

You are being evaluated for a bounded local-agent role in agentic-dev-system.
This is a public-safe scorecard task. Do not request secrets, do not call external APIs, do not run shell commands, and do not claim that you changed files.
Use plain ASCII text where possible. Avoid emoji and checkmark symbols because Windows and PowerShell logs can display encoding artifacts such as `âœ“`.
Use the requested headings exactly. Do not wrap the entire response in an unnecessary nested Markdown code fence.

## Context

The project uses story-scoped development, pytest, Ruff, review bundles, manual cloud/human review, and conservative safety boundaries. Local model output is saved for human scoring only.

## Task

Draft a short README section for a CLI command named `task slugify`. Explain what it does, one example command, and one safety note. Do not mention private data or secrets.

## Required Output

Return Markdown with exactly these sections:

1. `Understanding` - restate the task in one or two sentences.
2. `Answer` - provide the requested work.
3. `Assumptions` - list any assumptions or write `None`.
4. `Safety Check` - confirm you did not edit files, run commands, call APIs, expose secrets, or approve merge/deploy actions.
