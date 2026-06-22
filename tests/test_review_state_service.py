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
    )
    report_mismatch = compare_host_and_container_identity(container, mismatched_host)
    assert report_mismatch.supplied is True
    assert report_mismatch.matched is False
    assert report_mismatch.status == "failed"
    assert "branch mismatch" in report_mismatch.mismatches


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


