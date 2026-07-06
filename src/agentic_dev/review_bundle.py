from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.runtime_config import resolve_project_base_ref


MAX_UNTRACKED_SNAPSHOT_BYTES = 100 * 1024
REVIEW_BUNDLE_SNAPSHOT_FILE = "review_bundle_snapshot.yaml"

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
    strict_clean_passed: bool


@dataclass(frozen=True)
class UntrackedSnapshotResult:
    untracked_files: list[str]
    captured_files: list[str]
    skipped_files: list[tuple[str, str]]


@dataclass(frozen=True)
class CommittedDiffMetadata:
    requested_base_ref: str
    resolved_base_ref: str
    base_sha: str
    head_sha: str
    resolution_command: str
    diff_command: str
    diff_stat_command: str
    changed_files_command: str


CommandRunner = Callable[[list[str], Path], CommandResult]


def run_command(command: list[str], cwd: Path) -> CommandResult:
    """Run a command and capture output without raising on failure."""
    import os
    env = os.environ.copy()
    
    if command and command[0] == "git":
        env["GIT_PAGER"] = "cat"
        env["PAGER"] = "cat"
        env["GIT_TERMINAL_PROMPT"] = "0"
        if len(command) > 1 and command[1] != "--no-pager":
            command = ["git", "--no-pager"] + command[1:]
            
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=env,
            stdin=subprocess.DEVNULL,
            timeout=300,
        )
        return CommandResult(
            command=" ".join(command),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except FileNotFoundError as e:
        return CommandResult(
            command=" ".join(command),
            returncode=127,
            stdout="",
            stderr=str(e),
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            command=" ".join(command),
            returncode=124,
            stdout="",
            stderr=f"Subprocess timed out after 60s in {cwd}: {' '.join(command)}",
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


def format_committed_diff_metadata(metadata: CommittedDiffMetadata) -> str:
    return "\n".join(
        [
            "# Committed PR Diff Metadata",
            "",
            f"Requested base ref: `{metadata.requested_base_ref}`",
            f"Resolved base ref: `{metadata.resolved_base_ref}`",
            f"Base SHA: `{metadata.base_sha}`",
            f"Head SHA: `{metadata.head_sha}`",
            f"Resolution command: `{metadata.resolution_command}`",
            f"Diff command: `{metadata.diff_command}`",
            f"Diff stat command: `{metadata.diff_stat_command}`",
            f"Changed files command: `{metadata.changed_files_command}`",
            "",
        ],
    )


def resolve_committed_diff_metadata(
    project_path: Path,
    base_ref: str,
    command_runner: CommandRunner,
    snapshot: dict[str, Any] | None = None,
) -> CommittedDiffMetadata:
    if snapshot is not None:
        metadata = snapshot.get("committed_diff_metadata")
        if isinstance(metadata, dict):
            requested_base_ref = str(metadata.get("requested_base_ref", base_ref))
            resolved_base_ref = str(metadata.get("resolved_base_ref", requested_base_ref))
            base_sha = str(metadata.get("base_sha", "")).strip()
            head_sha = str(metadata.get("head_sha", "")).strip()
            resolution_command = str(metadata.get("resolution_command", "")).strip()
            diff_command = str(metadata.get("diff_command", "")).strip()
            diff_stat_command = str(metadata.get("diff_stat_command", "")).strip()
            changed_files_command = str(metadata.get("changed_files_command", "")).strip()

            if base_sha and head_sha and resolution_command and diff_command and diff_stat_command and changed_files_command:
                return CommittedDiffMetadata(
                    requested_base_ref=requested_base_ref,
                    resolved_base_ref=resolved_base_ref,
                    base_sha=base_sha,
                    head_sha=head_sha,
                    resolution_command=resolution_command,
                    diff_command=diff_command,
                    diff_stat_command=diff_stat_command,
                    changed_files_command=changed_files_command,
                )

    candidate_refs = [base_ref]
    if base_ref != "main":
        candidate_refs.append("main")

    base_sha = ""
    resolved_base_ref = ""
    merge_base_command = ""
    for candidate_ref in candidate_refs:
        candidate_command = ["git", "merge-base", "HEAD", candidate_ref]
        merge_base_result = command_runner(candidate_command, project_path)
        if not merge_base_result.passed:
            continue

        base_sha = (
            merge_base_result.stdout.strip().splitlines()[0]
            if merge_base_result.stdout.strip()
            else ""
        )
        if base_sha:
            resolved_base_ref = candidate_ref
            merge_base_command = " ".join(candidate_command)
            break

    if not base_sha or not resolved_base_ref:
        attempted_commands = ", ".join(
            f"`git merge-base HEAD {candidate_ref}`" for candidate_ref in candidate_refs
        )
        raise ValueError(
            "Unable to resolve the committed PR diff base SHA with any of: "
            f"{attempted_commands}.",
        )

    head_command = ["git", "rev-parse", "HEAD"]
    head_result = command_runner(head_command, project_path)
    if not head_result.passed:
        raise ValueError(
            "Unable to resolve the current HEAD SHA with `git rev-parse HEAD`.",
        )

    head_sha = head_result.stdout.strip().splitlines()[0] if head_result.stdout.strip() else ""
    if not head_sha:
        raise ValueError("The current HEAD SHA command did not return a SHA.")

    return CommittedDiffMetadata(
        requested_base_ref=base_ref,
        resolved_base_ref=resolved_base_ref,
        base_sha=base_sha,
        head_sha=head_sha,
        resolution_command=merge_base_command,
        diff_command=f"git diff {base_sha}..HEAD",
        diff_stat_command=f"git diff --stat {base_sha}..HEAD",
        changed_files_command=f"git diff --name-only {base_sha}..HEAD",
    )


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def load_review_bundle_snapshot(story_path: Path) -> dict[str, Any] | None:
    snapshot_path = story_path / "reports" / REVIEW_BUNDLE_SNAPSHOT_FILE
    if not snapshot_path.exists():
        return None

    loaded = yaml.safe_load(snapshot_path.read_text(encoding="utf-8"))
    if loaded is None:
        return None

    if not isinstance(loaded, dict):
        raise ValueError(f"Review bundle snapshot must be a YAML mapping: {snapshot_path}")

    return loaded


def command_result_from_snapshot(
    command: list[str],
    snapshot_outputs: dict[str, Any],
    key: str,
) -> CommandResult:
    value = snapshot_outputs.get(key, {})
    if not isinstance(value, dict):
        value = {}

    return CommandResult(
        command=" ".join(command),
        returncode=int(value.get("returncode", 0)),
        stdout=str(value.get("stdout", "")),
        stderr=str(value.get("stderr", "")),
    )


def generate_handoff(
    story: str,
    project_path: Path,
    generated_files: list[Path],
    git_status: CommandResult,
    git_diff: CommandResult,
    git_diff_staged: CommandResult,
    committed_diff_metadata: CommittedDiffMetadata,
    committed_diff_stat: CommandResult,
    committed_diff_files: CommandResult,
    committed_diff_patch: CommandResult,
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
    committed_stat_changes = has_diff_output(committed_diff_stat)
    committed_file_list_changes = has_diff_output(committed_diff_files)
    committed_changes = has_diff_output(committed_diff_patch)
    committed_changed_file_count = len(
        [line for line in committed_diff_files.stdout.splitlines() if line.strip()],
    )

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

## Committed PR diff

- requested base ref: `{committed_diff_metadata.requested_base_ref}`
- resolved base ref: `{committed_diff_metadata.resolved_base_ref}`
- base sha: `{committed_diff_metadata.base_sha}`
- head sha: `{committed_diff_metadata.head_sha}`
- base resolution command: `{committed_diff_metadata.resolution_command}`
- diff command: `{committed_diff_metadata.diff_command}`
- diff stat command: `{committed_diff_metadata.diff_stat_command}`
- changed files command: `{committed_diff_metadata.changed_files_command}`
- changed file count: {committed_changed_file_count}
- committed diff stat present: {committed_stat_changes}
- committed file list present: {committed_file_list_changes}
- committed diff present: {committed_changes}

## Git status summary

{summarize_git_status(git_status.stdout)}

## Next recommended action

{next_action}
"""


@dataclass(frozen=True)
class ReviewBundleDiagnosticsResult:
    diagnostics_report: str
    identity: Any
    host_identity: Any
    parity_mismatches: list[str]
    cleanliness: Any


def create_review_bundle(
    project_path: Path,
    story: str,
    base_ref: str | None = None,
    command_runner: CommandRunner = run_command,
    strict_clean: bool = False,
    diagnose_git_state: bool = False,
    allow_generated_artifacts: bool = False,
    host_identity_file: Path | None = None,
) -> ReviewBundleResult | ReviewBundleDiagnosticsResult:
    from agentic_dev.review_state.service import (
        create_review_bundle as create_review_state_bundle,
        ReviewBundleDiagnosticsServiceResult,
    )

    resolved_base_ref = resolve_project_base_ref(project_path, base_ref)

    result = create_review_state_bundle(
        project_path,
        story,
        base_ref=resolved_base_ref,
        command_runner=command_runner,
        strict_clean=strict_clean,
        diagnose_git_state=diagnose_git_state,
        allow_generated_artifacts=allow_generated_artifacts,
        host_identity_file=host_identity_file,
    )

    if isinstance(result, ReviewBundleDiagnosticsServiceResult):
        return ReviewBundleDiagnosticsResult(
            diagnostics_report=result.diagnostics_report,
            identity=result.identity,
            host_identity=result.host_identity,
            parity_mismatches=result.parity_mismatches,
            cleanliness=result.cleanliness,
        )

    compatibility_paths = {
        "handoff.md",
        "git_status.txt",
        "git_log.txt",
        "git_diff_stat.txt",
        "git_diff_staged.patch",
        "git_diff.patch",
        "committed_diff_metadata.txt",
        "committed_diff_stat.txt",
        "committed_changed_files.txt",
        "committed_diff.patch",
        "untracked_files.txt",
        "untracked_file_contents.md",
        "skipped_untracked_files.txt",
        "pytest_output.txt",
        "ruff_output.txt",
        "file_tree.txt",
    }
    generated_files = [
        path
        for path in result.generated_files
        if path.relative_to(result.review_bundle_path).as_posix() in compatibility_paths
    ]
    return ReviewBundleResult(
        review_bundle_path=result.review_bundle_path,
        generated_files=generated_files,
        pytest_passed=result.pytest_passed,
        ruff_passed=result.ruff_passed,
        strict_clean_passed=result.strict_clean_passed,
    )
