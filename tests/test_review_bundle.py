from pathlib import Path

from agentic_dev.review_bundle import CommandResult, create_review_bundle


BASE_SHA = "5f0d9fda8b6b0a89ed6c6ef819a6937630d79d3e"
HEAD_SHA = "c2ec13bfefe6e8cf35d2f6ac4dc2f3a20193b47a"


def passing_runner(command: list[str], cwd: Path) -> CommandResult:
    command_text = " ".join(command)
    outputs = {
        "git merge-base HEAD origin/main": f"{BASE_SHA}\n",
        "git rev-parse HEAD": f"{HEAD_SHA}\n",
        "git diff --stat": " src/agentic_dev/demo_subtasks.py | 10 +++++-----\n 1 file changed, 5 insertions(+), 5 deletions(-)\n",
        "git diff --cached": "diff --git a/README.md b/README.md\n",
        "git diff": "diff --git a/src/agentic_dev/demo_subtasks.py b/src/agentic_dev/demo_subtasks.py\n",
        f"git diff --stat {BASE_SHA}..HEAD": " src/agentic_dev/demo_subtasks.py | 10 +++++-----\n 1 file changed, 5 insertions(+), 5 deletions(-)\n",
        f"git diff --name-only {BASE_SHA}..HEAD": "src/agentic_dev/demo_subtasks.py\nsrc/agentic_dev/subtask_execution.py\n",
        f"git diff {BASE_SHA}..HEAD": (
            "diff --git a/src/agentic_dev/demo_subtasks.py b/src/agentic_dev/demo_subtasks.py\n"
            "diff --git a/src/agentic_dev/subtask_execution.py b/src/agentic_dev/subtask_execution.py\n"
        ),
        "git ls-files --others --exclude-standard": "",
        "git status --short": "",
        "git log --oneline -5": "c2ec13b fix: harden real local subtask demo execution\n",
        "pytest": "12 passed in 0.34s\n",
        "ruff check .": "All checks passed!\n",
    }
    stdout = outputs.get(command_text, f"ran from {cwd}: {command_text}\n")

    return CommandResult(
        command=" ".join(command),
        returncode=0,
        stdout=stdout,
        stderr="",
    )


def test_create_review_bundle_writes_expected_files(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    story_path = tmp_path / "stories" / story
    story_path.mkdir(parents=True)

    result = create_review_bundle(tmp_path, story, command_runner=passing_runner)

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
    assert "- untracked files: 0" in handoff
    assert "- skipped untracked files: 0" in handoff
    assert "- staged changes: yes" in handoff
    assert "- unstaged changes: yes" in handoff
    assert f"- base sha: `{BASE_SHA}`" in handoff
    assert f"- head sha: `{HEAD_SHA}`" in handoff
    assert "committed diff present: yes" in handoff


def test_file_tree_excludes_noisy_folders(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")

    noisy_folders = [
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "review_to_chatgpt",
    ]

    for folder in noisy_folders:
        noisy_path = tmp_path / folder
        noisy_path.mkdir()
        (noisy_path / "noise.txt").write_text("noise\n", encoding="utf-8")

    result = create_review_bundle(tmp_path, story, command_runner=passing_runner)

    file_tree = (result.review_bundle_path / "file_tree.txt").read_text(encoding="utf-8")
    assert "src/app.py" in file_tree

    for folder in noisy_folders:
        assert folder not in file_tree


def test_command_failures_are_written_to_output_files(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)

    def failing_pytest_runner(command: list[str], cwd: Path) -> CommandResult:
        if command == ["git", "merge-base", "HEAD", "origin/main"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"{BASE_SHA}\n",
                stderr="",
            )

        if command == ["git", "rev-parse", "HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"{HEAD_SHA}\n",
                stderr="",
            )

        if command == ["git", "diff", "--stat", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="",
                stderr="",
            )

        if command == ["git", "diff", "--name-only", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="src/agentic_dev/demo_subtasks.py\n",
                stderr="",
            )

        if command == ["git", "diff", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="diff --git a/src/agentic_dev/demo_subtasks.py b/src/agentic_dev/demo_subtasks.py\n",
                stderr="",
            )

        if command == ["pytest"]:
            return CommandResult(
                command="pytest",
                returncode=1,
                stdout="one test failed\n",
                stderr="failure details\n",
            )

        return CommandResult(
            command=" ".join(command),
            returncode=0,
            stdout="",
            stderr="",
        )

    result = create_review_bundle(tmp_path, story, command_runner=failing_pytest_runner)

    pytest_output = (result.review_bundle_path / "pytest_output.txt").read_text(
        encoding="utf-8",
    )
    handoff = (result.review_bundle_path / "handoff.md").read_text(encoding="utf-8")

    assert result.pytest_passed is False
    assert result.ruff_passed is True
    assert "Status: FAILED" in pytest_output
    assert "one test failed" in pytest_output
    assert "failure details" in pytest_output
    assert "- pytest: failed" in handoff
    assert "Fix the failing checks" in handoff


def test_untracked_file_outputs_include_safe_text_file_contents(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "review.txt").write_text("new review notes\n", encoding="utf-8")

    def runner(command: list[str], cwd: Path) -> CommandResult:
        if command == ["git", "merge-base", "HEAD", "origin/main"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"{BASE_SHA}\n",
                stderr="",
            )

        if command == ["git", "rev-parse", "HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"{HEAD_SHA}\n",
                stderr="",
            )

        if command == ["git", "diff", "--stat", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="",
                stderr="",
            )

        if command == ["git", "diff", "--name-only", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="notes/review.txt\n",
                stderr="",
            )

        if command == ["git", "diff", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="diff --git a/notes/review.txt b/notes/review.txt\n",
                stderr="",
            )

        if command == ["git", "ls-files", "--others", "--exclude-standard"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="notes/review.txt\n",
                stderr="",
            )

        return CommandResult(
            command=" ".join(command),
            returncode=0,
            stdout="",
            stderr="",
        )

    result = create_review_bundle(tmp_path, story, command_runner=runner)

    untracked_files = (result.review_bundle_path / "untracked_files.txt").read_text(
        encoding="utf-8",
    )
    contents = (result.review_bundle_path / "untracked_file_contents.md").read_text(
        encoding="utf-8",
    )
    skipped = (result.review_bundle_path / "skipped_untracked_files.txt").read_text(
        encoding="utf-8",
    )

    assert "notes/review.txt" in untracked_files
    assert "## `notes/review.txt`" in contents
    assert "new review notes" in contents
    assert "No untracked files were skipped." in skipped


def test_untracked_file_outputs_record_skipped_files(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)
    (tmp_path / ".env").write_text("SECRET=value\n", encoding="utf-8")
    (tmp_path / "large.txt").write_text("x" * 102_401, encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"hello\x00world")

    def runner(command: list[str], cwd: Path) -> CommandResult:
        if command == ["git", "merge-base", "HEAD", "origin/main"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"{BASE_SHA}\n",
                stderr="",
            )

        if command == ["git", "rev-parse", "HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"{HEAD_SHA}\n",
                stderr="",
            )

        if command == ["git", "diff", "--stat", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="",
                stderr="",
            )

        if command == ["git", "diff", "--name-only", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="",
                stderr="",
            )

        if command == ["git", "diff", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="",
                stderr="",
            )

        if command == ["git", "ls-files", "--others", "--exclude-standard"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=".env\nlarge.txt\nbinary.bin\n",
                stderr="",
            )

        return CommandResult(
            command=" ".join(command),
            returncode=0,
            stdout="",
            stderr="",
        )

    result = create_review_bundle(tmp_path, story, command_runner=runner)

    contents = (result.review_bundle_path / "untracked_file_contents.md").read_text(
        encoding="utf-8",
    )
    skipped = (result.review_bundle_path / "skipped_untracked_files.txt").read_text(
        encoding="utf-8",
    )
    handoff = (result.review_bundle_path / "handoff.md").read_text(encoding="utf-8")

    assert "SECRET=value" not in contents
    assert ".env: potential secret file" in skipped
    assert "large.txt: file too large" in skipped
    assert "binary.bin: binary or unreadable" in skipped
    assert "- untracked files: 3" in handoff
    assert "- skipped untracked files: 3" in handoff


def test_review_bundle_folders_are_not_captured_as_untracked_contents(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    story_path = tmp_path / "stories" / story
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir(parents=True)
    (review_bundle_path / "old.txt").write_text("old bundle output\n", encoding="utf-8")

    def runner(command: list[str], cwd: Path) -> CommandResult:
        if command == ["git", "merge-base", "HEAD", "origin/main"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"{BASE_SHA}\n",
                stderr="",
            )

        if command == ["git", "rev-parse", "HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"{HEAD_SHA}\n",
                stderr="",
            )

        if command == ["git", "diff", "--stat", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="",
                stderr="",
            )

        if command == ["git", "diff", "--name-only", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="stories/story_002_review_bundle_command/review_bundle/old.txt\n",
                stderr="",
            )

        if command == ["git", "diff", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="diff --git a/stories/story_002_review_bundle_command/review_bundle/old.txt b/stories/story_002_review_bundle_command/review_bundle/old.txt\n",
                stderr="",
            )

        if command == ["git", "ls-files", "--others", "--exclude-standard"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"stories/{story}/review_bundle/old.txt\n",
                stderr="",
            )

        return CommandResult(
            command=" ".join(command),
            returncode=0,
            stdout="",
            stderr="",
        )

    result = create_review_bundle(tmp_path, story, command_runner=runner)

    contents = (result.review_bundle_path / "untracked_file_contents.md").read_text(
        encoding="utf-8",
    )
    skipped = (result.review_bundle_path / "skipped_untracked_files.txt").read_text(
        encoding="utf-8",
    )

    assert "old bundle output" not in contents
    assert f"stories/{story}/review_bundle/old.txt: excluded path" in skipped


def test_untracked_file_command_failure_is_written_safely(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)

    def runner(command: list[str], cwd: Path) -> CommandResult:
        if command == ["git", "merge-base", "HEAD", "origin/main"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"{BASE_SHA}\n",
                stderr="",
            )

        if command == ["git", "rev-parse", "HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout=f"{HEAD_SHA}\n",
                stderr="",
            )

        if command == ["git", "diff", "--stat", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="",
                stderr="",
            )

        if command == ["git", "diff", "--name-only", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="",
                stderr="",
            )

        if command == ["git", "diff", f"{BASE_SHA}..HEAD"]:
            return CommandResult(
                command=" ".join(command),
                returncode=0,
                stdout="",
                stderr="",
            )

        if command == ["git", "ls-files", "--others", "--exclude-standard"]:
            return CommandResult(
                command=" ".join(command),
                returncode=128,
                stdout="",
                stderr="git failed\n",
            )

        return CommandResult(
            command=" ".join(command),
            returncode=0,
            stdout="",
            stderr="",
        )

    result = create_review_bundle(tmp_path, story, command_runner=runner)

    untracked_files = (result.review_bundle_path / "untracked_files.txt").read_text(
        encoding="utf-8",
    )
    contents = (result.review_bundle_path / "untracked_file_contents.md").read_text(
        encoding="utf-8",
    )

    assert "Status: FAILED" in untracked_files
    assert "git failed" in untracked_files
    assert "No safe untracked text files were captured." in contents


def test_create_review_bundle_records_committed_pr_diff_for_clean_branch(tmp_path: Path) -> None:
    story = "story_002_review_bundle_command"
    (tmp_path / "stories" / story).mkdir(parents=True)

    def clean_branch_runner(command: list[str], cwd: Path) -> CommandResult:
        command_text = " ".join(command)
        outputs = {
            "git merge-base HEAD origin/main": f"{BASE_SHA}\n",
            "git rev-parse HEAD": f"{HEAD_SHA}\n",
            "git diff --stat": "",
            "git diff --cached": "",
            "git diff": "",
            f"git diff --stat {BASE_SHA}..HEAD": " src/agentic_dev/demo_subtasks.py | 2 ++\n 1 file changed, 2 insertions(+)\n",
            f"git diff --name-only {BASE_SHA}..HEAD": "src/agentic_dev/demo_subtasks.py\n",
            f"git diff {BASE_SHA}..HEAD": (
                "diff --git a/src/agentic_dev/demo_subtasks.py b/src/agentic_dev/demo_subtasks.py\n"
                "+++ b/src/agentic_dev/demo_subtasks.py\n"
            ),
            "git ls-files --others --exclude-standard": "",
            "pytest": "12 passed in 0.34s\n",
            "ruff check .": "All checks passed!\n",
        }
        return CommandResult(
            command=command_text,
            returncode=0,
            stdout=outputs.get(command_text, f"ran from {cwd}: {command_text}\n"),
            stderr="",
        )

    result = create_review_bundle(tmp_path, story, command_runner=clean_branch_runner)

    handoff = (result.review_bundle_path / "handoff.md").read_text(encoding="utf-8")
    committed_patch = (result.review_bundle_path / "committed_diff.patch").read_text(
        encoding="utf-8",
    )
    committed_files = (result.review_bundle_path / "committed_changed_files.txt").read_text(
        encoding="utf-8",
    )

    assert "staged changes: no" in handoff
    assert "unstaged changes: no" in handoff
    assert "committed diff present: yes" in handoff
    assert f"base sha: `{BASE_SHA}`" in handoff
    assert "src/agentic_dev/demo_subtasks.py" in committed_files
    assert "diff --git a/src/agentic_dev/demo_subtasks.py" in committed_patch
    assert "Status: PASSED" in committed_patch
