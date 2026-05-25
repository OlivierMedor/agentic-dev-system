from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


MAX_UNTRACKED_SNAPSHOT_BYTES = 100 * 1024

EXCLUDED_TREE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "review_to_chatgpt",
}

EXCLUDED_UNTRACKED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "review_to_chatgpt",
    "review_bundle",
}


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class ReviewBundleResult:
    review_bundle_path: Path
    generated_files: list[Path]
    pytest_passed: bool
    ruff_passed: bool


@dataclass(frozen=True)
class UntrackedSnapshotResult:
    untracked_files: list[str]
    captured_files: list[str]
    skipped_files: list[tuple[str, str]]


CommandRunner = Callable[[list[str], Path], CommandResult]


def run_command(command: list[str], cwd: Path) -> CommandResult:
    """Run a command and capture output without raising on failure."""
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    return CommandResult(
        command=" ".join(command),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def build_file_tree(project_path: Path) -> str:
    """Build a simple file tree while skipping noisy local folders."""
    lines: list[str] = []

    for path in sorted(project_path.rglob("*")):
        relative_path = path.relative_to(project_path)
        parts = set(relative_path.parts)

        if parts.intersection(EXCLUDED_TREE_DIRS):
            continue

        prefix = "[D]" if path.is_dir() else "[F]"
        lines.append(f"{prefix} {relative_path.as_posix()}")

    return "\n".join(lines) + "\n"


def format_command_output(result: CommandResult) -> str:
    status = "PASSED" if result.passed else "FAILED"
    sections = [
        f"Command: {result.command}",
        f"Exit code: {result.returncode}",
        f"Status: {status}",
        "",
        "STDOUT:",
        result.stdout.rstrip(),
        "",
        "STDERR:",
        result.stderr.rstrip(),
        "",
    ]

    return "\n".join(sections)


def summarize_git_status(output: str) -> str:
    lines = [line for line in output.splitlines() if line.strip()]

    if not lines:
        return "Working tree clean."

    return f"{len(lines)} changed or untracked path(s)."


def has_diff_output(result: CommandResult) -> str:
    if not result.passed:
        return "unknown"

    if result.stdout.strip():
        return "yes"

    return "no"


def parse_untracked_files(result: CommandResult) -> list[str]:
    if not result.passed:
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def should_skip_untracked_file(relative_path: str, full_path: Path) -> str | None:
    parts = Path(relative_path).parts
    filename = parts[-1] if parts else relative_path
    lowercase_filename = filename.lower()

    if filename == ".env" or filename.startswith(".env."):
        return "potential secret file"

    if lowercase_filename.endswith(".zip") or lowercase_filename.endswith(".pyc"):
        return "excluded path"

    if any(part in EXCLUDED_UNTRACKED_DIRS for part in parts):
        return "excluded path"

    if not full_path.exists() or not full_path.is_file():
        return "binary or unreadable"

    if full_path.stat().st_size > MAX_UNTRACKED_SNAPSHOT_BYTES:
        return "file too large"

    return None


def is_binary_or_unreadable(path: Path) -> bool:
    try:
        content = path.read_bytes()
    except OSError:
        return True

    if b"\x00" in content:
        return True

    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return True

    return False


def build_untracked_snapshots(project_path: Path, untracked_files: list[str]) -> UntrackedSnapshotResult:
    captured_files: list[str] = []
    skipped_files: list[tuple[str, str]] = []

    for relative_path in untracked_files:
        full_path = project_path / relative_path
        skip_reason = should_skip_untracked_file(relative_path, full_path)

        if skip_reason is None and is_binary_or_unreadable(full_path):
            skip_reason = "binary or unreadable"

        if skip_reason is not None:
            skipped_files.append((relative_path, skip_reason))
            continue

        captured_files.append(relative_path)

    return UntrackedSnapshotResult(
        untracked_files=untracked_files,
        captured_files=captured_files,
        skipped_files=skipped_files,
    )


def format_untracked_file_list(result: CommandResult, untracked_files: list[str]) -> str:
    if not result.passed:
        return format_command_output(result)

    if not untracked_files:
        return "No untracked files found.\n"

    return "\n".join(untracked_files) + "\n"


def format_untracked_contents(
    project_path: Path,
    snapshot_result: UntrackedSnapshotResult,
) -> str:
    captured_sections: list[str] = ["# Untracked File Contents", ""]

    for relative_path in snapshot_result.captured_files:
        content = (project_path / relative_path).read_text(encoding="utf-8", errors="replace")
        captured_sections.extend(
            [
                f"## `{relative_path}`",
                "",
                "```text",
                content.rstrip(),
                "```",
                "",
            ],
        )

    if not snapshot_result.captured_files:
        captured_sections.append("No safe untracked text files were captured.")

    return "\n".join(captured_sections).rstrip() + "\n"


def format_skipped_untracked_files(skipped_files: list[tuple[str, str]]) -> str:
    if not skipped_files:
        return "No untracked files were skipped.\n"

    return "\n".join(f"{path}: {reason}" for path, reason in skipped_files) + "\n"


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def generate_handoff(
    story: str,
    project_path: Path,
    generated_files: list[Path],
    git_status: CommandResult,
    git_diff: CommandResult,
    git_diff_staged: CommandResult,
    pytest_result: CommandResult,
    ruff_result: CommandResult,
    untracked_snapshot: UntrackedSnapshotResult,
) -> str:
    pytest_status = "passed" if pytest_result.passed else "failed"
    ruff_status = "passed" if ruff_result.passed else "failed"
    untracked_count = len(untracked_snapshot.untracked_files)
    skipped_count = len(untracked_snapshot.skipped_files)
    staged_changes = has_diff_output(git_diff_staged)
    unstaged_changes = has_diff_output(git_diff)

    if pytest_result.passed and ruff_result.passed:
        next_action = "Review the bundle, then ask a human reviewer to approve or request changes."
    else:
        next_action = "Fix the failing checks, then regenerate the review bundle."

    generated_list = "\n".join(f"- `{path.name}`" for path in generated_files)

    return f"""# Review Bundle Handoff

## Story

{story}

## Project path

`{project_path}`

## Generated files

{generated_list}

## Validation

- pytest: {pytest_status}
- ruff: {ruff_status}
- untracked files: {untracked_count}
- skipped untracked files: {skipped_count}
- staged changes: {staged_changes}
- unstaged changes: {unstaged_changes}

## Git status summary

{summarize_git_status(git_status.stdout)}

## Next recommended action

{next_action}
"""


def create_review_bundle(
    project_path: Path,
    story: str,
    command_runner: CommandRunner = run_command,
) -> ReviewBundleResult:
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir(parents=True, exist_ok=True)

    commands = {
        "git_status.txt": ["git", "status", "--short"],
        "git_log.txt": ["git", "log", "--oneline", "-5"],
        "git_diff_stat.txt": ["git", "diff", "--stat"],
        "git_diff_staged.patch": ["git", "diff", "--cached"],
        "git_diff.patch": ["git", "diff"],
        "untracked_files.txt": ["git", "ls-files", "--others", "--exclude-standard"],
        "pytest_output.txt": ["pytest"],
        "ruff_output.txt": ["ruff", "check", "."],
    }

    results: dict[str, CommandResult] = {}
    generated_files: list[Path] = []

    for filename, command in commands.items():
        result = command_runner(command, project_path)
        results[filename] = result

        output_path = review_bundle_path / filename
        write_text(output_path, format_command_output(result))
        generated_files.append(output_path)

    untracked_files = parse_untracked_files(results["untracked_files.txt"])
    untracked_snapshot = build_untracked_snapshots(project_path, untracked_files)

    untracked_files_path = review_bundle_path / "untracked_files.txt"
    write_text(
        untracked_files_path,
        format_untracked_file_list(results["untracked_files.txt"], untracked_files),
    )

    untracked_contents_path = review_bundle_path / "untracked_file_contents.md"
    write_text(
        untracked_contents_path,
        format_untracked_contents(project_path, untracked_snapshot),
    )
    generated_files.append(untracked_contents_path)

    skipped_untracked_path = review_bundle_path / "skipped_untracked_files.txt"
    write_text(
        skipped_untracked_path,
        format_skipped_untracked_files(untracked_snapshot.skipped_files),
    )
    generated_files.append(skipped_untracked_path)

    file_tree_path = review_bundle_path / "file_tree.txt"
    write_text(file_tree_path, build_file_tree(project_path))
    generated_files.append(file_tree_path)

    handoff_path = review_bundle_path / "handoff.md"
    write_text(
        handoff_path,
        generate_handoff(
            story=story,
            project_path=project_path,
            generated_files=[handoff_path, *generated_files],
            git_status=results["git_status.txt"],
            git_diff=results["git_diff.patch"],
            git_diff_staged=results["git_diff_staged.patch"],
            pytest_result=results["pytest_output.txt"],
            ruff_result=results["ruff_output.txt"],
            untracked_snapshot=untracked_snapshot,
        ),
    )

    return ReviewBundleResult(
        review_bundle_path=review_bundle_path,
        generated_files=[handoff_path, *generated_files],
        pytest_passed=results["pytest_output.txt"].passed,
        ruff_passed=results["ruff_output.txt"].passed,
    )
