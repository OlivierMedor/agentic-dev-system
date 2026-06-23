from __future__ import annotations

from pathlib import Path

from agentic_dev.review_bundle import create_review_bundle
from agentic_dev.review_state.service import validate_review_bundle


class Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FixedRunner:
    def __init__(self, head_sha: str = "HEADSHA") -> None:
        self.head_sha = head_sha

    def __call__(self, command: list[str], cwd: Path) -> Result:
        text = " ".join(command)
        outputs = {
            "git rev-parse --is-inside-work-tree": "true\n",
            "git rev-parse --show-toplevel": f"{cwd}\n",
            "git rev-parse --git-dir": ".git\n",
            "git branch --show-current": "main\n",
            "git rev-parse HEAD": f"{self.head_sha}\n",
            "git rev-parse --is-shallow-repository": "false\n",
            "git rev-parse --verify origin/main": "BASESHA\n",
            "git merge-base HEAD origin/main": "BASESHA\n",
            "git rev-parse --verify refs/remotes/origin/main": "BASESHA\n",
            "git config --get remote.origin.url": "https://github.com/OlivierMedor/agentic-dev-system.git\n",
            "git rev-list --max-parents=0 HEAD": "rootcommit\n",
            "git status --short": "M file.txt\n",
            "git diff --cached --name-only": "file.txt\n",
            "git diff --name-only": "file.txt\n",
            "git ls-files --others --exclude-standard": "",
            "git ls-files --others --ignored --exclude-standard": "",
            "git ls-files": "file.txt\n",
            "git diff --cached": "cached\n",
            "git diff": "diff\n",
            f"git rev-list --count BASESHA..{self.head_sha}": "1\n",
            f"git log --reverse --format=%H%x09%s BASESHA..{self.head_sha}": "c1\tmsg\n",
            f"git diff --name-only BASESHA..{self.head_sha}": "file.txt\n",
            f"git diff --stat BASESHA..{self.head_sha}": " file.txt | 1 +\n",
            f"git diff --binary BASESHA..{self.head_sha}": "patch\n",
            f"git diff --summary BASESHA..{self.head_sha}": "",
            f"git diff --name-status BASESHA..{self.head_sha}": "M\tfile.txt\n",
            "git show HEAD:file.txt": "content\n",
            "git check-attr -a -- file.txt": "file.txt: text: set\n",
            "git diff --summary -- file.txt": "",
            "git diff -U0 -- file.txt": "",
            "pytest": "ok\n",
            "ruff check .": "ok\n",
        }
        return Result(0, outputs[text], "")


def test_review_bundle_writes_manifest_and_legacy_outputs(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    story_path = tmp_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# story\n", encoding="utf-8")
    (story_path / "file.txt").write_text("content\n", encoding="utf-8")

    result = create_review_bundle(tmp_path, story, command_runner=FixedRunner())

    assert result.pytest_passed is True
    assert result.ruff_passed is True
    assert {path.relative_to(result.review_bundle_path).as_posix() for path in result.generated_files} == {
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
    assert (result.review_bundle_path / "manifest.yaml").exists()
    assert (result.review_bundle_path / "validation" / "checksums.yaml").exists()
    assert (result.review_bundle_path / "committed" / "git_log.txt").exists()
    assert (result.review_bundle_path / "working_tree" / "status.yaml").exists()


def test_validate_review_bundle_rejects_head_changes(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    story_path = tmp_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# story\n", encoding="utf-8")
    (story_path / "file.txt").write_text("content\n", encoding="utf-8")

    create_review_bundle(tmp_path, story, command_runner=FixedRunner(head_sha="HEADSHA"))

    validation = validate_review_bundle(tmp_path, story, command_runner=FixedRunner(head_sha="DIFFERENT"))

    assert validation.valid is False
    assert any("HEAD changed" in reason for reason in validation.reasons)


def test_host_container_parity_not_checked_when_absent(tmp_path: Path) -> None:
    from agentic_dev.review_state.git_identity import compare_host_and_container_identity
    from agentic_dev.review_state.models import RepositoryIdentity
    
    container = RepositoryIdentity(
        root=Path("/app"),
        branch="main",
        head_sha="HEADSHA",
        remote_head_sha="REMOTESHA",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path(".git"),
        shallow_clone=False,
        detached_head=False,
        missing_remote=False,
        missing_base_ref=False,
    )
    
    report = compare_host_and_container_identity(container, None)
    assert report.supplied is False
    assert report.matched is False
    assert report.status == "not_checked"


def test_host_container_parity_fails_on_mismatches(tmp_path: Path) -> None:
    from agentic_dev.review_state.git_identity import compare_host_and_container_identity
    from agentic_dev.review_state.models import RepositoryIdentity, HostIdentity
    
    container = RepositoryIdentity(
        root=Path("/app"),
        branch="main",
        head_sha="HEADSHA",
        remote_head_sha="REMOTESHA",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path(".git"),
        shallow_clone=False,
        detached_head=False,
        missing_remote=False,
        missing_base_ref=False,
        repository_id="rootcommit:github.com/oliviermedor/agentic-dev-system",
        remote_url="https://github.com/OlivierMedor/agentic-dev-system.git",
    )
    
    # Matching host identity
    matching_host = HostIdentity(
        root=Path("/app"),
        branch="main",
        head_sha="HEADSHA",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path(".git"),
        shallow_clone=False,
        detached_head=False,
        repository_id="rootcommit:github.com/oliviermedor/agentic-dev-system",
        remote_url="https://github.com/OlivierMedor/agentic-dev-system.git",
    )
    report_match = compare_host_and_container_identity(container, matching_host)
    assert report_match.supplied is True
    assert report_match.matched is True
    assert report_match.status == "passed"
    
    # Mismatched host identity
    mismatched_host = HostIdentity(
        root=Path("/app"),
        branch="feature",  # different branch!
        head_sha="HEADSHA",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path(".git"),
        shallow_clone=False,
        detached_head=False,
        repository_id="rootcommit:github.com/oliviermedor/agentic-dev-system",
        remote_url="https://github.com/OlivierMedor/agentic-dev-system.git",
    )
    report_mismatch = compare_host_and_container_identity(container, mismatched_host)
    assert report_mismatch.supplied is True
    assert report_mismatch.matched is False
    assert report_mismatch.status == "failed"
    assert "branch mismatch" in report_mismatch.mismatches


def test_host_container_parity_detailed_cases(tmp_path: Path) -> None:
    from agentic_dev.review_state.git_identity import compare_host_and_container_identity
    from agentic_dev.review_state.models import RepositoryIdentity, HostIdentity
    
    container = RepositoryIdentity(
        root=Path("/workspace"),
        branch="main",
        head_sha="HEADSHA",
        remote_head_sha="REMOTESHA",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path("/workspace/.git"),
        shallow_clone=False,
        detached_head=False,
        missing_remote=False,
        missing_base_ref=False,
        repository_id="rootcommit:github.com/oliviermedor/agentic-dev-system",
        remote_url="https://github.com/OlivierMedor/agentic-dev-system.git",
    )
    
    # 1. Valid same repository, different paths
    matching_host = HostIdentity(
        root=Path("C:\\dev\\agentic-dev-system"),
        branch="main",
        head_sha="HEADSHA",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path("C:\\dev\\agentic-dev-system\\.git"),
        shallow_clone=False,
        detached_head=False,
        repository_id="rootcommit:github.com/oliviermedor/agentic-dev-system",
        remote_url="git@github.com:OlivierMedor/agentic-dev-system.git",  # ssh URL matches HTTPS normalized URL!
    )
    report_match = compare_host_and_container_identity(container, matching_host)
    assert report_match.supplied is True
    assert report_match.matched is True
    assert report_match.status == "passed"
    assert len(report_match.mismatches) == 0

    # 2. Different repository fingerprint
    different_host = HostIdentity(
        root=Path("C:\\dev\\agentic-dev-system"),
        branch="main",
        head_sha="HEADSHA",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path("C:\\dev\\agentic-dev-system\\.git"),
        shallow_clone=False,
        detached_head=False,
        repository_id="differentcommit:github.com/oliviermedor/agentic-dev-system",
        remote_url="git@github.com:OlivierMedor/agentic-dev-system.git",
    )
    report_diff = compare_host_and_container_identity(container, different_host)
    assert report_diff.matched is False
    assert "wrong repository" in report_diff.mismatches

    # 3. Same path name but different repository (remote differs)
    same_path_diff_repo = HostIdentity(
        root=Path("C:\\dev\\agentic-dev-system"),
        branch="main",
        head_sha="HEADSHA",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path("C:\\dev\\agentic-dev-system\\.git"),
        shallow_clone=False,
        detached_head=False,
        repository_id="rootcommit:github.com/other/agentic-dev-system",
        remote_url="https://github.com/other/agentic-dev-system.git",
    )
    report_diff_repo = compare_host_and_container_identity(container, same_path_diff_repo)
    assert report_diff_repo.matched is False
    assert "wrong repository" in report_diff_repo.mismatches

    # 4. Worktree: different host/container .git locations (different paths, e.g. using git worktree)
    worktree_host = HostIdentity(
        root=Path("C:\\dev\\worktree-folder"),
        branch="main",
        head_sha="HEADSHA",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path("C:\\dev\\agentic-dev-system\\.git\\worktrees\\worktree-folder"),
        shallow_clone=False,
        detached_head=False,
        repository_id="rootcommit:github.com/oliviermedor/agentic-dev-system",
        remote_url="https://github.com/OlivierMedor/agentic-dev-system.git",
    )
    report_worktree = compare_host_and_container_identity(container, worktree_host)
    assert report_worktree.matched is True

    # 5. Missing fingerprint (both remote_url and repository_id are None on host)
    missing_fingerprint_host = HostIdentity(
        root=Path("C:\\dev\\agentic-dev-system"),
        branch="main",
        head_sha="HEADSHA",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path("C:\\dev\\agentic-dev-system\\.git"),
        shallow_clone=False,
        detached_head=False,
        repository_id=None,
        remote_url=None,
    )
    report_missing = compare_host_and_container_identity(container, missing_fingerprint_host)
    assert report_missing.matched is False
    assert "missing Git metadata" in report_missing.mismatches or "missing fingerprint" in report_missing.mismatches

    # 6. Existing mismatch behaviors:
    # HEAD mismatch
    head_mismatch_host = HostIdentity(
        root=Path("C:\\dev\\agentic-dev-system"),
        branch="main",
        head_sha="DIFFERENT_HEAD",
        requested_base_ref="origin/main",
        base_sha="BASESHA",
        merge_base_sha="MERGESHA",
        git_dir=Path("C:\\dev\\agentic-dev-system\\.git"),
        shallow_clone=False,
        detached_head=False,
        repository_id="rootcommit:github.com/oliviermedor/agentic-dev-system",
        remote_url="https://github.com/OlivierMedor/agentic-dev-system.git",
    )
    assert "HEAD mismatch" in compare_host_and_container_identity(container, head_mismatch_host).mismatches


def test_byte_safe_normalization_classification(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    story_path = tmp_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# story\n", encoding="utf-8")
    
    # Create test files with different line endings/BOMs
    (tmp_path / "crlf.txt").write_bytes(b"line1\r\nline2\r\n")
    (tmp_path / "bom.txt").write_bytes(b"\xef\xbb\xbfline1\nline2\n")
    (tmp_path / "binary.bin").write_bytes(b"some\x00binary\x00data")
    
    class NormalizationRunner(FixedRunner):
        def __call__(self, command: list[str], cwd: Path) -> Result:
            text = " ".join(command)
            # Override HEAD contents
            if text == "git show HEAD:crlf.txt":
                return Result(0, "line1\nline2\n", "")
            if text == "git show HEAD:bom.txt":
                return Result(0, "line1\nline2\n", "")
            if text == "git show HEAD:binary.bin":
                return Result(0, "some binary data", "")
            if "check-attr" in text:
                return Result(0, "", "")
            return super().__call__(command, cwd)

    runner = NormalizationRunner()
    result = create_review_bundle(tmp_path, story, command_runner=runner)
    
    # Just to assert that bundle runs successfully
    assert result.pytest_passed is True


def test_review_state_parity_and_checksum_matrix(tmp_path: Path) -> None:
    from agentic_dev.review_state.git_identity import (
        normalize_git_url,
        strip_credentials,
        compare_host_and_container_identity,
        validate_and_recompute_host_identity,
    )
    from agentic_dev.review_state.models import RepositoryIdentity, HostIdentity
    from agentic_dev.review_state.service import validate_review_manifest, verify_checksum_entry
    from agentic_dev.review_state.integrity import generate_checksum_metadata
    from hashlib import sha256

    # 1. Multiple root commits with deterministic ordering & different returned order
    container = RepositoryIdentity(
        root=Path("/workspace"),
        branch="main",
        head_sha="a" * 40,
        remote_head_sha="b" * 40,
        requested_base_ref="origin/main",
        base_sha="c" * 40,
        merge_base_sha="d" * 40,
        git_dir=Path("/workspace/.git"),
        shallow_clone=False,
        detached_head=False,
        missing_remote=False,
        missing_base_ref=False,
        root_commit_shas=["c1" * 20, "c2" * 20],
        remote_url="https://github.com/OlivierMedor/agentic-dev-system.git",
        normalized_remote_url="github.com/oliviermedor/agentic-dev-system",
        repository_id_strength="strong",
        repository_id_version=1,
    )
    # Compute container repository_id manually using canonical v1 payload
    payload = "repository-id-v1\n" + "c1" * 20 + "\n" + "c2" * 20 + "\n" + "github.com/oliviermedor/agentic-dev-system"
    expected_container_id = sha256(payload.encode("utf-8")).hexdigest()
    container = RepositoryIdentity(
        root=container.root,
        branch=container.branch,
        head_sha=container.head_sha,
        remote_head_sha=container.remote_head_sha,
        requested_base_ref=container.requested_base_ref,
        base_sha=container.base_sha,
        merge_base_sha=container.merge_base_sha,
        git_dir=container.git_dir,
        shallow_clone=container.shallow_clone,
        detached_head=container.detached_head,
        missing_remote=container.missing_remote,
        missing_base_ref=container.missing_base_ref,
        root_commit_shas=container.root_commit_shas,
        remote_url=container.remote_url,
        normalized_remote_url=container.normalized_remote_url,
        repository_id_strength=container.repository_id_strength,
        repository_id_version=container.repository_id_version,
        repository_id=expected_container_id,
    )

    # Host has same root commits but in different order:
    host_data = {
        "root": "C:\\dev\\agentic-dev-system",
        "branch": "main",
        "head_sha": "a" * 40,
        "requested_base_ref": "origin/main",
        "base_sha": "c" * 40,
        "merge_base_sha": "d" * 40,
        "git_dir": "C:\\dev\\agentic-dev-system\\.git",
        "shallow_clone": False,
        "detached_head": False,
        "root_commit_shas": ["c2" * 20, "c1" * 20],  # order reversed
        "remote_url": "git@github.com:OlivierMedor/agentic-dev-system.git",
    }
    host = validate_and_recompute_host_identity(host_data)
    assert host.repository_id == expected_container_id
    assert host.repository_id_strength == "strong"
    
    report = compare_host_and_container_identity(container, host)
    assert report.matched is True

    # 2. Versioned fingerprint reproducibility
    assert host.repository_id_version == 1

    # 3. Strong versus weak identity policy
    weak_container = RepositoryIdentity(
        root=Path("/workspace"),
        branch="main",
        head_sha="a" * 40,
        remote_head_sha="b" * 40,
        requested_base_ref="origin/main",
        base_sha="c" * 40,
        merge_base_sha="d" * 40,
        git_dir=Path("/workspace/.git"),
        shallow_clone=False,
        detached_head=False,
        missing_remote=False,
        missing_base_ref=False,
        root_commit_shas=["c1" * 20],
        remote_url=None,
        normalized_remote_url=None,
        repository_id_strength="weak",
    )
    weak_host = HostIdentity(
        root=Path("C:\\dev\\agentic-dev-system"),
        branch="main",
        head_sha="a" * 40,
        requested_base_ref="origin/main",
        base_sha="c" * 40,
        merge_base_sha="d" * 40,
        git_dir=Path("C:\\dev\\agentic-dev-system\\.git"),
        shallow_clone=False,
        detached_head=False,
        root_commit_shas=["c1" * 20],
        remote_url=None,
        repository_id_strength="weak",
    )
    report_weak = compare_host_and_container_identity(weak_container, weak_host)
    assert report_weak.matched is False
    assert "weak repository identity" in report_weak.mismatches

    # 4. Local path remote normalizes to None & results in weak/none strength
    assert normalize_git_url("C:\\dev\\repo") is None
    assert normalize_git_url("/workspace/repo") is None
    assert normalize_git_url("file:///C:/dev/repo") is None

    # 5. Unknown case-sensitive Git host preserves path casing, hostname lowercased
    assert normalize_git_url("https://My-Server.org/Folder/SubFolder/Repo.git") == "my-server.org/Folder/SubFolder/Repo"

    # 6. Credential-bearing URLs (HTTP/SSH)
    assert strip_credentials("https://user:pass@github.com/owner/repo.git?query=123#frag") == "https://github.com/owner/repo.git"
    assert normalize_git_url("https://user:pass@github.com/owner/repo.git") == "github.com/owner/repo"
    assert normalize_git_url("ssh://git@github.com/owner/repo.git") == "github.com/owner/repo"

    # 7. Malformed host identity types & invalid SHA values
    import pytest
    with pytest.raises(ValueError, match="Invalid SHA format"):
        validate_and_recompute_host_identity({"head_sha": "not-a-sha"})
    with pytest.raises(ValueError, match="root_commit_shas must be a list"):
        validate_and_recompute_host_identity({"root_commit_shas": "not-a-list"})

    # 8. Schema version mismatch in validate_review_manifest
    with pytest.raises(ValueError, match="Unsupported review manifest schema version"):
        validate_review_manifest({"schema_version": 3, "repository": {}, "committed_diff": {}})

    # 9. Schema version 1 compatibility (validate string checksums)
    # verify_checksum_entry with string checksum should match
    text_data = b"hello\r\nworld\r\n"
    # string checksum representing exact bytes (crlf)
    exact_crlf_hash = sha256(text_data).hexdigest()
    assert verify_checksum_entry(text_data, exact_crlf_hash) is True
    # string checksum representing canonical bytes (lf)
    canonical_lf_hash = sha256(b"hello\nworld\n").hexdigest()
    assert verify_checksum_entry(text_data, canonical_lf_hash) is True
    
    # 10. Schema version 2 dual-digest checksum policies
    # Binary file (no canonical allowed):
    bin_meta = generate_checksum_metadata(b"hello\r\nworld\r\n", allow_canonical=False)
    assert bin_meta["content_type"] == "text"  # text file detected, but let's check validation
    assert bin_meta["canonicalization"]["allowed"] is False
    # If allowed is False, only exact-byte matches
    assert verify_checksum_entry(b"hello\r\nworld\r\n", bin_meta) is True
    assert verify_checksum_entry(b"hello\nworld\n", bin_meta) is False  # LF doesn't match CRLF when canonicalization not allowed!
    
    # Text file (canonical allowed):
    text_meta = generate_checksum_metadata(b"hello\r\nworld\r\n", allow_canonical=True)
    assert text_meta["canonicalization"]["allowed"] is True
    # If allowed is True, both exact byte and LF normalized match passes
    assert verify_checksum_entry(b"hello\r\nworld\r\n", text_meta) is True
    assert verify_checksum_entry(b"hello\nworld\n", text_meta) is True
    
    # Semantic text modification fails
    assert verify_checksum_entry(b"hello edit\nworld\n", text_meta) is False


def test_powershell_json_integration(tmp_path: Path) -> None:
    from agentic_dev.review_state.git_identity import load_host_identity
    import json
    
    mock_payload = {
        "root": "C:\\dev\\agentic-dev-system",
        "branch": "story/066-review-bundle-diff-normalization-implementation",
        "head_sha": "0f8894f87f076331612e4a60b07d5c1480e4f070",
        "requested_base_ref": "origin/main",
        "base_sha": "5b5d25d67c0825afc8bf884fd56ea0cc4ced0b15",
        "merge_base_sha": "5b5d25d67c0825afc8bf884fd56ea0cc4ced0b15",
        "git_dir": "C:/dev/agentic-dev-system/.git/worktrees/agentic-dev-system-story066-impl2",
        "detached_head": False,
        "shallow_clone": False,
        "remote_url": "https://github.com/OlivierMedor/agentic-dev-system.git",
        "normalized_remote_url": "github.com/oliviermedor/agentic-dev-system",
        "root_commit_shas": ["de66f85b054b705da5615e508175a995c4c7aeea"],
        "repository_id": "dd2b95248f0a3365f94c74da05ec54f36dede9624c603d9d1026d1f72054ac3b",
        "repository_id_strength": "strong",
        "repository_id_version": 1
    }
    
    temp_json = tmp_path / "host_identity.json"
    temp_json.write_text(json.dumps(mock_payload), encoding="utf-8")
    
    loaded = load_host_identity(temp_json)
    assert loaded.repository_id == "dd2b95248f0a3365f94c74da05ec54f36dede9624c603d9d1026d1f72054ac3b"
    assert loaded.repository_id_strength == "strong"
    assert loaded.repository_id_version == 1


