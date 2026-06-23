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
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def is_binary_content(data: bytes) -> bool:
    if b"\x00" in data[:8000]:
        return True
    return False


def generate_checksum_metadata(data: bytes, allow_canonical: bool = True) -> dict[str, Any]:
    is_bin = is_binary_content(data)
    byte_sha = checksum_bytes(data)
    if is_bin:
        return {
            "byte_sha256": byte_sha,
            "canonical_text_sha256": None,
            "content_type": "binary",
            "canonicalization": {
                "allowed": False
            }
        }
    else:
        try:
            text = data.decode("utf-8", errors="replace")
            normalized = text.replace("\r\n", "\n")
            canonical_sha = checksum_text(normalized)
        except Exception:
            canonical_sha = None
            
        allowed = allow_canonical and canonical_sha is not None
        return {
            "byte_sha256": byte_sha,
            "canonical_text_sha256": canonical_sha if allowed else None,
            "content_type": "text",
            "canonicalization": {
                "allowed": allowed,
                "line_endings": "lf" if allowed else None
            }
        }


def compute_checksum_info(data: bytes, is_binary: bool = False) -> dict[str, Any]:
    return generate_checksum_metadata(data, allow_canonical=not is_binary)

