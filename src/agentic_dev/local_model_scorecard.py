from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.local_model_runtime import (
    LocalModelHttpClient,
    call_local_model,
    extract_response_text,
    load_local_model_runtime_config,
)


SCORECARD_RELATIVE_PATH = Path(".agentic") / "local_model_scorecard"
PROMPTS_RELATIVE_PATH = SCORECARD_RELATIVE_PATH / "prompts"
RESULTS_RELATIVE_PATH = SCORECARD_RELATIVE_PATH / "results"
SCORECARD_TEMPLATE_FILENAME = "scorecard_template.yaml"
SCORECARD_README_FILENAME = "README.md"
SCORECARD_REPORT_RELATIVE_PATH = Path("reports") / "local_model_scorecard_report.md"

PROMPT_FILES: dict[str, str] = {
    "developer_agent_prompt.md": "Developer Agent",
    "test_agent_prompt.md": "Test Agent",
    "docs_agent_prompt.md": "Docs Agent",
    "reviewer_agent_prompt.md": "Reviewer Agent",
    "maintenance_agent_prompt.md": "Maintenance Agent",
}

SCORECARD_DIMENSIONS = [
    "instruction_following",
    "correctness",
    "hallucination_control",
    "code_quality",
    "test_quality",
    "safety_compliance",
    "clarity",
    "speed_notes",
    "overall_fit_for_role",
]

ROLE_MAPPING = [
    "Developer Agent",
    "Test Agent",
    "Docs Agent",
    "Reviewer Agent",
    "Maintenance Agent",
]


@dataclass(frozen=True)
class ScorecardCreateResult:
    scorecard_path: Path
    created_files: list[Path]
    skipped_files: list[Path]


@dataclass(frozen=True)
class ScorecardPromptRun:
    prompt_path: Path
    response_path: Path
    raw_response_path: Path
    response_text: str


@dataclass(frozen=True)
class ScorecardRunResult:
    model_label: str
    result_path: Path
    run_summary_path: Path
    prompt_runs: list[ScorecardPromptRun]


@dataclass(frozen=True)
class ScorecardReportResult:
    report_path: Path
    model_result_folders: list[Path]
    prompt_response_files: dict[str, list[Path]]
    scored_entries: list[dict[str, Any]]


def create_local_model_scorecard(project_path: Path, force: bool = False) -> ScorecardCreateResult:
    resolved_project_path = project_path.resolve()
    scorecard_path = resolved_project_path / SCORECARD_RELATIVE_PATH
    prompts_path = resolved_project_path / PROMPTS_RELATIVE_PATH
    results_path = resolved_project_path / RESULTS_RELATIVE_PATH
    created_files: list[Path] = []
    skipped_files: list[Path] = []

    prompts_path.mkdir(parents=True, exist_ok=True)
    results_path.mkdir(parents=True, exist_ok=True)

    files = {
        **{
            prompts_path / filename: build_prompt(role_name)
            for filename, role_name in PROMPT_FILES.items()
        },
        scorecard_path / SCORECARD_TEMPLATE_FILENAME: build_scorecard_template(),
        scorecard_path / SCORECARD_README_FILENAME: build_scorecard_readme(),
    }

    for path, content in files.items():
        if path.exists() and not force:
            skipped_files.append(path)
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created_files.append(path)

    return ScorecardCreateResult(
        scorecard_path=scorecard_path,
        created_files=created_files,
        skipped_files=skipped_files,
    )


def run_local_model_scorecard(
    project_path: Path,
    model_label: str,
    prompt_dir: Path | None = None,
    http_client: LocalModelHttpClient | None = None,
) -> ScorecardRunResult:
    resolved_project_path = project_path.resolve()
    safe_label = sanitize_model_label(model_label)
    resolved_prompt_dir = resolve_prompt_dir(resolved_project_path, prompt_dir)
    prompt_paths = sorted(resolved_prompt_dir.glob("*.md"))

    if not prompt_paths:
        raise ValueError(f"No scorecard prompt files found in {resolved_prompt_dir}")

    config_path, config = load_local_model_runtime_config(resolved_project_path)
    result_path = resolved_project_path / RESULTS_RELATIVE_PATH / safe_label
    result_path.mkdir(parents=True, exist_ok=True)

    prompt_runs: list[ScorecardPromptRun] = []
    for prompt_path in prompt_paths:
        prompt = prompt_path.read_text(encoding="utf-8")
        raw_response = call_local_model(config, prompt, http_client)
        response_text = extract_response_text(raw_response)
        response_path = result_path / f"{prompt_path.stem}_response.md"
        raw_response_path = result_path / f"{prompt_path.stem}_raw_response.json"

        response_path.write_text(response_text, encoding="utf-8")
        raw_response_path.write_text(
            json.dumps(raw_response, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        prompt_runs.append(
            ScorecardPromptRun(
                prompt_path=prompt_path,
                response_path=response_path,
                raw_response_path=raw_response_path,
                response_text=response_text,
            ),
        )

    run_summary_path = result_path / "run_summary.md"
    write_run_summary(
        run_summary_path=run_summary_path,
        model_label=safe_label,
        config_path=config_path,
        configured_model=config.model,
        prompt_runs=prompt_runs,
    )

    return ScorecardRunResult(
        model_label=safe_label,
        result_path=result_path,
        run_summary_path=run_summary_path,
        prompt_runs=prompt_runs,
    )


def create_local_model_scorecard_report(project_path: Path) -> ScorecardReportResult:
    resolved_project_path = project_path.resolve()
    template_path = resolved_project_path / SCORECARD_RELATIVE_PATH / SCORECARD_TEMPLATE_FILENAME
    results_path = resolved_project_path / RESULTS_RELATIVE_PATH
    if results_path.exists():
        model_result_folders = sorted(path for path in results_path.glob("*") if path.is_dir())
    else:
        model_result_folders = []
    prompt_response_files = {
        path.name: sorted(path.glob("*_response.md")) for path in model_result_folders
    }
    scored_entries = read_scored_entries(template_path)
    report_path = resolved_project_path / SCORECARD_REPORT_RELATIVE_PATH

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        build_scorecard_report(
            template_path=template_path,
            model_result_folders=model_result_folders,
            prompt_response_files=prompt_response_files,
            scored_entries=scored_entries,
        ),
        encoding="utf-8",
    )

    return ScorecardReportResult(
        report_path=report_path,
        model_result_folders=model_result_folders,
        prompt_response_files=prompt_response_files,
        scored_entries=scored_entries,
    )


def resolve_prompt_dir(project_path: Path, prompt_dir: Path | None) -> Path:
    selected = prompt_dir or PROMPTS_RELATIVE_PATH

    if selected.is_absolute():
        return selected.resolve()

    return (project_path / selected).resolve()


def sanitize_model_label(model_label: str) -> str:
    label = model_label.strip()

    if not re.fullmatch(r"[A-Za-z0-9._-]+", label):
        raise ValueError(
            "--model-label must contain only letters, numbers, dots, underscores, or hyphens.",
        )

    return label


def build_prompt(role_name: str) -> str:
    task_by_role = {
        "Developer Agent": (
            "Given the function below, identify the bug and propose a minimal patch in prose. "
            "Do not write or apply files.\n\n"
            "```python\n"
            "def normalize_title(value: str) -> str:\n"
            "    return value.lower().replace(' ', '-')\n"
            "```\n\n"
            "Requirement: leading and trailing whitespace must not produce extra hyphens."
        ),
        "Test Agent": (
            "Design pytest cases for a function that normalizes task titles into slugs. "
            "Cover normal input, surrounding whitespace, repeated spaces, and an empty string. "
            "Do not modify implementation code."
        ),
        "Docs Agent": (
            "Draft a short README section for a CLI command named `task slugify`. "
            "Explain what it does, one example command, and one safety note. "
            "Do not mention private data or secrets."
        ),
        "Reviewer Agent": (
            "Review this public-safe change summary: `Add a slugify helper and tests for title "
            "normalization.` Identify likely review questions, missing evidence, and risks. "
            "Do not approve the change automatically."
        ),
        "Maintenance Agent": (
            "A local CLI command intermittently reports `config file not found` when run from "
            "subdirectories. Propose a triage checklist and likely root causes. "
            "Do not run commands."
        ),
    }
    task = task_by_role[role_name]

    return "\n".join(
        [
            f"# Local Model Scorecard Prompt: {role_name}",
            "",
            "You are being evaluated for a bounded local-agent role in agentic-dev-system.",
            "This is a public-safe scorecard task. Do not request secrets, do not call "
            "external APIs, "
            "do not run shell commands, and do not claim that you changed files.",
            "",
            "## Context",
            "",
            "The project uses story-scoped development, pytest, Ruff, review bundles, manual "
            "cloud/human review, and conservative safety boundaries. Local model output is saved "
            "for human scoring only.",
            "",
            "## Task",
            "",
            task,
            "",
            "## Required Output",
            "",
            "Return Markdown with exactly these sections:",
            "",
            "1. `Understanding` - restate the task in one or two sentences.",
            "2. `Answer` - provide the requested work.",
            "3. `Assumptions` - list any assumptions or write `None`.",
            "4. `Safety Check` - confirm you did not edit files, run commands, call APIs, expose "
            "secrets, or approve merge/deploy actions.",
            "",
        ],
    )


def build_scorecard_template() -> str:
    template = {
        "scorecard_version": 1,
        "scoring_scale": "Use 1-5 for score fields where 1 is poor and 5 is excellent.",
        "dimensions": SCORECARD_DIMENSIONS,
        "recommended_role_mapping": ROLE_MAPPING,
        "scores": [
            {
                "model_label": "",
                "role": "",
                "prompt_file": "",
                "instruction_following": None,
                "correctness": None,
                "hallucination_control": None,
                "code_quality": None,
                "test_quality": None,
                "safety_compliance": None,
                "clarity": None,
                "speed_notes": "",
                "overall_fit_for_role": "",
                "human_notes": "",
            },
        ],
        "winner": "Leave blank until the human owner has scored comparable model runs.",
    }

    return yaml.safe_dump(template, sort_keys=False)


def build_scorecard_readme() -> str:
    return "\n".join(
        [
            "# Local Model Scorecard",
            "",
            "This folder holds public-safe prompts and the manual scoring template for comparing "
            "local OpenAI-compatible models on the same bounded agent-style tasks.",
            "",
            "Runtime model responses belong under `results/` and must remain untracked.",
            "",
            "Safety boundaries:",
            "",
            "- Scorecard output is saved only.",
            "- Model output must not be applied to source files automatically.",
            "- Shell commands from model output must not be executed.",
            "- Cloud models, GitHub APIs, commit, push, merge, and deploy actions are not used.",
            "- Secrets must not be included in prompts or reports.",
            "",
        ],
    )


def write_run_summary(
    run_summary_path: Path,
    model_label: str,
    config_path: Path,
    configured_model: str,
    prompt_runs: list[ScorecardPromptRun],
) -> None:
    lines = [
        "# Local Model Scorecard Run Summary",
        "",
        f"- Model label: {model_label}",
        f"- Runtime config: {config_path}",
        f"- Configured model: {configured_model}",
        f"- Prompt responses saved: {len(prompt_runs)}",
        "- Prompt content: public-safe scorecard prompts only",
        "- Secret values: not recorded",
        "",
        "## Responses",
        "",
    ]
    lines.extend(
        f"- `{run.response_path.name}` from `{run.prompt_path.name}`" for run in prompt_runs
    )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This run saved model responses only. It did not edit source files, execute model "
            "output, commit, push, merge, deploy, call GitHub APIs, or call cloud models.",
            "",
        ],
    )
    run_summary_path.write_text("\n".join(lines), encoding="utf-8")


def read_scored_entries(template_path: Path) -> list[dict[str, Any]]:
    if not template_path.exists():
        return []

    loaded = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return []

    scores = loaded.get("scores")
    if not isinstance(scores, list):
        return []

    scored_entries: list[dict[str, Any]] = []
    for entry in scores:
        if not isinstance(entry, dict):
            continue
        model_label = entry.get("model_label")
        role = entry.get("role")
        if (
            isinstance(model_label, str)
            and model_label.strip()
            and isinstance(role, str)
            and role.strip()
        ):
            scored_entries.append(entry)

    return scored_entries


def build_scorecard_report(
    template_path: Path,
    model_result_folders: list[Path],
    prompt_response_files: dict[str, list[Path]],
    scored_entries: list[dict[str, Any]],
) -> str:
    lines = [
        "# Local Model Scorecard Report",
        "",
        f"- Scorecard template: {template_path}",
        f"- Model result folders found: {len(model_result_folders)}",
        f"- Scored entries found: {len(scored_entries)}",
        "",
        "## Model Result Folders",
        "",
    ]

    if model_result_folders:
        for folder in model_result_folders:
            lines.append(f"- `{folder.name}`")
            responses = prompt_response_files.get(folder.name, [])
            if responses:
                lines.extend(f"  - response: `{response.name}`" for response in responses)
            else:
                lines.append("  - response: none found")
    else:
        lines.append(
            "- None found yet. Run `agentic local-model scorecard-run --model-label <label>`.",
        )

    lines.extend(
        [
            "",
            "## What To Score",
            "",
            "For each model and prompt response, the human owner should score:",
            "",
        ],
    )
    lines.extend(f"- {dimension}" for dimension in SCORECARD_DIMENSIONS)

    lines.extend(
        [
            "",
            "Recommended manual role mapping:",
            "",
        ],
    )
    lines.extend(f"- {role}" for role in ROLE_MAPPING)

    lines.extend(
        [
            "",
            "## Winner",
            "",
        ],
    )

    if scored_entries:
        lines.extend(
            [
                "Scores are present in the template. Compare the scored entries manually before "
                "assigning models to roles; this report does not automatically choose a winner.",
            ],
        )
    else:
        lines.extend(
            [
                "No scored model entries are present yet. Do not claim a winner until the human "
                "owner has scored comparable model runs.",
            ],
        )

    lines.extend(
        [
            "",
            "## Safety",
            "",
            "Scorecard reports summarize saved local model output only. They do not execute model "
            "output, apply source edits, call cloud models, commit, push, merge, deploy, or call "
            "GitHub APIs.",
            "",
        ],
    )

    return "\n".join(lines)
