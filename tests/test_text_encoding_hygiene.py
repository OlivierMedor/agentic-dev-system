from __future__ import annotations

from pathlib import Path


TEXT_SUFFIXES = {".md", ".py", ".txt", ".yaml", ".yml", ".json"}
INVISIBLE_CODEPOINTS = tuple(range(0x200B, 0x2010)) + tuple(range(0x202A, 0x202F)) + tuple(
    range(0x2060, 0x206A)
)
LF_REQUIRED_TEXT_FILES = (Path("scripts/install_codex_cli.sh"),)
SCANNED_PATHS = (
    Path("README.md"),
    Path("docs"),
    Path("src"),
    Path("tests"),
    Path("blueprints/blueprint.yaml"),
    Path("docs/cloud_queue_operator_guide.md"),
    Path("stories/structured-cloud-escalation-and-manual-packet-queue"),
    Path("stories/blueprint-defined-context-safe-subtask-execution"),
)


def test_tracked_text_files_do_not_contain_hidden_unicode_controls() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    violations: list[str] = []
    for candidate in SCANNED_PATHS:
        path = repo_root / candidate
        paths = [path] if path.is_file() else [child for child in path.rglob("*") if child.is_file()]
        for scanned in paths:
            if scanned.suffix.lower() not in TEXT_SUFFIXES:
                continue
            relative = scanned.relative_to(repo_root).as_posix()
            data = scanned.read_bytes()
            if data.startswith(b"\xef\xbb\xbf"):
                violations.append(f"{relative}: UTF-8 BOM at file start")

            content = data.decode("utf-8")
            for index, character in enumerate(content):
                codepoint = ord(character)
                if codepoint == 0xFEFF:
                    violations.append(f"{relative}: unexpected U+FEFF at character {index}")
                elif codepoint in INVISIBLE_CODEPOINTS:
                    violations.append(f"{relative}: hidden U+{codepoint:04X} at character {index}")

    assert violations == []


def test_docker_text_files_are_lf_only_and_shell_shebang_is_posix() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    violations: list[str] = []
    for candidate in LF_REQUIRED_TEXT_FILES:
        path = repo_root / candidate
        data = path.read_bytes()
        relative = path.relative_to(repo_root).as_posix()
        if data.startswith(b"\xef\xbb\xbf"):
            violations.append(f"{relative}: UTF-8 BOM at file start")
        if b"\r" in data:
            violations.append(f"{relative}: carriage return found")
        if candidate.name == "install_codex_cli.sh" and not data.startswith(b"#!/bin/sh\n"):
            violations.append(f"{relative}: expected exact '#!/bin/sh' shebang with LF")

    assert violations == []
