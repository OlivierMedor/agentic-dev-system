from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentic_dev.artifact_policy import (
    is_env_file,
    is_feature_scan_runtime_path,
    is_generated_cloud_review_packet_path,
    is_generated_remote_dev_validation_path,
    is_generated_review_bundle_path,
    is_local_agent_context_output_path,
    is_local_agent_draft_output_path,
    is_local_model_raw_response_path,
    is_local_model_scorecard_result_path,
    is_local_model_scorecard_scoring_artifact_path,
    is_runtime_queue_item_path,
    is_support_queue_runtime_path,
    normalize_git_path,
    run_git_ls_files,
)


PUBLIC_READINESS_REPORT_RELATIVE_PATH = Path("reports") / "public_readiness_report.md"


@dataclass(frozen=True)
class PublicReadinessViolation:
    path: str
    reason: str


@dataclass(frozen=True)
class PublicReadinessResult:
    project_path: Path
    tracked_files: list[str]
    violations: list[PublicReadinessViolation]
    report_path: Path

    @property
    def passed(self) -> bool:
        return not self.violations


def find_public_readiness_violations(tracked_files: list[str]) -> list[PublicReadinessViolation]:
    violations: list[PublicReadinessViolation] = []

    for tracked_file in tracked_files:
        normalized_path = normalize_git_path(tracked_file)
        parts = normalized_path.split("/") if normalized_path else []
        filename = parts[-1] if parts else normalized_path
        lowercase_filename = filename.lower()

        reason = public_readiness_violation_reason(normalized_path, parts, filename)

        if reason is None and lowercase_filename.endswith(".zip"):
            reason = "zip archives must not be tracked for public readiness"

        if reason is not None:
            violations.append(PublicReadinessViolation(path=normalized_path, reason=reason))

    return violations


def public_readiness_violation_reason(
    normalized_path: str,
    parts: list[str],
    filename: str,
) -> str | None:
    if normalized_path == "blueprints/agentic-architecture.md":
        return "private local operator guidance must remain untracked"

    if is_env_file(filename):
        return "environment files and secrets must remain untracked"

    if parts and parts[0] == "review_to_chatgpt":
        return "review_to_chatgpt artifacts must remain untracked"

    if is_generated_review_bundle_path(parts, filename):
        return "generated review bundle files must remain untracked"

    if is_generated_cloud_review_packet_path(parts, filename):
        return "generated cloud review packet files must remain untracked"

    if is_generated_remote_dev_validation_path(parts, filename):
        return "generated remote dev validation files must remain untracked"

    if is_support_queue_runtime_path(parts, filename):
        return "support queue runtime files must remain untracked"

    if is_feature_scan_runtime_path(parts, filename):
        return "feature scan runtime files must remain untracked"

    if is_local_model_scorecard_result_path(parts, filename):
        return "local model scorecard result files must remain untracked"

    if is_local_agent_draft_output_path(parts, filename):
        return "local agent draft outputs must remain untracked"

    if is_local_agent_context_output_path(parts, filename):
        return "local agent context packets must remain untracked"

    if is_local_model_raw_response_path(parts, filename):
        return "local model raw response files must remain untracked"

    if is_local_model_scorecard_scoring_artifact_path(normalized_path):
        return "local model scorecard scoring artifacts must remain untracked"

    if normalized_path == "reports/local_model_scorecard_report.md":
        return "local model scorecard reports must remain untracked"

    if is_runtime_queue_item_path(parts, filename):
        return "queue runtime item files must remain untracked"

    return None


def run_public_readiness(project_path: Path) -> PublicReadinessResult:
    resolved_project_path = project_path.resolve()
    tracked_files = run_git_ls_files(resolved_project_path)
    violations = find_public_readiness_violations(tracked_files)
    report_path = resolved_project_path / PUBLIC_READINESS_REPORT_RELATIVE_PATH
    result = PublicReadinessResult(
        project_path=resolved_project_path,
        tracked_files=tracked_files,
        violations=violations,
        report_path=report_path,
    )
    write_public_readiness_report(result)
    return result


def write_public_readiness_report(result: PublicReadinessResult) -> None:
    result.report_path.parent.mkdir(parents=True, exist_ok=True)
    result.report_path.write_text(format_public_readiness_report(result), encoding="utf-8")


def format_public_readiness_report(result: PublicReadinessResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        "# Public Readiness Report",
        "",
        f"- Project: {result.project_path}",
        f"- Status: {status}",
        f"- Git-tracked files checked: {len(result.tracked_files)}",
        f"- Violations: {len(result.violations)}",
        "",
    ]

    if result.passed:
        lines.extend(
            [
                "## Result",
                "",
                "Public readiness passed. No forbidden tracked files were found.",
                "",
            ],
        )
    else:
        lines.extend(
            [
                "## Result",
                "",
                "Public readiness failed. Remove these files from Git tracking before making the "
                "repository public.",
                "",
                "## Violations",
                "",
            ],
        )

        for violation in result.violations:
            lines.append(f"- `{violation.path}`: {violation.reason}")

        lines.append("")

    lines.extend(
        [
            "## Policy",
            "",
            "These tracked paths are forbidden for public readiness:",
            "",
            "- `blueprints/agentic-architecture.md`",
            "- `.env` and `.env.*` except `.env.example`",
            "- `review_to_chatgpt/**`",
            "- `*.zip`",
            "- `stories/**/review_bundle/*` except `.gitkeep`",
            "- `stories/**/cloud_review_packet/*` except `.gitkeep`",
            "- `stories/**/remote_dev_validation/*` except `.gitkeep`",
            "- `.agentic/support_queue/**/*.yaml` and `*.md` runtime files",
            "- `.agentic/feature_scan/*.md` and `*.yaml` runtime files",
            "- `.agentic/local_model_scorecard/results/**`",
            "- `stories/**/reports/local_agent_drafts/*` except `.gitkeep`",
            "- `stories/**/reports/local_agent_context/*` except `.gitkeep`",
            "- `*_raw_response.json`",
            "- `.agentic/local_model_scorecard/scorecard_scores.yaml`",
            "- `reports/local_model_scorecard_report.md`",
            "- `reports/local_model_role_recommendations.md`",
            "- `reports/local_model_role_recommendations.yaml`",
            "- `.agentic/improvement_queue/**/IMP-*.yaml`",
            "- `.agentic/maintenance_queue/**/MAINT-*.yaml`",
            "- `.agentic/feature_queue/**/FEATURE-*.yaml`",
            "",
            "This command checks Git tracking only. It does not delete files, call cloud models, "
            "commit, push, merge, or deploy.",
            "",
        ],
    )

    return "\n".join(lines)


def format_public_readiness_terminal_report(result: PublicReadinessResult) -> str:
    if result.passed:
        return (
            "Public readiness passed: no forbidden tracked files were found.\n"
            f"Report written to: {result.report_path}"
        )

    lines = [
        "Public readiness failed: forbidden tracked files were found.",
        f"Report written to: {result.report_path}",
        "",
        "Violations:",
    ]

    for violation in result.violations:
        lines.append(f"  - {violation.path}: {violation.reason}")

    return "\n".join(lines)
