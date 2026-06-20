from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from agentic_dev.cloud_queue.redaction import is_sensitive_filename, redact_path_fragment, redact_text
from agentic_dev.cloud_queue.validation import (
    ensure_json_or_yaml_text,
    load_mapping_text,
    normalize_relative_path,
    validate_archive,
)


def write_zip(path: Path, members: dict[str, bytes]) -> Path:
    with ZipFile(path, "w") as archive:
        for member_name, content in members.items():
            archive.writestr(member_name, content)
    return path


@pytest.mark.parametrize(
    "filename",
    [
        ".env",
        ".env.local",
        "config/.env.production",
        "ssh/id_rsa",
        "credentials.json",
    ],
)
def test_sensitive_filenames_are_detected(filename: str) -> None:
    assert is_sensitive_filename(filename) is True
    assert redact_path_fragment(filename) == "[REDACTED:FILENAME]"


@pytest.mark.parametrize(
    "filename",
    [
        "README.md",
        "docs/guide.md",
        "src/app.py",
    ],
)
def test_allowed_filenames_are_not_redacted(filename: str) -> None:
    assert is_sensitive_filename(filename) is False
    assert redact_path_fragment(filename) == filename


def test_redact_text_masks_common_secret_material() -> None:
    text = "\n".join(
        [
            "AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF",
            "Authorization: Bearer secret-token-value",
            "password = correct horse battery staple",
            "-----BEGIN PRIVATE KEY-----",
            "cookie: session=abc123",
        ],
    )

    redacted, summary = redact_text(text)

    assert "AKIA1234567890ABCDEF" not in redacted
    assert "secret-token-value" not in redacted
    assert "correct horse battery staple" not in redacted
    assert "BEGIN PRIVATE KEY" not in redacted
    assert "session=abc123" not in redacted
    assert summary.content_count >= 4
    assert summary.pattern_counts


@pytest.mark.parametrize(
    "relative_path",
    [
        "../escape.txt",
        "nested/../../escape.txt",
        "/absolute/path.txt",
        "//server/share.txt",
        "C:/windows/path.txt",
        "C:\\windows\\path.txt",
        "nested\\..\\escape.txt",
    ],
)
def test_relative_path_normalization_rejects_traversal_and_absolute_paths(relative_path: str) -> None:
    with pytest.raises(ValueError):
        normalize_relative_path(relative_path)


def test_yaml_aliases_and_tags_are_rejected() -> None:
    with pytest.raises(ValueError, match="YAML aliases are not allowed"):
        load_mapping_text("a: &anchor 1\nb: *anchor\n")
    with pytest.raises(ValueError, match="YAML tags are not allowed"):
        load_mapping_text("value: !!python/object/apply:os.system ['echo nope']\n")


def test_invalid_utf8_is_rejected() -> None:
    with pytest.raises(ValueError, match="not valid UTF-8"):
        ensure_json_or_yaml_text(b"\xff\xfe\xfa")


def test_validate_archive_rejects_empty_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "empty.zip"
    write_zip(archive_path, {})

    with pytest.raises(ValueError, match="Archive is empty"):
        validate_archive(archive_path)


def test_validate_archive_rejects_traversal_entries(tmp_path: Path) -> None:
    archive_path = write_zip(tmp_path / "traversal.zip", {"../escape.txt": b"oops"})

    with pytest.raises(ValueError, match="Path traversal is not allowed"):
        validate_archive(archive_path)


def test_validate_archive_rejects_absolute_and_drive_letter_entries(tmp_path: Path) -> None:
    absolute_archive = write_zip(tmp_path / "absolute.zip", {"/abs.txt": b"oops"})
    drive_archive = write_zip(tmp_path / "drive.zip", {"C:/abs.txt": b"oops"})

    with pytest.raises(ValueError, match="Absolute paths are not allowed"):
        validate_archive(absolute_archive)
    with pytest.raises(ValueError, match="Drive-letter paths are not allowed"):
        validate_archive(drive_archive)


def test_validate_archive_rejects_nested_zip_entries(tmp_path: Path) -> None:
    archive_path = write_zip(tmp_path / "nested.zip", {"nested/bundle.zip": b"nested"})

    with pytest.raises(ValueError, match="Nested zip archives are not allowed"):
        validate_archive(archive_path)


def test_validate_archive_rejects_duplicate_normalized_paths(tmp_path: Path) -> None:
    archive_path = write_zip(
        tmp_path / "duplicate.zip",
        {
            "request.yaml": b"a: 1\n",
            "REQUEST.yaml": b"a: 2\n",
        },
    )

    with pytest.raises(ValueError, match="Duplicate normalized archive path"):
        validate_archive(archive_path)


def test_validate_archive_rejects_nested_traversal_and_unsupported_unicode(tmp_path: Path) -> None:
    archive_path = write_zip(tmp_path / "backslash.zip", {"nested\\..\\escape.txt": b"oops"})

    with pytest.raises(ValueError):
        validate_archive(archive_path)

