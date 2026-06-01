from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


APPROVE = "APPROVE"
APPROVE_WITH_NOTES = "APPROVE_WITH_NOTES"
REQUEST_CHANGES = "REQUEST_CHANGES"

ACCEPTED_DECISIONS = (APPROVE, APPROVE_WITH_NOTES, REQUEST_CHANGES)

DECISION_OUTCOMES = {
    APPROVE: {
        "ready_for_human_merge_decision": True,
        "status": "cloud_review_approved",
        "ready_for_review": True,
        "next_action": "Human owner may approve merge after reviewing the PR.",
    },
    APPROVE_WITH_NOTES: {
        "ready_for_human_merge_decision": True,
        "status": "cloud_review_approved_with_notes",
        "ready_for_review": True,
        "next_action": "Human owner should review notes before merge.",
    },
    REQUEST_CHANGES: {
        "ready_for_human_merge_decision": False,
        "status": "request_changes",
        "ready_for_review": False,
        "next_action": "Address requested changes before merge.",
    },
}

DECISION_LINE_PATTERN = re.compile(
    rf"^\s*Decision\s*:\s*({'|'.join(ACCEPTED_DECISIONS)})\s*$",
    re.MULTILINE,
)
OWN_LINE_PATTERN = re.compile(
    rf"^\s*({'|'.join(ACCEPTED_DECISIONS)})\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class CloudReviewResult:
    story: str
    story_path: Path
    decision: str
    ready_for_human_merge_decision: bool
    result_file: Path
    cloud_review_result_path: Path
    cloud_review_report_path: Path
    status_path: Path
    next_action: str


def record_cloud_review(project_path: Path, story: str, result_file: Path) -> CloudReviewResult:
    """Record a manual cloud review result without calling cloud models or merging code."""
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    result_path = result_file.resolve()
    if not result_path.exists():
        raise FileNotFoundError(f"Cloud review result file does not exist: {result_path}")

    if not result_path.is_file():
        raise ValueError(f"Cloud review result path is not a file: {result_path}")

    raw_content = result_path.read_text(encoding="utf-8")
    decision = extract_decision(raw_content)
    outcome = DECISION_OUTCOMES[decision]

    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    cloud_review_result_path = reports_path / "cloud_review_result.yaml"
    cloud_review_report_path = reports_path / "cloud_review_report.md"
    status_path = story_path / "status.yaml"

    result = CloudReviewResult(
        story=story,
        story_path=story_path,
        decision=decision,
        ready_for_human_merge_decision=bool(outcome["ready_for_human_merge_decision"]),
        result_file=result_path,
        cloud_review_result_path=cloud_review_result_path,
        cloud_review_report_path=cloud_review_report_path,
        status_path=status_path,
        next_action=str(outcome["next_action"]),
    )

    write_cloud_review_result(result)
    write_cloud_review_report(result, raw_content)
    update_status(status_path, story, decision)

    return result


def extract_decision(content: str) -> str:
    content = content.lstrip("\ufeff")

    decision_line_matches = DECISION_LINE_PATTERN.findall(content)
    own_line_matches = OWN_LINE_PATTERN.findall(content)
    all_matches = decision_line_matches + own_line_matches
    unique_matches = set(all_matches)

    if len(unique_matches) > 1:
        joined = ", ".join(sorted(unique_matches))
        raise ValueError(f"Ambiguous cloud review decision. Found multiple decisions: {joined}.")

    if decision_line_matches:
        return single_decision_or_error(decision_line_matches)

    if own_line_matches:
        return single_decision_or_error(own_line_matches)

    accepted = ", ".join(ACCEPTED_DECISIONS)
    raise ValueError(f"Missing cloud review decision. Expected one of: {accepted}.")


def single_decision_or_error(matches: list[str]) -> str:
    unique_decisions = sorted(set(matches))
    if len(unique_decisions) == 1:
        return unique_decisions[0]

    joined = ", ".join(unique_decisions)
    raise ValueError(f"Ambiguous cloud review decision. Found multiple decisions: {joined}.")


def write_cloud_review_result(result: CloudReviewResult) -> None:
    data = {
        "story": result.story,
        "decision": result.decision,
        "ready_for_human_merge_decision": result.ready_for_human_merge_decision,
        "result_file": str(result.result_file),
        "cloud_review_report_path": str(result.cloud_review_report_path),
        "next_action": result.next_action,
    }

    result.cloud_review_result_path.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )


def write_cloud_review_report(result: CloudReviewResult, raw_content: str) -> None:
    content = f"""# Cloud Review Report

## Story

{result.story}

## Decision

{result.decision}

## Summary

Recorded the manual cloud review decision from `{result.result_file}`.
This command did not call cloud models, commit, push, merge, or deploy.
Human final approval is still required before merge.

## Original result file

{result.result_file}

## Raw cloud review content

```markdown
{raw_content.rstrip()}
```

## Next action

{result.next_action}
"""

    result.cloud_review_report_path.write_text(content, encoding="utf-8")


def update_status(status_path: Path, story: str, decision: str) -> None:
    outcome = DECISION_OUTCOMES[decision]
    status_data = load_yaml_mapping(status_path)
    status_data["story_id"] = status_data.get("story_id") or story
    status_data["status"] = outcome["status"]
    status_data["ready_for_review"] = outcome["ready_for_review"]
    status_data["cloud_review_decision"] = decision

    status_path.write_text(yaml.safe_dump(status_data, sort_keys=False), encoding="utf-8")


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file_handle:
        loaded = yaml.safe_load(file_handle)

    if loaded is None:
        return {}

    if not isinstance(loaded, dict):
        raise ValueError(f"status.yaml must be a YAML mapping: {path}")

    return loaded
