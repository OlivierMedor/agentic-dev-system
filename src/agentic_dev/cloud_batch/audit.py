from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agentic_dev.cloud_batch.persistence import batch_audit_log_path, ensure_batch_dirs
from agentic_dev.cloud_queue.persistence import checksum_text


@dataclass(frozen=True)
class BatchAuditEvent:
    event_id: str
    event_type: str
    batch_id: str
    item_id: str = ""
    prior_state: str = ""
    new_state: str = ""
    timestamp: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["details"] = dict(self.details)
        return data


def append_batch_audit_event(project_path: Path, event: BatchAuditEvent) -> Path:
    paths = ensure_batch_dirs(project_path)
    path = paths.audit_log
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.to_dict(), sort_keys=True))
        handle.write("\n")
    return path


def load_batch_audit_events(project_path: Path) -> list[dict[str, Any]]:
    path = batch_audit_log_path(project_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stable_batch_event_id(event: BatchAuditEvent) -> str:
    payload = "|".join(
        [
            event.event_type,
            event.batch_id,
            event.item_id,
            event.prior_state,
            event.new_state,
            event.timestamp,
            json.dumps(event.details, sort_keys=True),
        ],
    )
    return checksum_text(payload)[:16]

