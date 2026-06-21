from __future__ import annotations

import json

from agentic_dev.cloud_application.models import (
    ApplicationRecord,
    ApplicationStatusResult,
    RecoveryResult,
    ResumeResult,
)


def format_application_record(record: ApplicationRecord) -> str:
    return "\n".join(
        [
            f"Application: {record.application_id}",
            f"Request: {record.request_id}",
            f"Status: {record.status}",
            f"Plan checksum: {record.plan_checksum}",
            f"Revision: {record.revision_id or 'pending'}",
            "",
            json.dumps(record.to_dict(), sort_keys=True),
        ],
    )


def format_application_summary(result: ApplicationStatusResult) -> str:
    lines = [
        "Application status:",
        f"Total applications: {len(result.applications)}",
    ]
    for state, count in sorted(result.counts_by_state.items()):
        lines.append(f"- {state}: {count}")
    if result.active_pointer is not None:
        lines.extend(["", json.dumps(result.active_pointer.to_dict(), sort_keys=True)])
    return "\n".join(lines)


def format_application_status(result: ApplicationStatusResult) -> str:
    return format_application_summary(result)


def format_resume_result(result: ResumeResult) -> str:
    return "\n".join(
        [
            f"Application: {result.application_id}",
            f"Revision: {result.revision_id}",
            f"Status: {result.status}",
            f"Task IDs: {', '.join(result.task_ids) if result.task_ids else 'none'}",
            f"Lease IDs: {', '.join(result.lease_ids) if result.lease_ids else 'none'}",
            *( [f"Reasons: {', '.join(result.reasons)}"] if result.reasons else [] ),
        ],
    )


def format_recovery_result(result: RecoveryResult) -> str:
    lines = [
        "Recovery inspection:",
        f"Project: {result.project_path}",
        f"Reconciled: {result.reconciled}",
        "",
        "Findings:",
    ]
    for finding in result.findings:
        lines.append(f"- {finding}")
    lines.append("")
    lines.append("Recommended actions:")
    for action in result.recommended_actions:
        lines.append(f"- {action}")
    return "\n".join(lines)
