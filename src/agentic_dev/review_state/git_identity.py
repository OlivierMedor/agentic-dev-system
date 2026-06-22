from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Protocol

import yaml

from .models import HostIdentity, HostContainerParityReport, RepositoryIdentity


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def __call__(self, command: list[str], cwd: Path) -> CommandResult: ...


def run_git(command: list[str], cwd: Path) -> CommandResult:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _run(command: list[str], cwd: Path, command_runner: CommandRunner | None) -> str:
    result = (command_runner or run_git)(command, cwd)
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def _optional_run(command: list[str], cwd: Path, command_runner: CommandRunner | None) -> str | None:
    try:
        value = _run(command, cwd, command_runner)
    except ValueError:
        return None
    return value or None


def resolve_repository_identity(
    project_path: Path,
    requested_base_ref: str = "origin/main",
    command_runner: CommandRunner | None = None,
) -> RepositoryIdentity:
    project_path = project_path.resolve()
    try:
        _run(["git", "rev-parse", "--is-inside-work-tree"], project_path, command_runner)
    except ValueError as e:
        raise ValueError(f"Not a git repository (missing .git): {project_path}") from e

    root = Path(_run(["git", "rev-parse", "--show-toplevel"], project_path, command_runner))
    git_dir = Path(_run(["git", "rev-parse", "--git-dir"], project_path, command_runner))
    branch = _optional_run(["git", "branch", "--show-current"], project_path, command_runner)
    head_sha = _run(["git", "rev-parse", "HEAD"], project_path, command_runner)
    shallow_clone = _run(["git", "rev-parse", "--is-shallow-repository"], project_path, command_runner).lower() == "true"

    try:
        base_sha = _run(["git", "rev-parse", "--verify", requested_base_ref], project_path, command_runner)
    except ValueError as e:
        raise ValueError(f"Requested base ref '{requested_base_ref}' could not be resolved. Never silently substituting another base.") from e

    try:
        merge_base_sha = _run(["git", "merge-base", "HEAD", requested_base_ref], project_path, command_runner)
    except ValueError as e:
        raise ValueError(f"Could not find a merge base between HEAD and '{requested_base_ref}'.") from e

    remote_head_sha = _optional_run(["git", "rev-parse", "--verify", f"refs/remotes/{requested_base_ref}"], project_path, command_runner)
    detached_head = not bool(branch)

    return RepositoryIdentity(
        root=root,
        branch=branch,
        head_sha=head_sha,
        remote_head_sha=remote_head_sha,
        requested_base_ref=requested_base_ref,
        base_sha=base_sha,
        merge_base_sha=merge_base_sha,
        git_dir=git_dir,
        shallow_clone=shallow_clone,
        detached_head=detached_head,
        missing_remote=remote_head_sha is None,
        missing_base_ref=False,
    )


def load_host_identity(path: Path | None = None) -> HostIdentity | None:
    path = path or _default_host_identity_path()
    if path is None or not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    loaded: dict[str, object]
    if path.suffix.lower() == ".json":
        loaded = json.loads(text)
    else:
        loaded = yaml.safe_load(text) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Host identity file must be a mapping: {path}")
    return HostIdentity(
        root=Path(str(loaded["root"])) if loaded.get("root") else None,
        branch=str(loaded["branch"]) if loaded.get("branch") is not None else None,
        head_sha=str(loaded["head_sha"]) if loaded.get("head_sha") is not None else None,
        requested_base_ref=str(loaded["requested_base_ref"]) if loaded.get("requested_base_ref") is not None else None,
        base_sha=str(loaded["base_sha"]) if loaded.get("base_sha") is not None else None,
        merge_base_sha=str(loaded["merge_base_sha"]) if loaded.get("merge_base_sha") is not None else None,
        git_dir=Path(str(loaded["git_dir"])) if loaded.get("git_dir") else None,
        detached_head=loaded.get("detached_head"),
        shallow_clone=loaded.get("shallow_clone"),
    )


def _default_host_identity_path() -> Path | None:
    env_path = os.environ.get("AGENTIC_HOST_GIT_IDENTITY_FILE")
    return Path(env_path) if env_path else None


def compare_host_and_container_identity(
    container: RepositoryIdentity,
    host: HostIdentity | None,
) -> HostContainerParityReport:
    if host is None:
        return HostContainerParityReport(
            supplied=False,
            matched=False,
            status="not_checked",
            host=None,
            container=container,
        )

    mismatches: list[str] = []
    # Check for missing Git metadata in host
    if (
        host.head_sha is None
        or host.branch is None
        or host.base_sha is None
        or host.merge_base_sha is None
        or host.root is None
        or host.git_dir is None
    ):
        mismatches.append("missing Git metadata")

    # Check for wrong repository
    if host.root is not None and container.root is not None:
        if host.root.resolve() != container.root.resolve():
            mismatches.append("wrong repository")
    if host.git_dir is not None and container.git_dir is not None:
        if host.git_dir.resolve() != container.git_dir.resolve():
            mismatches.append("wrong repository")

    # Check for specific mismatches
    if host.head_sha is not None and host.head_sha != container.head_sha:
        mismatches.append("HEAD mismatch")
    if host.branch is not None and host.branch != container.branch:
        mismatches.append("branch mismatch")
    if host.base_sha is not None and host.base_sha != container.base_sha:
        mismatches.append("base mismatch")
    if host.merge_base_sha is not None and host.merge_base_sha != container.merge_base_sha:
        mismatches.append("merge-base mismatch")

    # Check detached head and shallow clone if specified
    if host.detached_head is not None and host.detached_head != container.detached_head:
        mismatches.append("detached HEAD mismatch")
    if host.shallow_clone is not None and host.shallow_clone != container.shallow_clone:
        mismatches.append("shallow clone mismatch")

    return HostContainerParityReport(
        supplied=True,
        matched=not mismatches,
        status="passed" if not mismatches else "failed",
        mismatches=mismatches,
        host=host,
        container=container,
    )


def identity_to_manifest(identity: RepositoryIdentity) -> dict[str, object]:
    return {
        "root": ".",
        "branch": identity.branch,
        "head_sha": identity.head_sha,
        "remote_head_sha": identity.remote_head_sha,
        "requested_base_ref": identity.requested_base_ref,
        "base_sha": identity.base_sha,
        "merge_base_sha": identity.merge_base_sha,
        "git_dir": ".git",
        "shallow_clone": identity.shallow_clone,
        "detached_head": identity.detached_head,
        "missing_remote": identity.missing_remote,
        "missing_base_ref": identity.missing_base_ref,
    }


def parity_report_to_manifest(report: HostContainerParityReport) -> dict[str, object]:
    return {
        "supplied": report.supplied,
        "matched": report.matched,
        "mismatches": report.mismatches,
        "host": None
        if report.host is None
        else {
            "root": "." if report.host.root is not None else None,
            "branch": report.host.branch,
            "head_sha": report.host.head_sha,
            "requested_base_ref": report.host.requested_base_ref,
            "base_sha": report.host.base_sha,
            "merge_base_sha": report.host.merge_base_sha,
            "git_dir": ".git" if report.host.git_dir is not None else None,
            "detached_head": report.host.detached_head,
            "shallow_clone": report.host.shallow_clone,
        },
        "container": identity_to_manifest(report.container) if report.container else None,
    }
