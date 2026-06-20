from __future__ import annotations

from pathlib import Path

import yaml

from agentic_dev.cloud_queue.models import CloudQueueResponse
from agentic_dev.cloud_queue.persistence import ensure_cloud_queue_dirs


def imported_response_path(project_path: Path, request_id: str) -> Path:
    return ensure_cloud_queue_dirs(project_path).imports / f"{request_id}.yaml"


def save_imported_response(project_path: Path, response: CloudQueueResponse) -> Path:
    path = imported_response_path(project_path, response.request_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(response.to_dict(), sort_keys=False), encoding="utf-8")
    return path


def load_imported_response(project_path: Path, request_id: str) -> CloudQueueResponse:
    path = imported_response_path(project_path, request_id)
    if not path.exists():
        raise FileNotFoundError(f"Imported response does not exist: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Imported response must be a YAML mapping: {path}")
    return CloudQueueResponse.from_dict(loaded, source_file=path)

