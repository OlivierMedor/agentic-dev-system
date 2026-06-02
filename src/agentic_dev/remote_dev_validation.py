from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEV_VALIDATED = "DEV_VALIDATED"
DEV_VALIDATED_WITH_NOTES = "DEV_VALIDATED_WITH_NOTES"
DEV_FAILED = "DEV_FAILED"
NOT_RUN = "NOT_RUN"

ACCEPTED_VALIDATION_STATUSES = (
    DEV_VALIDATED,
    DEV_VALIDATED_WITH_NOTES,
    DEV_FAILED,
    NOT_RUN,
)

STATUS_OUTCOMES = {
    DEV_VALIDATED: {
        "status": "remote_dev_validated",
        "ready_for_review": True,
    },
    DEV_VALIDATED_WITH_NOTES: {
        "status": "remote_dev_validated_with_notes",
        "ready_for_review": True,
    },
    DEV_FAILED: {
        "status": "remote_dev_failed",
        "ready_for_review": False,
    },
    NOT_RUN: {
        "status": "remote_dev_not_run",
        "ready_for_review": False,
    },
}

REQUIRED_RESULT_FIELDS = (
    "validation_status",
    "environment_name",
    "branch_or_commit",
    "validation_notes",
    "next_action",
)

PACKET_FILENAMES = (
    "remote_dev_packet.md",
    "remote_dev_result_template.yaml",
)

OPTIONAL_EVIDENCE_FILES = (
    ("status.yaml", "Story status"),
    ("test_plan.yaml", "Test plan"),
    ("monitoring_plan.yaml", "Monitoring plan"),
    ("reports/test_layer_result.yaml", "Test layer result"),
    ("reports/quality_gate_result.yaml", "Quality gate result"),
    ("reports/finalize_story_result.yaml", "Finalize story result"),
    ("reports/cloud_review_result.yaml", "Cloud review result"),
    ("reports/merge_readiness_result.yaml", "Merge readiness result"),
    ("review_bundle/handoff.md", "Review bundle handoff"),
)


@dataclass(frozen=True)
class RemoteDevPacketResult:
    story: str
    story_path: Path
    validation_path: Path
    packet_path: Path
    template_path: Path
    generated_files: list[Path]
    missing_optional_files: list[str]


@dataclass(frozen=True)
class Evidence:
    present_files: list[tuple[str, str, str]]
    missing_files: list[str]


@dataclass(frozen=True)
class RemoteDevValidationResult:
    story: str
    story_path: Path
    validation_status: str
    ready_for_review: bool
    environment_name: str
    deployment_url: str
    branch_or_commit: str
    result_file: Path
    result_path: Path
    report_path: Path
    status_path: Path
    next_action: str


def create_remote_dev_packet(
    project_path: Path,
    story: str,
    force: bool = False,
) -> RemoteDevPacketResult:
    """Create a remote-dev validation packet without deploying or calling external services."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story
    validate_story_folder(story_path)

    story_file = story_path / "story.md"
    if not story_file.exists():
        raise FileNotFoundError(f"Required story file does not exist: {story_file}")

    validation_path = story_path / "remote_dev_validation"
    validation_path.mkdir(parents=True, exist_ok=True)

    packet_path = validation_path / "remote_dev_packet.md"
    template_path = validation_path / "remote_dev_result_template.yaml"
    packet_files = [validation_path / filename for filename in PACKET_FILENAMES]
    existing_files = [path for path in packet_files if path.exists()]
    if existing_files and not force:
        existing_list = ", ".join(str(path) for path in existing_files)
        raise ValueError(
            "Remote dev validation packet files already exist: "
            f"{existing_list}. Use --force to overwrite."
        )

    story_content = read_text(story_file)
    evidence = read_optional_evidence(story_path)

    files_to_content = {
        packet_path: build_packet(story, story_content, evidence),
        template_path: build_result_template(),
    }

    generated_files: list[Path] = []
    for path, content in files_to_content.items():
        write_text(path, content)
        generated_files.append(path)

    gitkeep_path = validation_path / ".gitkeep"
    if not gitkeep_path.exists():
        write_text(gitkeep_path, "")

    return RemoteDevPacketResult(
        story=story,
        story_path=story_path,
        validation_path=validation_path,
        packet_path=packet_path,
        template_path=template_path,
        generated_files=generated_files,
        missing_optional_files=evidence.missing_files,
    )


def record_remote_dev_validation(
    project_path: Path,
    story: str,
    result_file: Path,
) -> RemoteDevValidationResult:
    """Record manual remote-dev validation evidence without deploying or merging code."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story
    validate_story_folder(story_path)

    result_path = result_file.resolve()
    if not result_path.exists():
        raise FileNotFoundError(f"Remote dev validation result file does not exist: {result_path}")

    if not result_path.is_file():
        raise ValueError(f"Remote dev validation result path is not a file: {result_path}")

    result_data = load_yaml_mapping(result_path, "remote dev validation result file")
    validate_result_data(result_data, result_path)

    validation_status = str(result_data["validation_status"])
    outcome = STATUS_OUTCOMES[validation_status]
    ready_for_review = bool(outcome["ready_for_review"])

    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    remote_result_path = reports_path / "remote_dev_validation_result.yaml"
    report_path = reports_path / "remote_dev_validation_report.md"
    status_path = story_path / "status.yaml"

    result = RemoteDevValidationResult(
        story=story,
        story_path=story_path,
        validation_status=validation_status,
        ready_for_review=ready_for_review,
        environment_name=str(result_data["environment_name"]),
        deployment_url=str(result_data.get("deployment_url") or ""),
        branch_or_commit=str(result_data["branch_or_commit"]),
        result_file=result_path,
        result_path=remote_result_path,
        report_path=report_path,
        status_path=status_path,
        next_action=str(result_data["next_action"]),
    )

    write_remote_dev_result(result)
    write_remote_dev_report(result, result_data)
    update_status(status_path, story, validation_status)

    return result


def validate_story_folder(story_path: Path) -> None:
    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")


def read_optional_evidence(story_path: Path) -> Evidence:
    present_files: list[tuple[str, str, str]] = []
    missing_files: list[str] = []

    for relative_path, label in OPTIONAL_EVIDENCE_FILES:
        path = story_path / relative_path
        if path.exists() and path.is_file():
            present_files.append((relative_path, label, read_text(path)))
        else:
            missing_files.append(relative_path)

    return Evidence(present_files=present_files, missing_files=missing_files)


def validate_result_data(data: dict[str, Any], result_path: Path) -> None:
    missing_fields = [field for field in REQUIRED_RESULT_FIELDS if field not in data]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise ValueError(f"Missing required remote dev validation fields in {result_path}: {joined}.")

    empty_fields = [
        field
        for field in REQUIRED_RESULT_FIELDS
        if data.get(field) is None or str(data.get(field)).strip() == ""
    ]
    if empty_fields:
        joined = ", ".join(empty_fields)
        raise ValueError(f"Empty required remote dev validation fields in {result_path}: {joined}.")

    validation_status = str(data["validation_status"])
    if validation_status not in ACCEPTED_VALIDATION_STATUSES:
        accepted = ", ".join(ACCEPTED_VALIDATION_STATUSES)
        raise ValueError(
            "Invalid remote dev validation_status "
            f"{validation_status!r}. Expected one of: {accepted}."
        )


def write_remote_dev_result(result: RemoteDevValidationResult) -> None:
    data = {
        "story": result.story,
        "validation_status": result.validation_status,
        "ready_for_review": result.ready_for_review,
        "environment_name": result.environment_name,
        "deployment_url": result.deployment_url,
        "branch_or_commit": result.branch_or_commit,
        "result_file": str(result.result_file),
        "report_path": str(result.report_path),
        "next_action": result.next_action,
    }

    result.result_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def write_remote_dev_report(result: RemoteDevValidationResult, data: dict[str, Any]) -> None:
    deployment_url = result.deployment_url or "not provided"
    content = f"""# Remote Dev Validation Report

## Story

{result.story}

## Validation status

{result.validation_status}

## Environment

{result.environment_name}

## Deployment URL

{deployment_url}

## Branch or commit

{result.branch_or_commit}

## Validation notes

{data["validation_notes"]}

## Smoke test summary

{format_check_summary(data.get("smoke_tests"))}
## Integration test summary

{format_check_summary(data.get("integration_tests"))}
## Mock E2E test summary

{format_check_summary(data.get("mock_e2e_tests"))}
## Logs review summary

{format_check_summary(data.get("logs_review"))}
## Environment variable checklist

{format_environment_checklist(data.get("environment_checklist"))}
## Rollback notes

{format_scalar(data.get("rollback_notes"), "not provided")}

## Known risks

{format_known_risks(data.get("known_risks"))}
## Next action

{result.next_action}

## Human decision reminder

The human owner still decides whether to merge or release after reviewing this evidence.
This command did not deploy, commit, push, merge, call GitHub APIs, or call cloud models.
"""

    result.report_path.write_text(content, encoding="utf-8")


def update_status(status_path: Path, story: str, validation_status: str) -> None:
    outcome = STATUS_OUTCOMES[validation_status]
    status_data = load_yaml_mapping(status_path, "status.yaml")
    status_data["story_id"] = status_data.get("story_id") or story
    status_data["status"] = outcome["status"]
    status_data["ready_for_review"] = outcome["ready_for_review"]
    status_data["remote_dev_validation_status"] = validation_status

    safe_write_yaml(status_path, status_data)


def build_packet(story: str, story_content: str, evidence: Evidence) -> str:
    sections = [
        "# Remote Dev Validation Packet",
        "",
        "This packet prepares manual remote-dev validation evidence. It does not deploy, "
        "commit, push, merge, call GitHub APIs, or call cloud models.",
        "",
        "## Story name",
        "",
        story,
        "",
        "## Story content",
        "",
        fenced("markdown", story_content),
        "",
    ]

    for relative_path, label, content in evidence.present_files:
        sections.extend(
            [
                f"## {label}",
                "",
                f"Source: `{relative_path}`",
                "",
                fenced(format_hint(relative_path), content),
                "",
            ],
        )

    sections.extend(
        [
            "## Missing optional evidence",
            "",
            format_missing_optional_evidence(evidence.missing_files),
            "",
            "## Remote dev evidence to collect",
            "",
            "- Record the deployment URL or environment name.",
            "- Record the branch or commit under validation.",
            "- Record Docker, build, and deployment results.",
            "- Run smoke checks and include concrete evidence.",
            "- Run relevant integration or mock E2E checks when applicable.",
            "- Review app logs for errors and warnings.",
            "- Review the environment variable checklist without exposing secret values.",
            "- Record database migration status when applicable.",
            "- Record rollback notes.",
            "- Record known risks.",
            "- Do not expose secrets, API keys, private keys, tokens, or `.env` values.",
            "- Do not mark DEV_VALIDATED if checks were not actually performed.",
            "",
            "## Smoke test checklist",
            "",
            "- [ ] Core app route or command works in remote dev.",
            "- [ ] Main user workflow for the story works.",
            "- [ ] No critical UI, API, or worker errors appear during the smoke check.",
            "",
            "## Integration test checklist",
            "",
            "- [ ] Relevant integration or mock E2E checks were run, or a reason is recorded.",
            "- [ ] External dependencies were mocked, disabled, or validated safely as appropriate.",
            "",
            "## Log review checklist",
            "",
            "- [ ] Application logs were checked.",
            "- [ ] Build or deployment logs were checked.",
            "- [ ] No unresolved critical errors remain.",
            "",
            "## Environment variable checklist",
            "",
            "- [ ] Required variable names are present.",
            "- [ ] Secret values were not printed, copied into reports, or committed.",
            "- [ ] Missing variables or unsafe defaults are recorded as risks.",
            "",
            "## Rollback notes",
            "",
            "- Record how to roll back the remote-dev deployment or revert the change if needed.",
            "",
            "## Known risks",
            "",
            "- Record unresolved risks, skipped checks, follow-up work, or manual review concerns.",
            "",
            "## Accepted validation statuses",
            "",
            "- DEV_VALIDATED",
            "- DEV_VALIDATED_WITH_NOTES",
            "- DEV_FAILED",
            "- NOT_RUN",
        ],
    )

    return "\n".join(sections).rstrip() + "\n"


def build_result_template() -> str:
    return """validation_status: DEV_VALIDATED
environment_name: remote-dev
deployment_url: ""
branch_or_commit: ""
validated_by: ""
validation_notes: ""
smoke_tests:
  status: passed
  evidence:
    - "Describe smoke test evidence."
integration_tests:
  status: not_run
  evidence:
    - "Explain why not run or include evidence."
mock_e2e_tests:
  status: not_run
  evidence:
    - "Explain why not run or include evidence."
logs_review:
  status: passed
  evidence:
    - "No critical errors found."
environment_checklist:
  status: passed
  notes: "Secrets were not printed or committed."
rollback_notes: ""
known_risks: []
next_action: "Human owner reviews remote dev evidence before merge/release."
"""


def format_check_summary(value: Any) -> str:
    if not isinstance(value, dict):
        return "- not provided\n"

    lines = [f"- status: {format_scalar(value.get('status'), 'not provided')}"]
    evidence = value.get("evidence")
    if isinstance(evidence, list) and evidence:
        lines.append("- evidence:")
        lines.extend(f"  - {format_scalar(item, 'not provided')}" for item in evidence)
    elif evidence:
        lines.append(f"- evidence: {format_scalar(evidence, 'not provided')}")
    else:
        lines.append("- evidence: not provided")

    return "\n".join(lines) + "\n"


def format_environment_checklist(value: Any) -> str:
    if not isinstance(value, dict):
        return "- not provided\n"

    return (
        f"- status: {format_scalar(value.get('status'), 'not provided')}\n"
        f"- notes: {format_scalar(value.get('notes'), 'not provided')}\n"
    )


def format_known_risks(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "- None recorded.\n"
        return "\n".join(f"- {format_scalar(item, 'not provided')}" for item in value) + "\n"

    if value:
        return f"- {format_scalar(value, 'not provided')}\n"

    return "- None recorded.\n"


def format_missing_optional_evidence(missing_files: list[str]) -> str:
    if not missing_files:
        return "No optional evidence files are missing."

    return "\n".join(f"- `{relative_path}` was not found." for relative_path in missing_files)


def format_hint(relative_path: str) -> str:
    suffix = Path(relative_path).suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".md":
        return "markdown"
    return "text"


def format_scalar(value: Any, fallback: str) -> str:
    if value is None or str(value).strip() == "":
        return fallback
    return str(value)


def fenced(language: str, content: str) -> str:
    return f"```{language}\n{content.rstrip()}\n```"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def load_yaml_mapping(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file_handle:
        loaded = yaml.safe_load(file_handle)

    if loaded is None:
        return {}

    if not isinstance(loaded, dict):
        raise ValueError(f"{label} must be a YAML mapping: {path}")

    return loaded


def safe_write_yaml(path: Path, data: dict[str, Any]) -> None:
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    temporary_path.replace(path)
