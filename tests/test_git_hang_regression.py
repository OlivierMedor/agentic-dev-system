import os
from pathlib import Path

from agentic_dev.review_state.git_identity import run_git

def test_run_git_no_pager(tmp_path: Path):
    """
    Ensure run_git uses safe Git execution defaults that prevent paging and hanging
    during large diff outputs or credential prompts.
    """
    # Create a dummy git repo with a large file
    run_git(["git", "init"], tmp_path)
    
    # Configure local git
    run_git(["git", "config", "user.name", "Test User"], tmp_path)
    run_git(["git", "config", "user.email", "test@example.com"], tmp_path)
    
    large_file = tmp_path / "large.txt"
    # Create a 2000 line file, to trigger typical pagers
    large_file.write_text("\n".join(f"Line {i}" for i in range(2000)))
    
    run_git(["git", "add", "large.txt"], tmp_path)
    run_git(["git", "commit", "-m", "Initial large file"], tmp_path)
    
    # Modify the file entirely
    large_file.write_text("\n".join(f"Changed {i}" for i in range(2000)))
    
    # Ensure our wrapper doesn't hang on large diffs
    # Even if global core.pager is set to something blocking, the environment overrides it.
    run_git(["git", "config", "core.pager", "less"], tmp_path)
    
    result = run_git(["git", "diff"], tmp_path)
    
    assert result.returncode == 0
    assert "Changed 1999" in result.stdout
    assert "Line 1999" in result.stdout
