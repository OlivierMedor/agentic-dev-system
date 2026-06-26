import shutil
import subprocess
from pathlib import Path

from agentic_dev.artifact_policy import find_artifact_policy_violations


STORY = "evidence-derived-local-execution-recording"

STORY_LIFECYCLE_ARTIFACTS = [
    f"stories/{STORY}/reports/local_execution_record.yaml",
    f"stories/{STORY}/reports/local_review_decision.yaml",
    f"stories/{STORY}/reports/local_execution_report.md",
    f"stories/{STORY}/reports/local_review_report.md",
    f"stories/{STORY}/reports/quality_gate_report.md",
    f"stories/{STORY}/reports/quality_gate_result.yaml",
    f"stories/{STORY}/reports/finalize_story_report.md",
    f"stories/{STORY}/reports/finalize_story_result.yaml",
    f"stories/{STORY}/reports/local_execution/state.yaml",
    f"stories/{STORY}/cloud_review_packet/cloud_review_prompt.md",
]

STATIC_STORY_FILES = [
    f"stories/{STORY}/story.md",
    f"stories/{STORY}/status.yaml",
    f"stories/{STORY}/agent_plan.yaml",
    f"stories/{STORY}/test_plan.yaml",
    f"stories/{STORY}/monitoring_plan.yaml",
    f"stories/{STORY}/cloud_review_packet/.gitkeep",
    f"stories/{STORY}/reports/local_execution/.gitkeep",
]

LEGACY_ROLE_AGENT_REPORTS = [
    f"stories/{STORY}/reports/developer_report.md",
    f"stories/{STORY}/reports/test_report.md",
    f"stories/{STORY}/reports/test_layer_report.md",
    f"stories/{STORY}/reports/test_layer_result.yaml",
]


def run_git(project_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )


def write_files(project_path: Path, paths: list[str]) -> None:
    for relative_path in paths:
        path = project_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test\n", encoding="utf-8")


def test_story_067_lifecycle_artifacts_are_classified_as_generated() -> None:
    violations = find_artifact_policy_violations(STORY_LIFECYCLE_ARTIFACTS)

    assert [violation.path for violation in violations] == STORY_LIFECYCLE_ARTIFACTS


def test_legacy_role_agent_reports_remain_trackable() -> None:
    assert find_artifact_policy_violations(LEGACY_ROLE_AGENT_REPORTS) == []


def test_static_story_files_remain_trackable() -> None:
    assert find_artifact_policy_violations(STATIC_STORY_FILES) == []


def test_git_add_dot_does_not_stage_story_067_lifecycle_artifacts(tmp_path: Path) -> None:
    shutil.copyfile(Path(".gitignore"), tmp_path / ".gitignore")
    assert run_git(tmp_path, "init").returncode == 0
    write_files(tmp_path, STORY_LIFECYCLE_ARTIFACTS + STATIC_STORY_FILES + LEGACY_ROLE_AGENT_REPORTS)

    add_result = run_git(tmp_path, "add", ".")
    assert add_result.returncode == 0, add_result.stderr

    staged = run_git(tmp_path, "diff", "--cached", "--name-only")
    assert staged.returncode == 0, staged.stderr
    staged_paths = set(staged.stdout.splitlines())

    for artifact_path in STORY_LIFECYCLE_ARTIFACTS:
        assert artifact_path not in staged_paths

    for static_path in STATIC_STORY_FILES:
        assert static_path in staged_paths

    for legacy_path in LEGACY_ROLE_AGENT_REPORTS:
        assert legacy_path in staged_paths
