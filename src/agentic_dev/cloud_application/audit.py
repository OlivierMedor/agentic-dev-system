from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from agentic_dev.cloud_application.models import ApplicationAuditEvent
from agentic_dev.cloud_application.persistence import (
    application_audit_log_path,
    append_jsonl,
    ensure_cloud_application_dirs,
    read_jsonl,
)

AuditIdFactory = Callable[[], str]


def record_application_audit_event(
    project_path: Path,
    event: ApplicationAuditEvent,
    event_id_factory: AuditIdFactory | None = None,
) -> Path:
    ensure_cloud_application_dirs(project_path)
    normalized = ApplicationAuditEvent(
        event_id=event.event_id or (event_id_factory() if event_id_factory else event.event_id),
        event_type=event.event_type,
        application_id=event.application_id,
        request_id=event.request_id,
        prior_state=event.prior_state,
        new_state=event.new_state,
        timestamp=event.timestamp,
        details=event.details,
    )
    return append_jsonl(application_audit_log_path(project_path), normalized.to_dict())


def load_application_audit_events(project_path: Path) -> list[dict[str, Any]]:
    ensure_cloud_application_dirs(project_path)
    return read_jsonl(application_audit_log_path(project_path))

