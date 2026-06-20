from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from agentic_dev.cloud_queue.models import CloudQueueAuditEvent, CloudQueueRequest


AuditIdFactory = Callable[[], str]


@dataclass(frozen=True)
class CloudQueuePaths:
    root: Path
    requests: Path
    exports: Path
    imports: Path
    audit_log: Path
    approvals: Path


def cloud_queue_paths(project_path: Path) -> CloudQueuePaths:
    root = project_path.resolve() / ".agentic" / "cloud_queue"
    return CloudQueuePaths(
        root=root,
        requests=root / "requests",
        exports=root / "exports",
        imports=root / "imports",
        audit_log=root / "audit.jsonl",
        approvals=root / "approvals",
    )


def ensure_cloud_queue_dirs(project_path: Path) -> CloudQueuePaths:
    paths = cloud_queue_paths(project_path)
    for directory in (paths.root, paths.requests, paths.exports, paths.imports, paths.approvals):
        directory.mkdir(parents=True, exist_ok=True)
    return paths


def request_path(project_path: Path, request_id: str, state: str | None = None) -> Path:
    paths = cloud_queue_paths(project_path)
    filename = f"{request_id}.yaml"
    if state:
        return paths.requests / state / filename
    return paths.requests / filename


def request_state_path(project_path: Path, request_id: str, state: str) -> Path:
    return cloud_queue_paths(project_path).requests / state / f"{request_id}.yaml"


def load_request(path: Path) -> CloudQueueRequest:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Request file must contain a YAML mapping: {path}")
    return CloudQueueRequest.from_dict(loaded)


def save_request(project_path: Path, request: CloudQueueRequest, allow_overwrite: bool = True) -> Path:
    ensure_cloud_queue_dirs(project_path)
    path = request_state_path(project_path, request.request_id, request.state)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not allow_overwrite:
        raise ValueError(f"Request already exists: {path}")
    path.write_text(yaml.safe_dump(request.to_dict(), sort_keys=False), encoding="utf-8")
    return path


def move_request(
    project_path: Path,
    request: CloudQueueRequest,
    new_state: str,
    allow_overwrite: bool = True,
) -> Path:
    new_path = request_state_path(project_path, request.request_id, new_state)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    if new_path.exists() and not allow_overwrite:
        raise ValueError(f"Request already exists in target state: {new_path}")
    old_state = request.prior_state or request.state
    old_path = request_path(project_path, request.request_id, old_state)
    if old_path.exists() and old_path != new_path:
        old_path.unlink()
    new_path.write_text(yaml.safe_dump(request.to_dict(), sort_keys=False), encoding="utf-8")
    return new_path


def load_requests(project_path: Path) -> list[tuple[Path, CloudQueueRequest]]:
    paths = ensure_cloud_queue_dirs(project_path)
    loaded: list[tuple[Path, CloudQueueRequest]] = []
    for state_dir in sorted(p for p in paths.requests.iterdir() if p.is_dir()):
        for file_path in sorted(state_dir.glob("*.yaml")):
            loaded.append((file_path, load_request(file_path)))
    return loaded


def append_audit_event(
    project_path: Path,
    event: CloudQueueAuditEvent,
    event_id_factory: AuditIdFactory | None = None,
) -> Path:
    paths = ensure_cloud_queue_dirs(project_path)
    audit_path = paths.audit_log
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    event_id = event.event_id or (event_id_factory() if event_id_factory else stable_event_id(event))
    normalized_event = CloudQueueAuditEvent(
        event_id=event_id,
        event_type=event.event_type,
        request_id=event.request_id,
        batch_id=event.batch_id,
        prior_state=event.prior_state,
        new_state=event.new_state,
        packet_checksum=event.packet_checksum,
        request_count=event.request_count,
        timestamp=event.timestamp,
        details=event.details,
    )
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized_event.to_dict(), sort_keys=True))
        handle.write("\n")
    return audit_path


def event_id_for(event: CloudQueueAuditEvent, event_id_factory: AuditIdFactory | None = None) -> str:
    return event.event_id or (event_id_factory() if event_id_factory else stable_event_id(event))


def read_audit_events(project_path: Path) -> list[dict[str, Any]]:
    paths = cloud_queue_paths(project_path)
    if not paths.audit_log.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in paths.audit_log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def checksum_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_event_id(event: CloudQueueAuditEvent) -> str:
    payload = "|".join(
        [
            event.event_type,
            event.request_id,
            event.batch_id,
            event.prior_state,
            event.new_state,
            event.packet_checksum,
            str(event.request_count),
            event.timestamp,
            json.dumps(event.details, sort_keys=True),
        ],
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
