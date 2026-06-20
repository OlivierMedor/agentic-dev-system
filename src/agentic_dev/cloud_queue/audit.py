from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic_dev.cloud_queue.models import CloudQueueAuditEvent
from agentic_dev.cloud_queue.persistence import append_audit_event, read_audit_events


def record_audit_event(
    project_path: Path,
    event: CloudQueueAuditEvent,
    event_id_factory: Any | None = None,
) -> Path:
    return append_audit_event(project_path, event, event_id_factory=event_id_factory)


def load_audit_events(project_path: Path) -> list[dict[str, Any]]:
    return read_audit_events(project_path)
