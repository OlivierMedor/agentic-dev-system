from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RepositoryIdentity:
    root: Path
    branch: str | None
    head_sha: str
    remote_head_sha: str | None
    requested_base_ref: str
    base_sha: str
    merge_base_sha: str
    git_dir: Path
    shallow_clone: bool
    detached_head: bool
    missing_remote: bool
    missing_base_ref: bool
    repository_id: str | None = None
    remote_url: str | None = None
    normalized_remote_url: str | None = None
    root_commit_shas: list[str] = field(default_factory=list)
    repository_id_strength: str | None = None
    repository_id_version: int | None = None

    @property
    def root_commit_sha(self) -> str | None:
        return self.root_commit_shas[0] if self.root_commit_shas else None


@dataclass(frozen=True)
class HostIdentity:
    root: Path | None
    branch: str | None
    head_sha: str | None
    requested_base_ref: str | None
    base_sha: str | None
    merge_base_sha: str | None
    git_dir: Path | None
    detached_head: bool | None = None
    shallow_clone: bool | None = None
    repository_id: str | None = None
    remote_url: str | None = None
    normalized_remote_url: str | None = None
    root_commit_shas: list[str] = field(default_factory=list)
    repository_id_strength: str | None = None
    repository_id_version: int | None = None

    @property
    def root_commit_sha(self) -> str | None:
        return self.root_commit_shas[0] if self.root_commit_shas else None


@dataclass(frozen=True)
class HostContainerParityReport:
    supplied: bool
    matched: bool
    status: str = "not_checked"
    mismatches: list[str] = field(default_factory=list)
    host: HostIdentity | None = None
    container: RepositoryIdentity | None = None


@dataclass(frozen=True)
class CommitRename:
    old_path: str
    new_path: str


@dataclass(frozen=True)
class CommittedDiffEvidence:
    commit_count: int
    changed_file_count: int
    paths: list[str]
    rename_paths: list[CommitRename]
    binary_files: list[str]
    diff_stat: str
    patch: str
    git_log: str
    patch_checksum: str
    paths_checksum: str
    git_log_checksum: str
    diff_stat_checksum: str


@dataclass(frozen=True)
class WorkingTreeEvidence:
    classification: str
    staged: list[str]
    unstaged: list[str]
    untracked: list[str]
    ignored: list[str]
    status: str
    status_checksum: str


@dataclass(frozen=True)
class NormalizationFinding:
    path: str
    classification: str
    repository_representation: str
    working_tree_representation: str
    git_attributes: list[str]
    original_checksums: dict[str, str]
    normalized_checksums: dict[str, str]
    reason: str
    kind: str | None = None
    change_status: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class FileModeFinding:
    path: str
    classification: str
    repository_mode: str
    working_tree_mode: str
    reason: str


@dataclass(frozen=True)
class ArtifactFinding:
    path: str
    category: str
    tracked: bool
    ignored: bool
    allowed: bool
    generated_during_invocation: bool
    reason: str


@dataclass(frozen=True)
class CleanlinessReport:
    classification: str
    staged: list[str]
    unstaged: list[str]
    untracked: list[str]
    ignored: list[str]
    normalization_only: list[str]
    file_mode_only: list[str]
    ambiguous: list[str]
    generated_artifacts: list[str]
    tracked_review_artifacts: list[str]
    tracked_runtime_artifacts: list[str]
    strict_blockers: list[str]


@dataclass(frozen=True)
class ReviewManifest:
    schema_version: int
    repository: dict[str, Any]
    committed_diff: dict[str, Any]
    working_tree: dict[str, Any]
    normalization: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    validation: dict[str, Any]
    integrity: dict[str, Any]
    host: dict[str, Any] | None = None

