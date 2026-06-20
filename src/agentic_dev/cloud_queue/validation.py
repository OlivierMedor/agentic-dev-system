from __future__ import annotations

import json
import math
import stat
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

import yaml
from yaml.tokens import AliasToken, TagToken

from agentic_dev.cloud_queue.models import (
    REQUEST_SCHEMA_VERSION,
    RESPONSE_SCHEMA_VERSION,
    CloudQueueRequest,
    CloudQueueResponse,
)
from agentic_dev.cloud_queue.redaction import is_sensitive_filename


MAX_ARCHIVE_ENTRIES = 256
MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
MAX_RESPONSE_BYTES = 512 * 1024
MAX_SINGLE_PATH_LENGTH = 240
MAX_EXPANSION_RATIO = 120.0
MAX_REQUESTS_PER_BATCH = 32


def normalize_request_id(request_id: str) -> str:
    request_id = request_id.strip()
    if not request_id:
        raise ValueError("Request ID cannot be empty.")
    if any(sep in request_id for sep in ("/", "\\", "..")):
        raise ValueError(f"Request ID cannot contain path separators: {request_id}")
    return request_id


def normalize_relative_path(relative_path: str) -> str:
    candidate = relative_path.replace("\\", "/")
    pure = PurePosixPath(candidate)
    if pure.is_absolute():
        raise ValueError(f"Absolute paths are not allowed: {relative_path}")
    if candidate.startswith(("/", "//")):
        raise ValueError(f"Absolute paths are not allowed: {relative_path}")
    if ":" in pure.parts[0] if pure.parts else False:
        raise ValueError(f"Drive-letter paths are not allowed: {relative_path}")
    normalized = pure.as_posix()
    if normalized.startswith("../") or "/../" in normalized or normalized == "..":
        raise ValueError(f"Path traversal is not allowed: {relative_path}")
    if len(normalized) > MAX_SINGLE_PATH_LENGTH:
        raise ValueError(f"Path is too long: {relative_path}")
    return normalized


def normalize_writable_paths(paths: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for path in paths:
        candidate = normalize_relative_path(path)
        if candidate in seen:
            raise ValueError(f"Duplicate writable path: {candidate}")
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def request_schema_is_valid(request: CloudQueueRequest) -> None:
    if request.request_schema_version != REQUEST_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported request schema version: {request.request_schema_version}.",
        )
    if request.response_schema_version != RESPONSE_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported response schema version: {request.response_schema_version}.",
        )
    normalize_request_id(request.request_id)
    normalize_writable_paths(request.writable_paths)


def response_schema_is_valid(data: dict[str, Any]) -> None:
    if int(data.get("response_schema_version", RESPONSE_SCHEMA_VERSION)) != RESPONSE_SCHEMA_VERSION:
        raise ValueError("Unsupported response schema version.")
    request_id = str(data.get("request_id", "")).strip()
    if not request_id:
        raise ValueError("Response must include request_id.")
    normalize_request_id(request_id)


def validate_file_bytes(path: Path, maximum_bytes: int = MAX_RESPONSE_BYTES) -> None:
    size = path.stat().st_size
    if size > maximum_bytes:
        raise ValueError(f"File exceeds maximum size of {maximum_bytes} bytes: {path}")


def validate_archive(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Archive does not exist: {path}")

    validate_file_bytes(path, MAX_ARCHIVE_BYTES)

    try:
        archive = ZipFile(path)
    except BadZipFile as error:
        raise ValueError(f"Archive is corrupt: {path}") from error

    with archive:
        infos = archive.infolist()
        if not infos:
            raise ValueError("Archive is empty.")
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise ValueError(f"Archive exceeds maximum entry count: {len(infos)}")

        total_uncompressed = 0
        seen_paths: set[str] = set()
        for info in infos:
            if info.is_dir():
                continue
            total_uncompressed += info.file_size
            if info.file_size == 0 and info.compress_size > 0:
                raise ValueError(f"Corrupt archive entry detected: {info.filename}")
            if info.file_size and info.compress_size:
                ratio = info.file_size / max(info.compress_size, 1)
                if ratio > MAX_EXPANSION_RATIO:
                    raise ValueError(f"Archive entry expands too much: {info.filename}")
            normalized = normalize_relative_path(info.filename)
            dedupe_key = normalized.lower()
            if dedupe_key in seen_paths:
                raise ValueError(f"Duplicate normalized archive path: {info.filename}")
            seen_paths.add(dedupe_key)
            if normalized.lower().endswith(".zip"):
                raise ValueError(f"Nested zip archives are not allowed: {info.filename}")
            mode = info.external_attr >> 16
            if mode:
                file_type = stat.S_IFMT(mode)
                if file_type in {
                    stat.S_IFLNK,
                    stat.S_IFCHR,
                    stat.S_IFBLK,
                    stat.S_IFIFO,
                    stat.S_IFSOCK,
                }:
                    raise ValueError(f"Unsupported archive entry type: {info.filename}")
            if is_sensitive_filename(normalized):
                continue
        if total_uncompressed > MAX_ARCHIVE_BYTES * 8:
            raise ValueError("Archive expands beyond the permitted total size.")


def ensure_json_or_yaml_text(content: bytes) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("File is not valid UTF-8.") from error
    if text.startswith("\ufeff"):
        raise ValueError("UTF-8 BOM is not allowed.")
    return text


def load_mapping_text(text: str) -> dict[str, Any]:
    for token in yaml.scan(text):
        if isinstance(token, AliasToken):
            raise ValueError("YAML aliases are not allowed.")
        if isinstance(token, TagToken):
            raise ValueError("YAML tags are not allowed.")
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValueError(f"YAML is invalid: {error}") from error

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("Response file must contain a mapping.")
    return loaded


def load_response_from_mapping(mapping: dict[str, Any], source_file: Path | None = None) -> CloudQueueResponse:
    response = CloudQueueResponse.from_dict(mapping, source_file=source_file)
    response_schema_is_valid(response.to_dict())
    return response


def load_json_mapping(content: str) -> dict[str, Any]:
    try:
        loaded = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON is invalid: {error}") from error
    if not isinstance(loaded, dict):
        raise ValueError("JSON response must contain an object.")
    return loaded


def ensure_request_count(requests: list[CloudQueueRequest]) -> None:
    if len(requests) > MAX_REQUESTS_PER_BATCH:
        raise ValueError(f"Batch exceeds maximum request count of {MAX_REQUESTS_PER_BATCH}.")


def path_exists_within(root: Path, relative_path: str) -> bool:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return False
    return candidate.exists()


def path_looks_safe(relative_path: str) -> bool:
    try:
        normalize_relative_path(relative_path)
    except ValueError:
        return False
    return not is_sensitive_filename(relative_path)


def compression_ratio(uncompressed: int, compressed: int) -> float:
    if compressed <= 0:
        return math.inf
    return uncompressed / compressed
