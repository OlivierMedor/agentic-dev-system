from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml


CHECKSUM_ALGORITHM = "sha256"


def checksum_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def checksum_text(text: str) -> str:
    return checksum_bytes(text.encode("utf-8"))


def checksum_mapping(mapping: dict[str, Any]) -> str:
    return checksum_text(dump_yaml(mapping))


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=True, default_flow_style=False, allow_unicode=False, width=1000)


def load_yaml_mapping(text: str) -> dict[str, Any]:
    loaded = yaml.safe_load(text)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("Expected YAML mapping.")
    return loaded


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

