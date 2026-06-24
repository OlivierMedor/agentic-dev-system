from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Protocol

import yaml

from .models import HostIdentity, HostContainerParityReport, RepositoryIdentity


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def __call__(self, command: list[str], cwd: Path) -> CommandResult: ...


def run_git(command: list[str], cwd: Path) -> CommandResult:
    import os
    env = os.environ.copy()
    env["GIT_PAGER"] = "cat"
    env["PAGER"] = "cat"
    env["GIT_TERMINAL_PROMPT"] = "0"
    
    if command and command[0] == "git" and len(command) > 1 and command[1] != "--no-pager":
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
            timeout=60,
        )
        # Mocking a compatible return object
        class _Result:
            pass
        res = _Result()
        res.returncode = completed.returncode
        res.stdout = completed.stdout
        res.stderr = completed.stderr
        return res
    except subprocess.TimeoutExpired as e:
        stderr_msg = f"\nStderr: {e.stderr}" if e.stderr else ""
        raise RuntimeError(f"Git subprocess timed out after 60s in {cwd}: {' '.join(command)}{stderr_msg}") from e


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


def strip_credentials(url: str | None) -> str | None:
    if not url:
        return None
    import re
    url = url.strip().split('?')[0].split('#')[0]
    match = re.match(r'^([a-zA-Z0-9+-]+)://([^@/]+)@(.*)$', url)
    if match:
        proto, creds, rest = match.groups()
        return f"{proto}://{rest}"
    return url


def normalize_git_url(url: str | None) -> str | None:
    if not url:
        return None
    import re
    url = url.strip()
    
    # 1. Strip fragments and query parameters
    url = url.split('#')[0].split('?')[0]
    
    # Check for local path or file:// or localhost/127.0.0.1
    if not url or url.startswith("/") or url.startswith("\\") or re.match(r'^[a-zA-Z]:', url) or url.startswith("file://") or url.startswith("localhost") or url.startswith("127.0.0.1"):
        return None

    # 2. Check for SSH SCP-style syntax: e.g. git@github.com:owner/repo.git
    scp_match = re.match(r'^(?:([^@/]+)@)?([^:/]+):([^/].*)$', url)
    if scp_match and "://" not in url:
        user, host, path = scp_match.groups()
    else:
        # Standard URL parse
        proto_match = re.match(r'^([a-zA-Z0-9+-]+)://', url)
        if proto_match:
            proto = proto_match.group(1).lower()
            url_no_proto = url[len(proto) + 3:]
        else:
            url_no_proto = url
            
        # Strip credentials
        if "@" in url_no_proto:
            url_no_proto = url_no_proto.split("@", 1)[1]
            
        # Split host and path
        if "/" in url_no_proto:
            host_port, path = url_no_proto.split("/", 1)
        else:
            host_port, path = url_no_proto, ""
            
        host = host_port.split(":", 1)[0]
        
    host = host.lower()
    if host in ("github.com", "ssh.github.com"):
        host = "github.com"
        
    path = path.replace("\\", "/")
    path = re.sub(r'/+', '/', path).strip('/')
    
    if path.lower().endswith('.git'):
        path = path[:-4]
        
    known_insensitive_providers = ("github.com", "gitlab.com", "bitbucket.org")
    if host in known_insensitive_providers:
        path = path.lower()
        
    if not host:
        return None
        
    return f"{host}/{path}"


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

    remote_url = _optional_run(["git", "config", "--get", "remote.origin.url"], project_path, command_runner)
    if remote_url:
        remote_url = strip_credentials(remote_url)
        
    root_commits_output = _optional_run(["git", "rev-list", "--max-parents=0", "HEAD"], project_path, command_runner) or ""
    root_commit_shas = sorted(line.strip() for line in root_commits_output.splitlines() if line.strip())
        
    normalized_remote_url = normalize_git_url(remote_url)
    
    repository_id = None
    repository_id_strength = "none"
    repository_id_version = None
    
    from hashlib import sha256
    
    if root_commit_shas and normalized_remote_url:
        lines = ["repository-id-v1"]
        lines.extend(root_commit_shas)
        lines.append(normalized_remote_url)
        payload = "\n".join(lines)
        repository_id = sha256(payload.encode("utf-8")).hexdigest()
        repository_id_strength = "strong"
        repository_id_version = 1
    elif root_commit_shas:
        repository_id = root_commit_shas[0]
        repository_id_strength = "weak"
    elif normalized_remote_url:
        repository_id = normalized_remote_url
        repository_id_strength = "none"

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
        repository_id=repository_id,
        remote_url=remote_url,
        normalized_remote_url=normalized_remote_url,
        root_commit_shas=root_commit_shas,
        repository_id_strength=repository_id_strength,
        repository_id_version=repository_id_version,
    )


def validate_and_recompute_host_identity(loaded: dict[str, Any]) -> HostIdentity:
    # Helper to check if string looks like a git SHA (40 hex chars or 64 hex chars)
    def is_valid_sha(val: Any) -> bool:
        if not isinstance(val, str):
            return False
        import re
        return bool(re.match(r'^[a-fA-F0-9]{40}$', val) or re.match(r'^[a-fA-F0-9]{64}$', val))

    for field_name in ("head_sha", "base_sha", "merge_base_sha"):
        val = loaded.get(field_name)
        if val is not None and not is_valid_sha(val):
            raise ValueError(f"Invalid SHA format for {field_name}: {val}")

    root_shas = []
    if "root_commit_shas" in loaded:
        val = loaded["root_commit_shas"]
        if not isinstance(val, list):
            raise ValueError("root_commit_shas must be a list of strings")
        for s in val:
            if not is_valid_sha(s):
                raise ValueError(f"Invalid SHA format in root_commit_shas: {s}")
        root_shas = sorted(list(set(val)))
    elif "root_commit_sha" in loaded:
        val = loaded["root_commit_sha"]
        if val is not None:
            if not is_valid_sha(val):
                raise ValueError(f"Invalid SHA format for root_commit_sha: {val}")
            root_shas = [val]

    remote_url = loaded.get("remote_url")
    if remote_url is not None:
        if not isinstance(remote_url, str):
            raise ValueError("remote_url must be a string")
        remote_url = strip_credentials(remote_url)

    normalized_remote = normalize_git_url(remote_url)
    
    expected_id = None
    expected_strength = "none"
    expected_version = None
    
    from hashlib import sha256
    
    if root_shas and normalized_remote:
        lines = ["repository-id-v1"]
        lines.extend(root_shas)
        lines.append(normalized_remote)
        payload = "\n".join(lines)
        expected_id = sha256(payload.encode("utf-8")).hexdigest()
        expected_strength = "strong"
        expected_version = 1
    elif root_shas:
        expected_id = root_shas[0]
        expected_strength = "weak"
    elif normalized_remote:
        expected_id = normalized_remote
        expected_strength = "none"
        
    supplied_id = loaded.get("repository_id")
    if supplied_id is not None and supplied_id != expected_id:
        raise ValueError("supplied fingerprint inconsistent with component fields")
        
    supplied_strength = loaded.get("repository_id_strength")
    if supplied_strength is not None and supplied_strength != expected_strength:
        raise ValueError("supplied fingerprint inconsistent with component fields")

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
        repository_id=expected_id,
        remote_url=remote_url,
        normalized_remote_url=normalized_remote,
        root_commit_shas=root_shas,
        repository_id_strength=expected_strength,
        repository_id_version=expected_version,
    )


def load_host_identity(path: Path | None = None) -> HostIdentity | None:
    path = path or _default_host_identity_path()
    if path is None or not path.exists():
        return None
    text = path.read_text(encoding="utf-8-sig")
    loaded: dict[str, object]
    if path.suffix.lower() == ".json":
        loaded = json.loads(text)
    else:
        loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Host identity file must be a mapping: {path}")
    return validate_and_recompute_host_identity(loaded)


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
    ):
        mismatches.append("missing Git metadata")

    # Recompute/derive strengths if not set (for ad-hoc host/container objects in tests):
    host_strength = host.repository_id_strength
    if host_strength is None:
        has_id = bool(host.repository_id)
        has_remote = bool(host.remote_url or host.normalized_remote_url)
        if has_id and has_remote:
            host_strength = "strong"
        elif has_id:
            host_strength = "weak"
        else:
            host_strength = "none"

    container_strength = container.repository_id_strength
    if container_strength is None:
        has_id = bool(container.repository_id)
        has_remote = bool(container.remote_url or container.normalized_remote_url)
        if has_id and has_remote:
            container_strength = "strong"
        elif has_id:
            container_strength = "weak"
        else:
            container_strength = "none"

    # Define strict identity-strength policy
    # "strong: eligible to pass"
    # "weak: fail by default with weak repository identity"
    # "none: fail with missing repository metadata"
    if host_strength == "none" or container_strength == "none":
        mismatches.append("missing repository metadata")
        mismatches.append("missing fingerprint")
    elif host_strength == "weak" or container_strength == "weak":
        mismatches.append("weak repository identity")

    # Compare path-independent repository identity
    if host.repository_id != container.repository_id:
        mismatches.append("wrong repository")
    if host.normalized_remote_url != container.normalized_remote_url:
        mismatches.append("wrong repository")
    if host.root_commit_shas != container.root_commit_shas:
        mismatches.append("wrong repository")

    # Compare other Git state fields
    if host.head_sha is not None and host.head_sha != container.head_sha:
        mismatches.append("HEAD mismatch")
    if host.branch is not None and host.branch != container.branch:
        mismatches.append("branch mismatch")
    if host.base_sha is not None and host.base_sha != container.base_sha:
        mismatches.append("base mismatch")
    if host.merge_base_sha is not None and host.merge_base_sha != container.merge_base_sha:
        mismatches.append("merge-base mismatch")
    if host.detached_head is not None and host.detached_head != container.detached_head:
        mismatches.append("detached HEAD mismatch")
    if host.shallow_clone is not None and host.shallow_clone != container.shallow_clone:
        mismatches.append("shallow clone mismatch")

    return HostContainerParityReport(
        supplied=True,
        matched=not mismatches,
        status="passed" if not mismatches else "failed",
        mismatches=sorted(list(set(mismatches))),
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
        "repository_id": identity.repository_id,
        "remote_url": identity.remote_url,
        "normalized_remote_url": identity.normalized_remote_url,
        "root_commit_shas": identity.root_commit_shas,
        "repository_id_strength": identity.repository_id_strength,
        "repository_id_version": identity.repository_id_version,
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
            "repository_id": report.host.repository_id,
            "remote_url": report.host.remote_url,
            "normalized_remote_url": report.host.normalized_remote_url,
            "root_commit_shas": report.host.root_commit_shas,
            "repository_id_strength": report.host.repository_id_strength,
            "repository_id_version": report.host.repository_id_version,
        },
        "container": identity_to_manifest(report.container) if report.container else None,
    }
