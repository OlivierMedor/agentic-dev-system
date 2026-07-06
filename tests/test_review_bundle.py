from pathlib import Path
import pytest

from agentic_dev.cli import main
from agentic_dev.review_bundle import CommandResult, ReviewBundleResult, create_review_bundle
from agentic_dev.review_state.service import validate_review_bundle

BASE_SHA = "5f0d9fda8b6b0a89ed6c6ef819a6937630d79d3e"
HEAD_SHA = "c2ec13bfefe6e8cf35d2f6ac4dc2f3a20193b47a"


def write_runtime_config(project_path: Path, default_base_ref: str) -> Path:
    config_path = project_path / ".agentic" / "agent_runtime.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(f"default_base_ref: {default_base_ref}\n", encoding="utf-8")
    return config_path


def mock_git_runner(cwd: Path, custom_outputs: dict[str, str | tuple[int, str, str]], head_sha=HEAD_SHA, base_sha=BASE_SHA):
    outputs = {
        "git rev-parse --is-inside-work-tree": "true\n",
        "git rev-parse --show-toplevel": f"{cwd.resolve()}\n",
        "git rev-parse --git-dir": ".git\n",
        "git branch --show-current": "main\n",
        "git rev-parse --is-shallow-repository": "false\n",
        "git rev-parse --verify origin/main": f"{base_sha}\n",
        "git rev-parse --verify refs/remotes/origin/main": f"{base_sha}\n",
        f"git rev-parse --verify refs/remotes/{base_sha}": (1, "", "fatal: Needed a single revision\n"),
        f"git rev-parse --verify {base_sha}": f"{base_sha}\n",
        "git rev-parse HEAD": f"{head_sha}\n",
        "git merge-base HEAD origin/main": f"{base_sha}\n",
        f"git merge-base HEAD {base_sha}": f"{base_sha}\n",
        "git diff --stat": "",
        "git diff --cached": "",
        "git diff": "",
        f"git diff --stat {base_sha}..HEAD": "",
        f"git diff --name-only {base_sha}..HEAD": "",
        f"git diff {base_sha}..HEAD": "",
        f"git diff --stat {base_sha}..{head_sha}": "",
        f"git diff --name-only {base_sha}..{head_sha}": "",
        f"git diff {base_sha}..{head_sha}": "",
        f"git rev-list --count {base_sha}..{head_sha}": "1\n",
        "git ls-files --others --exclude-standard": "",
        "git ls-files --others --ignored --exclude-standard": "",
        "git status --short": "",
        "git log --oneline -5": "c2ec13b fix: msg\n",
        f"git log --reverse --format=%H%x09%s {base_sha}..{head_sha}": "c2ec13b\tfix: msg\n",
        f"git diff --binary {base_sha}..{head_sha}": "",
        f"git diff --summary {base_sha}..{head_sha}": "",
        f"git diff --name-status {base_sha}..{head_sha}": "",
        "git ls-files": "",
        "git diff --cached --name-only": "",
        "git diff --name-only": "",
        "git config --get remote.origin.url": "https://github.com/OlivierMedor/agentic-dev-system.git\n",
        "git rev-list --max-parents=0 HEAD": "rootcommit\n",
        "pytest": "12 passed in 0.34s\n",
        "ruff check .": "All checks passed!\n",
    }
    outputs.update(custom_outputs)

    def runner(command: list[str], cwd_path: Path) -> CommandResult:
        cmd_text = " ".join(command)
        if cmd_text == "git rev-parse --show-toplevel":
            return CommandResult(cmd_text, 0, f"{cwd_path.resolve()}\n", "")
        if cmd_text not in outputs:
            raise KeyError(f"Unexpected strict command call: {cmd_text}")

        val = outputs[cmd_text]
        if isinstance(val, tuple):
            return CommandResult(cmd_text, val[0], val[1], val[2])
        return CommandResult(cmd_text, 0, val, "")
    return runner


def test_create_review_bundle_writes_expected_files(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    story_path = tmp_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text("# story\n", encoding="utf-8")

    runner = mock_git_runner(tmp_path, {
        "git diff --cached": "diff --git a/README.md b/README.md\n",
        "git diff": "diff --git a/src/app.py b/src/app.py\n",
        "git diff --cached --name-only": "README.md\n",
        "git diff --name-only": "src/app.py\n",
        "git show HEAD:README.md": "readme content\n",
        "git show HEAD:src/app.py": "app content\n",
        "git check-attr -a -- README.md": "",
        "git check-attr -a -- src/app.py": "",
        "git diff --summary -- README.md": "",
        "git diff --summary -- src/app.py": "",
    })

    result = create_review_bundle(tmp_path, story, command_runner=runner)

    expected_files = {
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

    assert result.review_bundle_path == story_path / "review_bundle"
    assert {path.name for path in result.generated_files} == expected_files

    for filename in expected_files:
        assert (result.review_bundle_path / filename).exists()

    handoff = (result.review_bundle_path / "handoff.md").read_text(encoding="utf-8")
    assert story in handoff
    assert "- pytest: passed" in handoff
    assert "- ruff: passed" in handoff


def test_create_review_bundle_accepts_explicit_base_sha_for_clean_branch(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")

    runner = mock_git_runner(tmp_path, {}, base_sha=BASE_SHA)

    result = create_review_bundle(tmp_path, story, base_ref=BASE_SHA, command_runner=runner)

    metadata = (result.review_bundle_path / "committed_diff_metadata.txt").read_text(encoding="utf-8")
    assert f"Requested base ref: `{BASE_SHA}`" in metadata
    assert f"Base SHA: `{BASE_SHA}`" in metadata


def test_create_review_bundle_uses_project_default_base_ref_when_base_ref_is_omitted(
    tmp_path: Path,
) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")
    default_base_ref = "origin/phase/01-funding-spike-detector"
    write_runtime_config(tmp_path, default_base_ref)

    runner = mock_git_runner(
        tmp_path,
        {
            f"git rev-parse --verify {default_base_ref}": f"{BASE_SHA}\n",
            f"git merge-base HEAD {default_base_ref}": f"{BASE_SHA}\n",
            f"git rev-parse --verify refs/remotes/{default_base_ref}": (
                1,
                "",
                "fatal: Needed a single revision\n",
            ),
        },
    )

    result = create_review_bundle(tmp_path, story, command_runner=runner)

    metadata = (result.review_bundle_path / "committed_diff_metadata.txt").read_text(encoding="utf-8")
    assert f"Requested base ref: `{default_base_ref}`" in metadata
    assert f"Resolved base ref: `{default_base_ref}`" in metadata
    assert f"Base SHA: `{BASE_SHA}`" in metadata


def test_create_review_bundle_fails_when_selected_base_ref_is_missing(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")
    missing_base_ref = "origin/phase/does-not-exist"
    write_runtime_config(tmp_path, missing_base_ref)

    runner = mock_git_runner(
        tmp_path,
        {
            f"git rev-parse --verify {missing_base_ref}": (
                1,
                "",
                f"fatal: Needed a single revision {missing_base_ref}\n",
            ),
            f"git merge-base HEAD {missing_base_ref}": (
                1,
                "",
                f"fatal: Not a valid object name {missing_base_ref}\n",
            ),
        },
    )

    with pytest.raises(ValueError, match="Requested base ref 'origin/phase/does-not-exist' could not be resolved"):
        create_review_bundle(tmp_path, story, command_runner=runner)


def test_file_tree_excludes_noisy_folders(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")

    runner = mock_git_runner(tmp_path, {})
    result = create_review_bundle(tmp_path, story, command_runner=runner)

    file_tree = (result.review_bundle_path / "file_tree.txt").read_text(encoding="utf-8")
    assert "src/app.py" in file_tree
    assert ".git" not in file_tree


def test_command_failures_are_written_to_output_files(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")

    runner = mock_git_runner(tmp_path, {
        "pytest": (1, "one test failed\n", "failure details\n"),
    })

    result = create_review_bundle(tmp_path, story, command_runner=runner)
    pytest_output = (result.review_bundle_path / "pytest_output.txt").read_text(encoding="utf-8")
    assert result.pytest_passed is False
    assert "Status: FAILED" in pytest_output
    assert "one test failed" in pytest_output


def test_untracked_file_outputs_include_safe_text_file_contents(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "review.txt").write_text("new review notes\n", encoding="utf-8")

    runner = mock_git_runner(tmp_path, {
        "git ls-files --others --exclude-standard": "notes/review.txt\n",
    })

    result = create_review_bundle(tmp_path, story, command_runner=runner)
    untracked_files = (result.review_bundle_path / "untracked_files.txt").read_text(encoding="utf-8")
    contents = (result.review_bundle_path / "untracked_file_contents.md").read_text(encoding="utf-8")
    assert "notes/review.txt" in untracked_files
    assert "new review notes" in contents


def test_untracked_file_outputs_record_skipped_files(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=value\n", encoding="utf-8")
    (tmp_path / "large.txt").write_text("x" * 102_401, encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"hello\x00world")

    runner = mock_git_runner(tmp_path, {
        "git ls-files --others --exclude-standard": ".env\nlarge.txt\nbinary.bin\n",
    })

    result = create_review_bundle(tmp_path, story, command_runner=runner)
    contents = (result.review_bundle_path / "untracked_file_contents.md").read_text(encoding="utf-8")
    skipped = (result.review_bundle_path / "skipped_untracked_files.txt").read_text(encoding="utf-8")
    assert "SECRET=value" not in contents
    assert ".env: potential secret file" in skipped
    assert "large.txt: file too large" in skipped


def test_uncommitted_edits_never_enter_committed_patch(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")

    # Add uncommitted edits in working tree, but ensure committed diff doesn't contain them
    runner = mock_git_runner(tmp_path, {
        "git diff --cached": "diff --git a/uncommitted_staged b/uncommitted_staged\n",
        "git diff": "diff --git a/uncommitted_unstaged b/uncommitted_unstaged\n",
        "git diff --cached --name-only": "uncommitted_staged\n",
        "git diff --name-only": "uncommitted_unstaged\n",
        f"git diff --binary {BASE_SHA}..{HEAD_SHA}": "diff --git a/committed_file b/committed_file\n",
        f"git diff --name-only {BASE_SHA}..{HEAD_SHA}": "committed_file\n",
        "git show HEAD:uncommitted_staged": "content\n",
        "git show HEAD:uncommitted_unstaged": "content\n",
        "git check-attr -a -- uncommitted_staged": "",
        "git check-attr -a -- uncommitted_unstaged": "",
        "git diff --summary -- uncommitted_staged": "",
        "git diff --summary -- uncommitted_unstaged": "",
    })

    result = create_review_bundle(tmp_path, story, command_runner=runner)
    committed_patch = (result.review_bundle_path / "committed_diff.patch").read_text(encoding="utf-8")
    assert "committed_file" in committed_patch
    assert "uncommitted_staged" not in committed_patch
    assert "uncommitted_unstaged" not in committed_patch


def test_diagnose_git_state_causes_no_mutation(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")

    runner = mock_git_runner(tmp_path, {})

    # Run in diagnose-git-state mode
    from agentic_dev.review_bundle import ReviewBundleDiagnosticsResult
    result = create_review_bundle(tmp_path, story, diagnose_git_state=True, command_runner=runner)

    # Ensure it returns the diagnostics result
    assert isinstance(result, ReviewBundleDiagnosticsResult)

    # Ensure no files were written to the review bundle path
    rb_path = tmp_path / "stories" / story / "review_bundle"
    written_files = list(rb_path.glob("**/*"))
    assert not written_files or all(f.name == ".gitkeep" for f in written_files)


def test_cli_diagnose_git_state_does_not_run_pytest_or_ruff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")

    import subprocess
    executed_commands = []

    outputs = {
        "git rev-parse --is-inside-work-tree": "true\n",
        "git rev-parse --show-toplevel": f"{tmp_path.resolve()}\n",
        "git rev-parse --git-dir": ".git\n",
        "git branch --show-current": "main\n",
        "git rev-parse --is-shallow-repository": "false\n",
        "git rev-parse --verify origin/main": f"{BASE_SHA}\n",
        "git rev-parse --verify refs/remotes/origin/main": f"{BASE_SHA}\n",
        f"git rev-parse --verify refs/remotes/{BASE_SHA}": (1, "", "fatal: Needed a single revision\n"),
        f"git rev-parse --verify {BASE_SHA}": f"{BASE_SHA}\n",
        "git rev-parse HEAD": f"{HEAD_SHA}\n",
        "git merge-base HEAD origin/main": f"{BASE_SHA}\n",
        f"git merge-base HEAD {BASE_SHA}": f"{BASE_SHA}\n",
        "git diff --stat": "",
        "git diff --cached": "",
        "git diff": "",
        f"git diff --stat {BASE_SHA}..HEAD": "",
        f"git diff --name-only {BASE_SHA}..HEAD": "",
        f"git diff {BASE_SHA}..HEAD": "",
        f"git diff --stat {BASE_SHA}..{HEAD_SHA}": "",
        f"git diff --name-only {BASE_SHA}..{HEAD_SHA}": "",
        f"git diff {BASE_SHA}..{HEAD_SHA}": "",
        f"git rev-list --count {BASE_SHA}..{HEAD_SHA}": "1\n",
        "git ls-files --others --exclude-standard": "",
        "git ls-files --others --ignored --exclude-standard": "",
        "git status --short": "",
        "git log --oneline -5": "c2ec13b fix: msg\n",
        f"git log --reverse --format=%H%x09%s {BASE_SHA}..{HEAD_SHA}": "c2ec13b\tfix: msg\n",
        f"git diff --binary {BASE_SHA}..{HEAD_SHA}": "",
        f"git diff --summary {BASE_SHA}..{HEAD_SHA}": "",
        f"git diff --name-status {BASE_SHA}..{HEAD_SHA}": "",
        "git ls-files": "",
        "git diff --cached --name-only": "",
        "git diff --name-only": "",
    }

    def fake_subprocess_run(command, *args, **kwargs):
        cmd_str = " ".join(command) if isinstance(command, list) else command
        executed_commands.append(cmd_str)

        val = outputs.get(cmd_str, "")
        returncode = 0
        stdout = val
        stderr = ""
        if isinstance(val, tuple):
            returncode, stdout, stderr = val

        return subprocess.CompletedProcess(
            args=command,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr
        )

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "review-bundle", "--story", story, "--diagnose-git-state"])

    main()

    captured = capsys.readouterr().out
    assert "Review Bundle Diagnostics" in captured

    # Prove that neither pytest nor ruff was passed to the command runner
    for cmd in executed_commands:
        assert "pytest" not in cmd
        assert "ruff" not in cmd


def test_diagnose_git_state_existing_bundle_unmodified(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    story_dir = tmp_path / "stories" / story
    story_dir.mkdir(parents=True)
    (story_dir / "story.md").write_text("# story\n", encoding="utf-8")

    runner = mock_git_runner(tmp_path, {})
    rb_path = story_dir / "review_bundle"
    assert not rb_path.exists()

    # 1. No existing review bundle
    create_review_bundle(tmp_path, story, diagnose_git_state=True, command_runner=runner)
    assert not rb_path.exists()

    # 2. Existing review bundle containing multiple files and nested directories
    rb_path.mkdir()
    file1 = rb_path / "file1.txt"
    file1.write_text("file1 content", encoding="utf-8")

    nested_dir = rb_path / "nested"
    nested_dir.mkdir()
    file2 = nested_dir / "file2.bin"
    file2.write_bytes(b"binary content")

    import os
    import time

    def get_bundle_state():
        state = {}
        for root, dirs, files in os.walk(rb_path):
            for f in files:
                p = Path(root) / f
                rel = p.relative_to(rb_path)
                stat = p.stat()
                state[rel] = {
                    "bytes": p.read_bytes(),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
        return state

    state_before = get_bundle_state()
    assert len(state_before) == 2

    # Sleep slightly to ensure if a timestamp did update we would detect it
    time.sleep(0.01)

    create_review_bundle(tmp_path, story, diagnose_git_state=True, command_runner=runner)

    state_after = get_bundle_state()

    assert len(state_before) == len(state_after)
    for rel_path, before in state_before.items():
        assert rel_path in state_after
        after = state_after[rel_path]
        assert before["bytes"] == after["bytes"]
        assert before["size"] == after["size"]
        assert before["mtime"] == after["mtime"]


def test_validation_rejects_stale_bundles(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")

    runner = mock_git_runner(tmp_path, {})
    create_review_bundle(tmp_path, story, command_runner=runner)

    # Change current HEAD SHA in the repository and try validating
    stale_runner = mock_git_runner(tmp_path, {}, head_sha="DIFFERENT_SHA")
    validation = validate_review_bundle(tmp_path, story, command_runner=stale_runner)
    assert validation.valid is False
    assert any("HEAD changed" in r for r in validation.reasons)


def test_cli_review_bundle_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")

    captured: dict[str, bool] = {}

    def fake_create_review_bundle(
        project_path, story_name, base_ref="origin/main", command_runner=None,
        strict_clean=False, diagnose_git_state=False, allow_generated_artifacts=False, host_identity_file=None
    ):
        captured["strict_clean"] = strict_clean
        captured["diagnose_git_state"] = diagnose_git_state
        captured["allow_generated_artifacts"] = allow_generated_artifacts

        story_path = project_path / "stories" / story_name
        (story_path / "review_bundle").mkdir(exist_ok=True)
        return ReviewBundleResult(story_path / "review_bundle", [], True, True, True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("agentic_dev.cli.create_review_bundle", fake_create_review_bundle)

    monkeypatch.setattr("sys.argv", ["agentic", "review-bundle", "--story", story, "--strict-clean", "--diagnose-git-state", "--allow-generated-artifacts"])
    main()

    assert captured["strict_clean"] is True
    assert captured["diagnose_git_state"] is True
    assert captured["allow_generated_artifacts"] is True


def test_diagnose_git_state_only_runs_readonly_git_commands(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")

    executed_commands = []
    base_runner = mock_git_runner(tmp_path, {})
    def track_commands(command: list[str], cwd: Path) -> CommandResult:
        executed_commands.append(" ".join(command))
        return base_runner(command, cwd)

    create_review_bundle(tmp_path, story, diagnose_git_state=True, command_runner=track_commands)

    forbidden_subcommands = {"add", "commit", "checkout", "reset", "push", "pull", "merge", "rebase", "rm", "clone"}
    for cmd in executed_commands:
        parts = cmd.split()
        if len(parts) >= 2 and parts[0] == "git":
            assert parts[1] not in forbidden_subcommands, f"Mutating git command executed: {cmd}"


def test_validation_rejects_bundle_with_mismatched_repository_state(tmp_path: Path) -> None:
    from test_review_state_service import FixedRunner, Result
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "stories" / story / "story.md").write_text("# story\n", encoding="utf-8")

    runner = mock_git_runner(tmp_path, {})
    create_review_bundle(tmp_path, story, command_runner=runner)

    # 1. Reject on HEAD SHA mismatch
    stale_runner = mock_git_runner(tmp_path, {}, head_sha="DIFFERENT_HEAD_SHA")
    validation = validate_review_bundle(tmp_path, story, command_runner=stale_runner)
    assert validation.valid is False
    assert any("HEAD changed" in r for r in validation.reasons)

    # 2. Reject on branch mismatch
    class BranchMismatchRunner(FixedRunner):
        def __call__(self, command: list[str], cwd: Path) -> Result:
            text = " ".join(command)
            if text == "git branch --show-current":
                return Result(0, "different_branch\n", "")
            return super().__call__(command, cwd)

    FixedRunner_runner = FixedRunner()
    create_review_bundle(tmp_path, story, command_runner=FixedRunner_runner)
    validation = validate_review_bundle(tmp_path, story, command_runner=BranchMismatchRunner())
    assert validation.valid is False
    assert any("branch changed" in r for r in validation.reasons)
