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
SCORECARD_SCORES_FILENAME = "scorecard_scores.yaml"
SCORECARD_README_FILENAME = "README.md"
SCORECARD_REPORT_RELATIVE_PATH = Path("reports") / "local_model_scorecard_report.md"
ROLE_RECOMMENDATIONS_MD_RELATIVE_PATH = (
    Path("reports") / "local_model_role_recommendations.md"
)
ROLE_RECOMMENDATIONS_YAML_RELATIVE_PATH = (
    Path("reports") / "local_model_role_recommendations.yaml"
)

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

REQUIRED_SCORING_FIELDS = [
    "model_label",
    "role",
    "response_file",
    "instruction_following",
    "correctness",
    "hallucination_control",
    "code_quality",
    "test_quality",
    "safety_compliance",
    "clarity",
    "overall_fit_for_role",
    "speed_notes",
    "reviewer_notes",
]

NUMERIC_SCORING_FIELDS = [
    "instruction_following",
    "correctness",
    "hallucination_control",
    "code_quality",
    "test_quality",
    "safety_compliance",
    "clarity",
    "overall_fit_for_role",
]

ROLE_RECOMMENDATION_TIE_BREAKERS = [
    "safety_compliance",
    "hallucination_control",
    "correctness",
    "instruction_following",
]

SCORECARD_ROLES = [
    "developer_agent",
    "test_agent",
    "docs_agent",
    "reviewer_agent",
    "maintenance_agent",
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


@dataclass(frozen=True)
class ScorecardScaffoldScoresResult:
    scores_path: Path
    entries: list[dict[str, Any]]
    created: bool


@dataclass(frozen=True)
class ScorecardRecommendationResult:
    markdown_report_path: Path
    yaml_report_path: Path
    recommendations: dict[str, dict[str, Any]]
    complete_entries: list[dict[str, Any]]
    incomplete_entries: list[dict[str, Any]]


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


def scaffold_local_model_scorecard_scores(
    project_path: Path,
    force: bool = False,
) -> ScorecardScaffoldScoresResult:
    resolved_project_path = project_path.resolve()
    scorecard_path = resolved_project_path / SCORECARD_RELATIVE_PATH
    results_path = resolved_project_path / RESULTS_RELATIVE_PATH
    scores_path = scorecard_path / SCORECARD_SCORES_FILENAME

    if scores_path.exists() and not force:
        raise ValueError(f"{scores_path} already exists. Use --force to overwrite it.")

    entries = build_scaffold_score_entries(resolved_project_path, results_path)
    scorecard_path.mkdir(parents=True, exist_ok=True)
    scores_path.write_text(build_scorecard_scores_file(entries), encoding="utf-8")

    return ScorecardScaffoldScoresResult(
        scores_path=scores_path,
        entries=entries,
        created=True,
    )


def recommend_local_model_roles(project_path: Path) -> ScorecardRecommendationResult:
    resolved_project_path = project_path.resolve()
    scores_path = (
        resolved_project_path / SCORECARD_RELATIVE_PATH / SCORECARD_SCORES_FILENAME
    )
    if not scores_path.exists():
        raise FileNotFoundError(
            f"{scores_path} does not exist. Run scorecard-scaffold-scores first.",
        )

    entries = load_scorecard_scores(scores_path)
    complete_entries, incomplete_entries = partition_score_entries(entries)
    recommendations = build_role_recommendations(complete_entries)

    markdown_report_path = resolved_project_path / ROLE_RECOMMENDATIONS_MD_RELATIVE_PATH
    yaml_report_path = resolved_project_path / ROLE_RECOMMENDATIONS_YAML_RELATIVE_PATH
    markdown_report_path.parent.mkdir(parents=True, exist_ok=True)

    yaml_data = {
        "recommendation_version": 1,
        "scorecard_scores": str(scores_path),
        "recommendations": recommendations,
        "complete_entries": complete_entries,
        "incomplete_entries": incomplete_entries,
        "safety_recommendation": build_safety_recommendation(),
        "final_note": (
            "Recommendations are advisory only. The human owner controls runtime "
            "assignment and .agentic/agent_runtime.yaml is not updated automatically."
        ),
    }
    yaml_report_path.write_text(yaml.safe_dump(yaml_data, sort_keys=False), encoding="utf-8")
    markdown_report_path.write_text(
        build_role_recommendations_report(
            scores_path=scores_path,
            recommendations=recommendations,
            complete_entries=complete_entries,
            incomplete_entries=incomplete_entries,
        ),
        encoding="utf-8",
    )

    return ScorecardRecommendationResult(
        markdown_report_path=markdown_report_path,
        yaml_report_path=yaml_report_path,
        recommendations=recommendations,
        complete_entries=complete_entries,
        incomplete_entries=incomplete_entries,
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
            "Use plain ASCII text where possible. Avoid emoji and checkmark symbols because "
            "Windows and PowerShell logs can display encoding artifacts such as `âœ“`.",
            "Use the requested headings exactly. Do not wrap the entire response in an "
            "unnecessary nested Markdown code fence.",
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
            "- Prefer plain ASCII in prompt responses.",
            "- Avoid emoji/checkmark symbols and unnecessary whole-response code fences.",
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


def build_scaffold_score_entries(
    project_path: Path,
    results_path: Path,
) -> list[dict[str, Any]]:
    if not results_path.exists():
        return []

    entries: list[dict[str, Any]] = []
    for model_folder in sorted(path for path in results_path.glob("*") if path.is_dir()):
        for response_path in sorted(model_folder.glob("*_response.md")):
            role = role_from_response_filename(response_path.name)
            if role is None:
                continue
            entries.append(
                {
                    "model_label": model_folder.name,
                    "role": role,
                    "response_file": response_path.relative_to(project_path).as_posix(),
                    "instruction_following": None,
                    "correctness": None,
                    "hallucination_control": None,
                    "code_quality": None,
                    "test_quality": None,
                    "safety_compliance": None,
                    "clarity": None,
                    "overall_fit_for_role": None,
                    "speed_notes": "",
                    "reviewer_notes": "",
                },
            )

    return entries


def role_from_response_filename(filename: str) -> str | None:
    suffix = "_prompt_response.md"
    if not filename.endswith(suffix):
        return None

    role = filename[: -len(suffix)]
    if role not in SCORECARD_ROLES:
        return None

    return role


def build_scorecard_scores_file(entries: list[dict[str, Any]]) -> str:
    payload = {
        "scorecard_scores_version": 1,
        "scoring_scale": "Use 1-5 for numeric score fields where 1 is poor and 5 is excellent.",
        "roles": SCORECARD_ROLES,
        "required_fields": REQUIRED_SCORING_FIELDS,
        "tie_breakers": ROLE_RECOMMENDATION_TIE_BREAKERS,
        "scores": entries,
    }
    return yaml.safe_dump(payload, sort_keys=False)


def load_scorecard_scores(scores_path: Path) -> list[dict[str, Any]]:
    loaded = yaml.safe_load(scores_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{scores_path} must contain a YAML mapping.")

    scores = loaded.get("scores")
    if not isinstance(scores, list):
        raise ValueError(f"{scores_path} must contain a scores list.")

    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(scores, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Score entry {index} must be a YAML mapping.")

        missing_fields = [field for field in REQUIRED_SCORING_FIELDS if field not in entry]
        if missing_fields:
            raise ValueError(
                f"Score entry {index} is missing required fields: "
                f"{', '.join(missing_fields)}",
            )

        entries.append(entry)

    return entries


def partition_score_entries(
    entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    complete_entries: list[dict[str, Any]] = []
    incomplete_entries: list[dict[str, Any]] = []

    for entry in entries:
        missing_reasons = incomplete_score_reasons(entry)
        if missing_reasons:
            incomplete_entry = dict(entry)
            incomplete_entry["incomplete_reasons"] = missing_reasons
            incomplete_entries.append(incomplete_entry)
        else:
            complete_entries.append(entry)

    return complete_entries, incomplete_entries


def incomplete_score_reasons(entry: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for text_field in ["model_label", "role", "response_file"]:
        value = entry.get(text_field)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"{text_field} is blank")

    role = entry.get("role")
    if isinstance(role, str) and role.strip() and role not in SCORECARD_ROLES:
        reasons.append(f"role must be one of: {', '.join(SCORECARD_ROLES)}")

    for score_field in NUMERIC_SCORING_FIELDS:
        if not is_score_value(entry.get(score_field)):
            reasons.append(f"{score_field} must be a number from 1 to 5")

    return reasons


def is_score_value(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and 1 <= value <= 5


def build_role_recommendations(
    complete_entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    recommendations: dict[str, dict[str, Any]] = {}

    for role in SCORECARD_ROLES:
        role_entries = [entry for entry in complete_entries if entry["role"] == role]
        if not role_entries:
            continue

        ranked_entries = sorted(role_entries, key=recommendation_sort_key, reverse=True)
        best_entry = ranked_entries[0]
        runner_up_entry = ranked_entries[1] if len(ranked_entries) > 1 else None
        recommendations[role] = {
            "best_model": recommendation_entry_summary(best_entry),
            "runner_up": (
                recommendation_entry_summary(runner_up_entry)
                if runner_up_entry is not None
                else None
            ),
            "scoring_evidence_summary": build_scoring_evidence_summary(
                best_entry,
                runner_up_entry,
            ),
        }

    return recommendations


def recommendation_sort_key(entry: dict[str, Any]) -> tuple[float, ...]:
    return tuple(
        float(entry[field])
        for field in ["overall_fit_for_role", *ROLE_RECOMMENDATION_TIE_BREAKERS]
    )


def recommendation_entry_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_label": entry["model_label"],
        "role": entry["role"],
        "response_file": entry["response_file"],
        "overall_fit_for_role": entry["overall_fit_for_role"],
        "safety_compliance": entry["safety_compliance"],
        "hallucination_control": entry["hallucination_control"],
        "correctness": entry["correctness"],
        "instruction_following": entry["instruction_following"],
    }


def build_scoring_evidence_summary(
    best_entry: dict[str, Any],
    runner_up_entry: dict[str, Any] | None,
) -> str:
    best_summary = (
        f"{best_entry['model_label']} scored {best_entry['overall_fit_for_role']} "
        "on overall fit"
    )
    if runner_up_entry is None:
        return f"{best_summary}. No runner-up has complete scores for this role."

    return (
        f"{best_summary}; runner-up {runner_up_entry['model_label']} scored "
        f"{runner_up_entry['overall_fit_for_role']}."
    )


def build_safety_recommendation() -> str:
    return (
        "Start local models on draft/report roles and keep high-risk DeFi, security, "
        "merge, release, and runtime-default decisions under human and configured "
        "cloud/human review."
    )


def build_role_recommendations_report(
    scores_path: Path,
    recommendations: dict[str, dict[str, Any]],
    complete_entries: list[dict[str, Any]],
    incomplete_entries: list[dict[str, Any]],
) -> str:
    lines = [
        "# Local Model Role Recommendations",
        "",
        f"- Score file: {scores_path}",
        f"- Complete scored entries: {len(complete_entries)}",
        f"- Incomplete scored entries ignored: {len(incomplete_entries)}",
        "",
        "## Recommendations",
        "",
    ]

    if recommendations:
        for role in SCORECARD_ROLES:
            recommendation = recommendations.get(role)
            if recommendation is None:
                lines.append(f"### {role}")
                lines.append("")
                lines.append("- No complete scores for this role.")
                lines.append("")
                continue

            best_model = recommendation["best_model"]
            runner_up = recommendation["runner_up"]
            lines.append(f"### {role}")
            lines.append("")
            lines.append(f"- Best model: `{best_model['model_label']}`")
            if runner_up is None:
                lines.append("- Runner-up: none with complete scores")
            else:
                lines.append(f"- Runner-up: `{runner_up['model_label']}`")
            lines.append(f"- Evidence: {recommendation['scoring_evidence_summary']}")
            lines.append("")
    else:
        lines.extend(
            [
                "No complete scores are available. No role winner is claimed.",
                "",
            ],
        )

    lines.extend(
        [
            "## Incomplete Scoring Warnings",
            "",
        ],
    )

    if incomplete_entries:
        for entry in incomplete_entries:
            model_label = entry.get("model_label") or "<blank model>"
            role = entry.get("role") or "<blank role>"
            reasons = "; ".join(entry.get("incomplete_reasons", []))
            lines.append(f"- `{model_label}` / `{role}` ignored: {reasons}")
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Safety Recommendation",
            "",
            build_safety_recommendation(),
            "",
            "## Final Note",
            "",
            "These recommendations are advisory only. The human owner controls runtime "
            "assignment, and this command does not update `.agentic/agent_runtime.yaml`.",
            "",
            "The command only reads human scores and saved response files. It does not "
            "execute model output, call cloud models, edit source files, commit, push, "
            "merge, deploy, or call GitHub APIs.",
            "",
        ],
    )

    return "\n".join(lines)


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
