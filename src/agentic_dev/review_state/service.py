from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .git_identity import (
    HostIdentity,
    HostContainerParityReport,
    compare_host_and_container_identity,
    identity_to_manifest,
    load_host_identity,
    parity_report_to_manifest,
    resolve_repository_identity,
    run_git,
)
from .integrity import CHECKSUM_ALGORITHM, checksum_bytes, checksum_text, dump_yaml, load_yaml_mapping, write_text_file
from .models import (
    ArtifactFinding,
    CleanlinessReport,
    CommitRename,
    CommittedDiffEvidence,
    FileModeFinding,
    NormalizationFinding,
    RepositoryIdentity,
    ReviewManifest,
    WorkingTreeEvidence,
)


REVIEW_BUNDLE_DIRNAME = "review_bundle"
REVIEW_BUNDLE_MANIFEST = "manifest.yaml"


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def __call__(self, command: list[str], cwd: Path) -> CommandResult: ...


@dataclass(frozen=True)
class ReviewBundleServiceResult:
    review_bundle_path: Path
    generated_files: list[Path]
    pytest_passed: bool
    ruff_passed: bool
    identity: RepositoryIdentity
    host_identity: HostIdentity | None
    parity_mismatches: list[str]
    cleanliness: CleanlinessReport
    manifest_path: Path
    validation_report_path: Path


@dataclass(frozen=True)
class ReviewBundleValidation:
    valid: bool
    reasons: list[str]
    manifest: dict[str, Any] | None
    manifest_path: Path
    checksum_path: Path


@dataclass(frozen=True)
class _SimpleResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def _cmd(command_runner: CommandRunner, command: list[str], cwd: Path) -> _SimpleResult:
    result = command_runner(command, cwd)
    return _SimpleResult(" ".join(command), result.returncode, result.stdout, result.stderr)


def _ensure_story_path(project_path: Path, story: str) -> Path:
    story_path = project_path.resolve() / "stories" / story
    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")
    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")
    return story_path


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _run_text(command_runner: CommandRunner, command: list[str], cwd: Path, default: str = "") -> str:
    result = _cmd(command_runner, command, cwd)
    return result.stdout if result.returncode == 0 else default


def collect_committed_diff(project_path: Path, base_sha: str, head_sha: str, command_runner: CommandRunner) -> CommittedDiffEvidence:
    project_path = project_path.resolve()
    commit_count = int(_run_text(command_runner, ["git", "rev-list", "--count", f"{base_sha}..{head_sha}"], project_path, "0") or "0")
    git_log = _run_text(command_runner, ["git", "log", "--reverse", "--format=%H%x09%s", f"{base_sha}..{head_sha}"], project_path)
    paths_output = _run_text(command_runner, ["git", "diff", "--name-only", f"{base_sha}..{head_sha}"], project_path)
    stat_output = _run_text(command_runner, ["git", "diff", "--stat", f"{base_sha}..{head_sha}"], project_path)
    patch_output = _run_text(command_runner, ["git", "diff", "--binary", f"{base_sha}..{head_sha}"], project_path)
    summary_output = _run_text(command_runner, ["git", "diff", "--summary", f"{base_sha}..{head_sha}"], project_path)
    name_status_output = _run_text(command_runner, ["git", "diff", "--name-status", f"{base_sha}..{head_sha}"], project_path)

    paths = _split_lines(paths_output)
    rename_paths = []
    for line in _split_lines(name_status_output):
        parts = line.split("\t")
        if parts and parts[0].startswith("R") and len(parts) >= 3:
            rename_paths.append(CommitRename(old_path=parts[1], new_path=parts[2]))

    binary_files = [line.split("\t")[-1] for line in _split_lines(summary_output) if "binary" in line.lower()]
    return CommittedDiffEvidence(
        commit_count=commit_count,
        changed_file_count=len(paths),
        paths=paths,
        rename_paths=rename_paths,
        binary_files=binary_files,
        diff_stat=stat_output,
        patch=patch_output,
        git_log=git_log,
        patch_checksum=checksum_text(patch_output),
        paths_checksum=checksum_text("\n".join(paths) + ("\n" if paths else "")),
        git_log_checksum=checksum_text(git_log),
        diff_stat_checksum=checksum_text(stat_output),
    )


def collect_working_tree_evidence(project_path: Path, command_runner: CommandRunner) -> WorkingTreeEvidence:
    project_path = project_path.resolve()
    status_output = _run_text(command_runner, ["git", "status", "--short"], project_path)
    staged = _split_lines(_run_text(command_runner, ["git", "diff", "--cached", "--name-only"], project_path))
    unstaged = _split_lines(_run_text(command_runner, ["git", "diff", "--name-only"], project_path))
    untracked = _split_lines(_run_text(command_runner, ["git", "ls-files", "--others", "--exclude-standard"], project_path))
    ignored = _split_lines(_run_text(command_runner, ["git", "ls-files", "--others", "--ignored", "--exclude-standard"], project_path))
    classification = "clean" if not staged and not unstaged and not untracked else "dirty"
    return WorkingTreeEvidence(
        classification=classification,
        staged=sorted(set(staged)),
        unstaged=sorted(set(unstaged)),
        untracked=sorted(set(untracked)),
        ignored=sorted(set(ignored)),
        status=status_output,
        status_checksum=checksum_text(status_output),
    )


def classify_normalization(project_path: Path, paths: list[str], command_runner: CommandRunner) -> list[NormalizationFinding]:
    project_path = project_path.resolve()
    findings: list[NormalizationFinding] = []
    for relative_path in sorted(set(paths)):
        file_path = project_path / relative_path
        
        is_deleted = not file_path.exists()
        repo_res = command_runner(["git", "show", f"HEAD:{relative_path}"], project_path)
        is_added = repo_res.returncode != 0

        if is_deleted:
            findings.append(
                NormalizationFinding(
                    path=relative_path,
                    classification="deleted",
                    repository_representation="text",
                    working_tree_representation="none",
                    git_attributes=_split_lines(_run_text(command_runner, ["git", "check-attr", "-a", "--", relative_path], project_path)),
                    original_checksums={"repository": "", "working_tree": ""},
                    normalized_checksums={"repository": "", "working_tree": ""},
                    reason="deleted file",
                )
            )
            continue

        if is_added:
            working_bytes = file_path.read_bytes()
            is_binary = b"\x00" in working_bytes[:8000]
            findings.append(
                NormalizationFinding(
                    path=relative_path,
                    classification="binary" if is_binary else "added",
                    repository_representation="none",
                    working_tree_representation="binary" if is_binary else "text",
                    git_attributes=_split_lines(_run_text(command_runner, ["git", "check-attr", "-a", "--", relative_path], project_path)),
                    original_checksums={"repository": "", "working_tree": checksum_bytes(working_bytes)},
                    normalized_checksums={"repository": "", "working_tree": checksum_bytes(working_bytes)},
                    reason="binary file" if is_binary else "added file",
                )
            )
            continue

        # Exists in both HEAD and working tree
        working_bytes = file_path.read_bytes()
        is_binary_work = b"\x00" in working_bytes[:8000]
        
        repo_bytes = repo_res.stdout.encode("utf-8", errors="surrogateescape")
        is_binary_repo = b"\x00" in repo_bytes[:8000]

        if is_binary_work or is_binary_repo:
            findings.append(
                NormalizationFinding(
                    path=relative_path,
                    classification="binary",
                    repository_representation="binary",
                    working_tree_representation="binary",
                    git_attributes=_split_lines(_run_text(command_runner, ["git", "check-attr", "-a", "--", relative_path], project_path)),
                    original_checksums={"repository": checksum_bytes(repo_bytes), "working_tree": checksum_bytes(working_bytes)},
                    normalized_checksums={"repository": checksum_bytes(repo_bytes), "working_tree": checksum_bytes(working_bytes)},
                    reason="binary file",
                )
            )
            continue

        repo_text = repo_res.stdout
        work_text = working_bytes.decode("utf-8", errors="replace")

        if repo_text == work_text:
            continue

        repo_has_bom = repo_text.startswith("\ufeff")
        work_has_bom = work_text.startswith("\ufeff")

        repo_no_bom = repo_text.lstrip("\ufeff")
        work_no_bom = work_text.lstrip("\ufeff")

        repo_norm_le = repo_no_bom.replace("\r\n", "\n").replace("\r", "\n")
        work_norm_le = work_no_bom.replace("\r\n", "\n").replace("\r", "\n")

        repo_final = repo_norm_le[:-1] if repo_norm_le.endswith("\n") else repo_norm_le
        work_final = work_norm_le[:-1] if work_norm_le.endswith("\n") else work_norm_le

        if repo_final == work_final:
            diffs = []
            if repo_has_bom != work_has_bom:
                diffs.append("bom")
            if ("\r\n" in repo_text) != ("\r\n" in work_text) or ("\r" in repo_text) != ("\r" in work_text):
                diffs.append("line-ending")
            if repo_text.endswith("\n") != work_text.endswith("\n"):
                diffs.append("final-newline")

            if "line-ending" in diffs or not diffs:
                classification = "line-ending-only"
                reason = "CRLF versus LF only"
            elif "bom" in diffs:
                classification = "bom-only"
                reason = "UTF-8 BOM only"
            else:
                classification = "final-newline-only"
                reason = "final newline only"
        else:
            classification = "mixed-normalization-and-content-change"
            reason = "normalization plus real content change"

        findings.append(
            NormalizationFinding(
                path=relative_path,
                classification=classification,
                repository_representation=_describe_text(repo_text),
                working_tree_representation=_describe_text(work_text),
                git_attributes=_split_lines(_run_text(command_runner, ["git", "check-attr", "-a", "--", relative_path], project_path)),
                original_checksums={"repository": checksum_text(repo_text), "working_tree": checksum_text(work_text)},
                normalized_checksums={"repository": checksum_text(repo_final), "working_tree": checksum_text(work_final)},
                reason=reason,
            ),
        )
    return findings


def classify_file_modes(project_path: Path, paths: list[str], command_runner: CommandRunner) -> list[FileModeFinding]:
    project_path = project_path.resolve()
    findings: list[FileModeFinding] = []
    for relative_path in sorted(set(paths)):
        summary = _run_text(command_runner, ["git", "diff", "--summary", "--", relative_path], project_path)
        if "mode change" in summary:
            parts = summary.split()
            try:
                repo_mode = parts[2]
                working_tree_mode = parts[4]
            except Exception:
                repo_mode = "100644"
                working_tree_mode = "100755"
            content_diff = _run_text(command_runner, ["git", "diff", "-U0", "--", relative_path], project_path)
            has_content_changes = False
            for line in content_diff.splitlines():
                if (line.startswith("+") and not line.startswith("+++")) or (line.startswith("-") and not line.startswith("---")):
                    has_content_changes = True
                    break
            if not has_content_changes:
                findings.append(
                    FileModeFinding(
                        path=relative_path,
                        classification="executable-bit-only",
                        repository_mode=repo_mode,
                        working_tree_mode=working_tree_mode,
                        reason="executable bit changed without content change",
                    ),
                )
    return findings


def classify_generated_artifact_path(path: str) -> str | None:
    normalized = path.replace("\\", "/").strip("/")
    if normalized.startswith("stories/") and "/review_bundle/" in normalized:
        return "review_bundle"
    if normalized.startswith("stories/") and "/cloud_review_packet/" in normalized:
        return "cloud_review_packet"
    if normalized.startswith("stories/") and "/remote_dev_validation/" in normalized:
        return "remote_dev_validation"
    if normalized.startswith(".agentic/cloud_batches/"):
        return "cloud_batch_runtime"
    if normalized.startswith(".agentic/cloud_queue/"):
        return "cloud_queue_runtime"
    if normalized.startswith(".agentic/cloud_applications/") or normalized.startswith(".agentic/runtime_plans/") or normalized.startswith(".agentic/execution_leases/"):
        return "cloud_application_runtime"
    if normalized.startswith(".agentic/support_queue/"):
        return "support_queue_runtime"
    if normalized.startswith("review_to_chatgpt/"):
        return "review_to_chatgpt"
    if normalized.endswith(".zip"):
        return "zip"
    return None


def classify_artifacts(tracked_files: list[str], untracked_files: list[str], generated_paths: list[str] | None = None) -> list[ArtifactFinding]:
    generated = set(path.replace("\\", "/").strip("/") for path in (generated_paths or []))
    findings: list[ArtifactFinding] = []
    for gen_path in sorted(generated):
        category = classify_generated_artifact_path(gen_path)
        if category:
            findings.append(
                ArtifactFinding(
                    path=gen_path,
                    category=category,
                    tracked=False,
                    ignored=True,
                    allowed=True,
                    generated_during_invocation=True,
                    reason=f"{category} artifact is generated during invocation",
                )
            )
    for tracked in tracked_files:
        if tracked in generated:
            continue
        category = classify_generated_artifact_path(tracked)
        if category:
            findings.append(
                ArtifactFinding(
                    path=tracked.replace("\\", "/").strip("/"),
                    category=category,
                    tracked=True,
                    ignored=False,
                    allowed=False,
                    generated_during_invocation=False,
                    reason=f"{category} artifact is tracked",
                ),
            )
    for untracked in untracked_files:
        if untracked in generated:
            continue
        category = classify_generated_artifact_path(untracked)
        if category:
            findings.append(
                ArtifactFinding(
                    path=untracked.replace("\\", "/").strip("/"),
                    category=category,
                    tracked=False,
                    ignored=True,
                    allowed=True,
                    generated_during_invocation=False,
                    reason=f"{category} artifact is ignored",
                ),
            )
    return findings


def derive_cleanliness(
    staged: list[str],
    unstaged: list[str],
    untracked: list[str],
    ignored: list[str],
    normalization_only: list[str],
    file_mode_only: list[str],
    ambiguous: list[str],
    generated_artifacts: list[str],
    tracked_review_artifacts: list[str],
    tracked_runtime_artifacts: list[str],
) -> CleanlinessReport:
    classification = "clean"
    strict_blockers: list[str] = []
    if ambiguous:
        classification = "ambiguous"
        strict_blockers.extend(ambiguous)
    elif tracked_review_artifacts or tracked_runtime_artifacts:
        classification = "dirty"
        strict_blockers.extend(tracked_review_artifacts)
        strict_blockers.extend(tracked_runtime_artifacts)
    else:
        real_staged = [p for p in staged if p not in normalization_only and p not in file_mode_only]
        real_unstaged = [p for p in unstaged if p not in normalization_only and p not in file_mode_only]
        if real_staged or real_unstaged or untracked:
            classification = "dirty"
        elif normalization_only or file_mode_only:
            classification = "normalization_noise_only"
        elif generated_artifacts:
            classification = "clean_with_generated_artifacts"

    return CleanlinessReport(
        classification=classification,
        staged=sorted(set(staged)),
        unstaged=sorted(set(unstaged)),
        untracked=sorted(set(untracked)),
        ignored=sorted(set(ignored)),
        normalization_only=sorted(set(normalization_only)),
        file_mode_only=sorted(set(file_mode_only)),
        ambiguous=sorted(set(ambiguous)),
        generated_artifacts=sorted(set(generated_artifacts)),
        tracked_review_artifacts=sorted(set(tracked_review_artifacts)),
        tracked_runtime_artifacts=sorted(set(tracked_runtime_artifacts)),
        strict_blockers=sorted(set(strict_blockers)),
    )


def build_review_manifest(
    repository: RepositoryIdentity,
    committed_diff: CommittedDiffEvidence,
    working_tree: WorkingTreeEvidence,
    normalization: list[NormalizationFinding],
    artifacts: list[ArtifactFinding],
    parity: HostContainerParityReport,
    strict_clean_passed: bool,
) -> ReviewManifest:
    payload = {
        "schema_version": 1,
        "repository": identity_to_manifest(repository),
        "committed_diff": {
            "commit_count": committed_diff.commit_count,
            "changed_file_count": committed_diff.changed_file_count,
            "paths": committed_diff.paths,
            "rename_paths": [{"old_path": r.old_path, "new_path": r.new_path} for r in committed_diff.rename_paths],
            "binary_files": committed_diff.binary_files,
            "patch_checksum": committed_diff.patch_checksum,
            "paths_checksum": committed_diff.paths_checksum,
            "git_log_checksum": committed_diff.git_log_checksum,
            "diff_stat_checksum": committed_diff.diff_stat_checksum,
        },
        "working_tree": {
            "classification": working_tree.classification,
            "staged": working_tree.staged,
            "unstaged": working_tree.unstaged,
            "untracked": working_tree.untracked,
            "ignored": working_tree.ignored,
        },
        "normalization": [finding.__dict__ for finding in normalization],
        "artifacts": [finding.__dict__ for finding in artifacts],
        "validation": {
            "host_container_git_match": parity.matched,
            "requested_base_resolved": bool(repository.base_sha),
            "merge_base_resolved": bool(repository.merge_base_sha),
            "strict_clean_passed": strict_clean_passed,
        },
    }
    manifest_checksum = checksum_text(dump_yaml(payload))
    payload["integrity"] = {"algorithm": CHECKSUM_ALGORITHM, "manifest_checksum": manifest_checksum}
    return ReviewManifest(
        schema_version=1,
        repository=payload["repository"],
        committed_diff=payload["committed_diff"],
        working_tree=payload["working_tree"],
        normalization=payload["normalization"],
        artifacts=payload["artifacts"],
        validation=payload["validation"],
        integrity=payload["integrity"],
    )


def validate_review_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported review manifest schema version.")
    if "repository" not in manifest or "committed_diff" not in manifest:
        raise ValueError("Review manifest is missing required sections.")


def format_diagnostics_report(
    identity: RepositoryIdentity,
    parity: HostContainerParityReport,
    working_tree: WorkingTreeEvidence,
    normalization: list[NormalizationFinding],
    file_modes: list[FileModeFinding],
    artifacts: list[ArtifactFinding],
    cleanliness: CleanlinessReport,
) -> str:
    lines = [
        "# Review Bundle Diagnostics",
        "",
        f"- branch: {identity.branch or '(detached)'}",
        f"- head_sha: {identity.head_sha}",
        f"- requested_base_ref: {identity.requested_base_ref}",
        f"- base_sha: {identity.base_sha}",
        f"- merge_base_sha: {identity.merge_base_sha}",
        f"- shallow_clone: {identity.shallow_clone}",
        f"- detached_head: {identity.detached_head}",
        f"- parity_matched: {parity.matched}",
        f"- staged: {len(working_tree.staged)}",
        f"- unstaged: {len(working_tree.unstaged)}",
        f"- untracked: {len(working_tree.untracked)}",
        f"- ignored: {len(working_tree.ignored)}",
        f"- normalization_only: {len(normalization)}",
        f"- file_mode_only: {len(file_modes)}",
        f"- artifacts: {len(artifacts)}",
        f"- classification: {cleanliness.classification}",
    ]
    if parity.mismatches:
        lines.extend(["", "## Parity mismatches", *[f"- {item}" for item in parity.mismatches]])
    if cleanliness.strict_blockers:
        lines.extend(["", "## Strict blockers", *[f"- {item}" for item in cleanliness.strict_blockers]])
    return "\n".join(lines) + "\n"


def _normalize_text(text: str) -> str:
    return _strip_final_newline(text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff"))


def _strip_bom(text: str) -> str:
    return text.lstrip("\ufeff")


def _strip_final_newline(text: str) -> str:
    return text[:-1] if text.endswith("\n") else text


def _describe_text(text: str) -> str:
    return "utf-8-bom-lf" if text.startswith("\ufeff") else "utf-8-lf"


def _build_command_result(command: str, stdout: str, returncode: int = 0, stderr: str = "") -> _SimpleResult:
    return _SimpleResult(command=command, returncode=returncode, stdout=stdout, stderr=stderr)


def _format_command_output(command: str, stdout: str, returncode: int = 0, stderr: str = "") -> str:
    result = _build_command_result(command, stdout, returncode, stderr)
    status = "PASSED" if result.passed else "FAILED"
    return "\n".join(
        [
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
        ],
    )


def _load_review_bundle_helpers():
    from agentic_dev.review_bundle import (
        CommittedDiffMetadata,
        build_file_tree,
        build_untracked_snapshots,
        format_committed_diff_metadata,
        format_skipped_untracked_files,
        format_untracked_contents,
        format_untracked_file_list,
        generate_handoff,
    )

    return {
        "CommittedDiffMetadata": CommittedDiffMetadata,
        "build_file_tree": build_file_tree,
        "build_untracked_snapshots": build_untracked_snapshots,
        "format_committed_diff_metadata": format_committed_diff_metadata,
        "format_skipped_untracked_files": format_skipped_untracked_files,
        "format_untracked_contents": format_untracked_contents,
        "format_untracked_file_list": format_untracked_file_list,
        "generate_handoff": generate_handoff,
    }


def create_review_bundle(
    project_path: Path,
    story: str,
    base_ref: str = "origin/main",
    command_runner: CommandRunner = run_git,
    strict_clean: bool = False,
    diagnose_git_state: bool = False,
    allow_generated_artifacts: bool = False,
    host_identity_file: Path | None = None,
) -> ReviewBundleServiceResult:
    project_path = project_path.resolve()
    story_path = _ensure_story_path(project_path, story)
    review_bundle_path = story_path / REVIEW_BUNDLE_DIRNAME
    review_bundle_path.mkdir(parents=True, exist_ok=True)

    identity = resolve_repository_identity(project_path, requested_base_ref=base_ref, command_runner=command_runner)
    host_identity = load_host_identity(host_identity_file)
    parity = compare_host_and_container_identity(identity, host_identity)

    # 1. Capture working tree BEFORE generating any files (Pre-generation)
    working_tree = collect_working_tree_evidence(project_path, command_runner)
    committed_diff = collect_committed_diff(project_path, identity.merge_base_sha, identity.head_sha, command_runner)

    tracked_files = _split_lines(_run_text(command_runner, ["git", "ls-files"], project_path))
    untracked_files = _split_lines(_run_text(command_runner, ["git", "ls-files", "--others", "--exclude-standard"], project_path))
    ignored_files = _split_lines(_run_text(command_runner, ["git", "ls-files", "--others", "--ignored", "--exclude-standard"], project_path))
    staged_raw = _cmd(command_runner, ["git", "diff", "--cached"], project_path)
    unstaged_raw = _cmd(command_runner, ["git", "diff"], project_path)
    staged_diff = _build_command_result("git diff --cached", staged_raw.stdout, staged_raw.returncode, staged_raw.stderr)
    unstaged_diff = _build_command_result("git diff", unstaged_raw.stdout, unstaged_raw.returncode, unstaged_raw.stderr)

    # 2. Exclude files we are about to generate from cleanliness check
    generated_relative_paths = []
    review_bundle_files = [
        REVIEW_BUNDLE_MANIFEST,
        "repository_identity.yaml",
        "host_container_parity.yaml",
        "committed/git_log.txt",
        "committed/changed_paths.txt",
        "committed/diff_stat.txt",
        "committed/patch.diff",
        "committed/binary_files.yaml",
        "working_tree/status.yaml",
        "working_tree/staged.patch",
        "working_tree/unstaged.patch",
        "working_tree/untracked.yaml",
        "working_tree/ignored.yaml",
        "normalization/report.yaml",
        "artifacts/report.yaml",
        "validation/pytest_output.txt",
        "validation/ruff_output.txt",
        "validation/checksums.yaml",
        "validation/diagnostics.md",
        # Legacy compatibility files
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
    ]
    for filename in review_bundle_files:
        generated_relative_paths.append(f"stories/{story}/review_bundle/{filename}")

    gen_set = set(generated_relative_paths)
    staged_filtered = [p for p in working_tree.staged if p not in gen_set]
    unstaged_filtered = [p for p in working_tree.unstaged if p not in gen_set]
    untracked_filtered = [p for p in working_tree.untracked if p not in gen_set]
    ignored_filtered = [p for p in working_tree.ignored if p not in gen_set]

    normalization_paths = sorted(set(staged_filtered + unstaged_filtered))
    normalization = classify_normalization(project_path, normalization_paths, command_runner)
    file_modes = classify_file_modes(project_path, normalization_paths, command_runner)
    artifacts = classify_artifacts(
        [p for p in tracked_files if p not in gen_set],
        [p for p in untracked_files if p not in gen_set] + [p for p in ignored_files if p not in gen_set],
        generated_paths=generated_relative_paths
    )

    tracked_review_artifacts = [item.path for item in artifacts if item.tracked and item.category in {"review_bundle", "cloud_review_packet", "remote_dev_validation"}]
    tracked_runtime_artifacts = [item.path for item in artifacts if item.tracked and item.category.endswith("runtime")]
    generated_artifacts = [item.path for item in artifacts if item.generated_during_invocation]

    cleanliness = derive_cleanliness(
        staged=staged_filtered,
        unstaged=unstaged_filtered,
        untracked=untracked_filtered,
        ignored=ignored_filtered,
        normalization_only=[finding.path for finding in normalization if finding.classification in {"line-ending-only", "bom-only", "final-newline-only"}],
        file_mode_only=[finding.path for finding in file_modes],
        ambiguous=[finding.path for finding in normalization if finding.classification == "mixed-normalization-and-content-change"],
        generated_artifacts=generated_artifacts,
        tracked_review_artifacts=tracked_review_artifacts,
        tracked_runtime_artifacts=tracked_runtime_artifacts,
    )

    # 3. Handle strict clean checks
    if strict_clean:
        rejections = []
        if cleanliness.classification == "dirty":
            rejections.append("repository is dirty")
        if cleanliness.classification == "ambiguous":
            rejections.append("repository cleanliness is ambiguous")
        if tracked_review_artifacts:
            rejections.append(f"tracked review artifacts: {', '.join(tracked_review_artifacts)}")
        if tracked_runtime_artifacts:
            rejections.append(f"tracked runtime artifacts: {', '.join(tracked_runtime_artifacts)}")
        if host_identity is not None and not parity.matched:
            rejections.append(f"host/container parity mismatch: {', '.join(parity.mismatches)}")
        
        if rejections:
            raise ValueError("Strict review bundle generation failed: " + "; ".join(rejections))

    # 4. Handle diagnose git state (Read-only mode)
    if diagnose_git_state:
        report = format_diagnostics_report(identity, parity, working_tree, normalization, file_modes, artifacts, cleanliness)
        print(report, end="")
        return ReviewBundleServiceResult(
            review_bundle_path=review_bundle_path,
            generated_files=[],
            pytest_passed=True,
            ruff_passed=True,
            identity=identity,
            host_identity=host_identity,
            parity_mismatches=parity.mismatches,
            cleanliness=cleanliness,
            manifest_path=review_bundle_path / REVIEW_BUNDLE_MANIFEST,
            validation_report_path=review_bundle_path / "validation" / "diagnostics.md",
        )

    # Post-generation: Generate artifacts and checksums
    strict_clean_passed = cleanliness.classification not in {"dirty", "ambiguous"} and not cleanliness.strict_blockers
    if host_identity is not None:
        strict_clean_passed = strict_clean_passed and parity.matched

    manifest = build_review_manifest(identity, committed_diff, working_tree, normalization, artifacts, parity, strict_clean_passed=strict_clean_passed)
    manifest_text = dump_yaml(
        {
            "schema_version": manifest.schema_version,
            "repository": manifest.repository,
            "committed_diff": manifest.committed_diff,
            "working_tree": manifest.working_tree,
            "normalization": manifest.normalization,
            "artifacts": manifest.artifacts,
            "validation": manifest.validation,
            "integrity": manifest.integrity,
        },
    )

    helpers = _load_review_bundle_helpers()
    untracked_snapshot = helpers["build_untracked_snapshots"](project_path, untracked_filtered)
    pytest_result = _cmd(command_runner, ["pytest"], project_path)
    ruff_result = _cmd(command_runner, ["ruff", "check", "."], project_path)
    committed_metadata = helpers["CommittedDiffMetadata"](
        requested_base_ref=identity.requested_base_ref,
        resolved_base_ref=identity.requested_base_ref,
        base_sha=identity.base_sha,
        head_sha=identity.head_sha,
        resolution_command=f"git merge-base HEAD {identity.requested_base_ref}",
        diff_command=f"git diff {identity.base_sha}..HEAD",
        diff_stat_command=f"git diff --stat {identity.base_sha}..HEAD",
        changed_files_command=f"git diff --name-only {identity.base_sha}..HEAD",
    )
    compatibility = {
        "git_status.txt": _format_command_output("git status --short", working_tree.status),
        "git_log.txt": committed_diff.git_log,
        "git_diff_stat.txt": _format_command_output(f"git diff --stat {identity.base_sha}..HEAD", committed_diff.diff_stat),
        "git_diff_staged.patch": staged_diff.stdout,
        "git_diff.patch": unstaged_diff.stdout,
        "committed_diff_metadata.txt": helpers["format_committed_diff_metadata"](committed_metadata),
        "committed_diff_stat.txt": committed_diff.diff_stat,
        "committed_changed_files.txt": "\n".join(committed_diff.paths) + ("\n" if committed_diff.paths else ""),
        "committed_diff.patch": committed_diff.patch,
        "untracked_files.txt": helpers["format_untracked_file_list"](_build_command_result("git ls-files --others --exclude-standard", "\n".join(untracked_filtered) + ("\n" if untracked_filtered else "")), untracked_filtered),
        "untracked_file_contents.md": helpers["format_untracked_contents"](project_path, untracked_snapshot),
        "skipped_untracked_files.txt": helpers["format_skipped_untracked_files"](untracked_snapshot.skipped_files),
        "file_tree.txt": helpers["build_file_tree"](project_path),
        "pytest_output.txt": _format_command_output("pytest", pytest_result.stdout, pytest_result.returncode, pytest_result.stderr),
        "ruff_output.txt": _format_command_output("ruff check .", ruff_result.stdout, ruff_result.returncode, ruff_result.stderr),
        "handoff.md": helpers["generate_handoff"](
            story=story,
            project_path=project_path,
            generated_files=[],
            git_status=_build_command_result("git status --short", working_tree.status),
            git_diff=unstaged_diff,
            git_diff_staged=staged_diff,
            committed_diff_metadata=committed_metadata,
            committed_diff_stat=_build_command_result(f"git diff --stat {identity.base_sha}..HEAD", committed_diff.diff_stat),
            committed_diff_files=_build_command_result(f"git diff --name-only {identity.base_sha}..HEAD", "\n".join(committed_diff.paths) + ("\n" if committed_diff.paths else "")),
            committed_diff_patch=_build_command_result(f"git diff {identity.base_sha}..HEAD", committed_diff.patch),
            pytest_result=_cmd(command_runner, ["pytest"], project_path),
            ruff_result=_cmd(command_runner, ["ruff", "check", "."], project_path),
            untracked_snapshot=untracked_snapshot,
        ),
    }

    committed_dir = review_bundle_path / "committed"
    working_tree_dir = review_bundle_path / "working_tree"
    normalization_dir = review_bundle_path / "normalization"
    artifacts_dir = review_bundle_path / "artifacts"
    validation_dir = review_bundle_path / "validation"
    for directory in [committed_dir, working_tree_dir, normalization_dir, artifacts_dir, validation_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    validation_checksums = {
        "algorithm": CHECKSUM_ALGORITHM,
        # Legacy compatibility keys
        "manifest": manifest.integrity["manifest_checksum"],
        "committed_patch": committed_diff.patch_checksum,
        "committed_paths": committed_diff.paths_checksum,
        "git_log": committed_diff.git_log_checksum,
        "diff_stat": committed_diff.diff_stat_checksum,
        "working_tree": working_tree.status_checksum,
        "normalization": checksum_text(dump_yaml({"findings": [finding.__dict__ for finding in normalization]})),
        "artifacts": checksum_text(dump_yaml({"findings": [finding.__dict__ for finding in artifacts]})),
        "pytest": checksum_text(pytest_result.stdout + pytest_result.stderr),
        "ruff": checksum_text(ruff_result.stdout + ruff_result.stderr),

        # Complete deterministic set
        "manifest_payload": manifest.integrity["manifest_checksum"],
        "repository_identity": checksum_text(dump_yaml(identity_to_manifest(identity))),
        "parity_report": checksum_text(dump_yaml(parity_report_to_manifest(parity))),
        "changed_paths": committed_diff.paths_checksum,
        "binary_report": checksum_text(dump_yaml({"binary_files": committed_diff.binary_files})),
        "working_tree_report": working_tree.status_checksum,
        "staged_patch": checksum_text(staged_diff.stdout),
        "unstaged_patch": checksum_text(unstaged_diff.stdout),
        "untracked_report": checksum_text(dump_yaml({"paths": working_tree.untracked})),
        "ignored_report": checksum_text(dump_yaml({"paths": working_tree.ignored})),
        "normalization_report": checksum_text(dump_yaml({"findings": [finding.__dict__ for finding in normalization]})),
        "artifact_report": checksum_text(dump_yaml({"findings": [finding.__dict__ for finding in artifacts]})),
        "pytest_output": checksum_text(pytest_result.stdout + pytest_result.stderr),
        "ruff_output": checksum_text(ruff_result.stdout + ruff_result.stderr),
    }

    files_to_write = {
        review_bundle_path / REVIEW_BUNDLE_MANIFEST: manifest_text,
        review_bundle_path / "repository_identity.yaml": dump_yaml(identity_to_manifest(identity)),
        review_bundle_path / "host_container_parity.yaml": dump_yaml(parity_report_to_manifest(parity)),
        committed_dir / "git_log.txt": committed_diff.git_log,
        committed_dir / "changed_paths.txt": "\n".join(committed_diff.paths) + ("\n" if committed_diff.paths else ""),
        committed_dir / "diff_stat.txt": committed_diff.diff_stat,
        committed_dir / "patch.diff": committed_diff.patch,
        committed_dir / "binary_files.yaml": dump_yaml({"binary_files": committed_diff.binary_files}),
        working_tree_dir / "status.yaml": dump_yaml({"classification": working_tree.classification, "staged": working_tree.staged, "unstaged": working_tree.unstaged, "untracked": working_tree.untracked, "ignored": working_tree.ignored}),
        working_tree_dir / "staged.patch": staged_diff.stdout,
        working_tree_dir / "unstaged.patch": unstaged_diff.stdout,
        working_tree_dir / "untracked.yaml": dump_yaml({"paths": working_tree.untracked}),
        working_tree_dir / "ignored.yaml": dump_yaml({"paths": working_tree.ignored}),
        normalization_dir / "report.yaml": dump_yaml({"findings": [finding.__dict__ for finding in normalization]}),
        artifacts_dir / "report.yaml": dump_yaml({"findings": [finding.__dict__ for finding in artifacts]}),
        validation_dir / "pytest_output.txt": _format_command_output("pytest", pytest_result.stdout, pytest_result.returncode, pytest_result.stderr),
        validation_dir / "ruff_output.txt": _format_command_output("ruff check .", ruff_result.stdout, ruff_result.returncode, ruff_result.stderr),
        validation_dir / "checksums.yaml": dump_yaml(validation_checksums),
        validation_dir / "diagnostics.md": format_diagnostics_report(identity, parity, working_tree, normalization, file_modes, artifacts, cleanliness),
    }
    files_to_write.update({review_bundle_path / name: content for name, content in compatibility.items()})
    generated_files: list[Path] = []
    for path, content in files_to_write.items():
        write_text_file(path, content)
        generated_files.append(path)

    return ReviewBundleServiceResult(
        review_bundle_path=review_bundle_path,
        generated_files=generated_files,
        pytest_passed=pytest_result.returncode == 0,
        ruff_passed=ruff_result.returncode == 0,
        identity=identity,
        host_identity=host_identity,
        parity_mismatches=parity.mismatches,
        cleanliness=cleanliness,
        manifest_path=review_bundle_path / REVIEW_BUNDLE_MANIFEST,
        validation_report_path=validation_dir / "diagnostics.md",
    )


def validate_review_bundle(project_path: Path, story: str, base_ref: str = "origin/main", command_runner: CommandRunner = run_git) -> ReviewBundleValidation:
    project_path = project_path.resolve()
    story_path = _ensure_story_path(project_path, story)
    review_bundle_path = story_path / REVIEW_BUNDLE_DIRNAME
    manifest_path = review_bundle_path / REVIEW_BUNDLE_MANIFEST
    checksum_path = review_bundle_path / "validation" / "checksums.yaml"

    if not manifest_path.exists():
        return ReviewBundleValidation(False, ["manifest missing"], None, manifest_path, checksum_path)
    
    try:
        manifest = load_yaml_mapping(manifest_path.read_text(encoding="utf-8"))
        validate_review_manifest(manifest)
    except Exception as e:
        return ReviewBundleValidation(False, [f"corrupt manifest file: {e}"], None, manifest_path, checksum_path)

    reasons: list[str] = []

    # 1. Verify manifest payload checksum
    try:
        manifest_copy = dict(manifest)
        integrity = manifest_copy.pop("integrity", {})
        expected_manifest_checksum = integrity.get("manifest_checksum")
        actual_manifest_checksum = checksum_text(dump_yaml(manifest_copy))
        if expected_manifest_checksum != actual_manifest_checksum:
            reasons.append("corrupt manifest checksum")
    except Exception as e:
        reasons.append(f"could not verify manifest checksum: {e}")

    # 2. Check stale bundle (Independently resolve current repo state)
    try:
        identity = resolve_repository_identity(project_path, requested_base_ref=base_ref, command_runner=command_runner)
        repository = manifest.get("repository", {})
        if repository.get("head_sha") != identity.head_sha:
            reasons.append("HEAD changed after review bundle generation")
        if repository.get("base_sha") != identity.base_sha:
            reasons.append("base ref changed")
        if repository.get("merge_base_sha") != identity.merge_base_sha:
            reasons.append("merge base changed")
        if repository.get("branch") != identity.branch:
            reasons.append("branch changed")
    except Exception as e:
        reasons.append(f"failed to resolve repository identity: {e}")

    # 3. Check checksum file presence
    if not checksum_path.exists():
        reasons.append("checksum file missing")
        checksums = {}
    else:
        try:
            checksums = load_yaml_mapping(checksum_path.read_text(encoding="utf-8"))
        except Exception as e:
            reasons.append(f"corrupt checksum file: {e}")
            checksums = {}

    if checksums and "manifest" in checksums:
        if checksums.get("manifest") != manifest.get("integrity", {}).get("manifest_checksum"):
            reasons.append("manifest checksum mismatch")

    # 4. Check for ambiguous review state
    cleanliness_classification = manifest.get("working_tree", {}).get("classification")
    if cleanliness_classification == "ambiguous":
        reasons.append("ambiguous review state")

    # 5. Check evidence checksums & missing mandatory evidence
    evidence_mappings = [
        ("committed/git_log.txt", ["git_log"], "git log"),
        ("committed/changed_paths.txt", ["committed_paths", "changed_paths"], "changed paths"),
        ("committed/diff_stat.txt", ["diff_stat", "diff_stat_checksum"], "diff stat"),
        ("committed/patch.diff", ["committed_patch", "patch_checksum"], "committed patch"),
        ("working_tree/status.yaml", ["working_tree", "working_tree_report"], "working tree report"),
        ("working_tree/staged.patch", ["staged_patch"], "staged patch"),
        ("working_tree/unstaged.patch", ["unstaged_patch"], "unstaged patch"),
        ("normalization/report.yaml", ["normalization", "normalization_report"], "normalization report"),
        ("artifacts/report.yaml", ["artifacts", "artifact_report"], "artifact report"),
        ("validation/pytest_output.txt", ["pytest", "pytest_output"], "pytest output"),
        ("validation/ruff_output.txt", ["ruff", "ruff_output"], "ruff output"),
    ]

    for rel_path, checksum_keys, desc in evidence_mappings:
        file_path = review_bundle_path / rel_path
        if not file_path.exists():
            reasons.append(f"missing mandatory evidence: {desc}")
            continue

        try:
            file_bytes = file_path.read_bytes()
            actual_hash = checksum_bytes(file_bytes)
            
            expected_hash = None
            for key in checksum_keys:
                if key in checksums:
                    expected_hash = checksums[key]
                    break
            
            if expected_hash is not None:
                if actual_hash != expected_hash:
                    text_content = file_bytes.decode("utf-8", errors="replace")
                    normalized_text_content = text_content.replace("\r\n", "\n")
                    if checksum_text(normalized_text_content) == expected_hash:
                        continue
                    reasons.append(f"corrupt evidence checksum: {desc}")
        except Exception as e:
            reasons.append(f"failed to verify evidence integrity for {desc}: {e}")

    return ReviewBundleValidation(not reasons, reasons, manifest, manifest_path, checksum_path)
