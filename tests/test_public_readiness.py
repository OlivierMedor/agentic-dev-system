from pathlib import Path

import pytest

from agentic_dev.cli import main
from agentic_dev.public_readiness import (
    find_public_readiness_violations,
    run_public_readiness,
)


def violation_paths(paths: list[str]) -> list[str]:
    return [violation.path for violation in find_public_readiness_violations(paths)]


def test_public_readiness_passes_for_safe_tracked_files() -> None:
    safe_paths = [
        "README.md",
        "docs/public_readiness.md",
        "blueprints/agentic-architecture.example.md",
        ".env.example",
        "stories/story_033_public_readiness_private_instructions/review_bundle/.gitkeep",
        "stories/story_033_public_readiness_private_instructions/cloud_review_packet/.gitkeep",
        "stories/story_033_public_readiness_private_instructions/remote_dev_validation/.gitkeep",
        ".agentic/support_queue/pending/.gitkeep",
        ".agentic/feature_scan/.gitkeep",
        ".agentic/local_model_scorecard/prompts/developer_agent_prompt.md",
        ".agentic/local_model_scorecard/scorecard_template.yaml",
        ".agentic/local_model_scorecard/results/.gitkeep",
        "stories/story_045_local_agent_draft_runner/reports/local_agent_drafts/.gitkeep",
        "stories/story_047_local_agent_prompt_slimming/reports/local_agent_context/.gitkeep",
        "stories/story_051_role_specific_context_builder/reports/role_context/.gitkeep",
        "stories/story_052_codex_runtime_connector/reports/codex_tasks/.gitkeep",
        "stories/story_056/reports/codex_runtime/.gitkeep",
        ".agentic/improvement_queue/pending/.gitkeep",
        ".agentic/maintenance_queue/pending/.gitkeep",
        ".agentic/feature_queue/pending/.gitkeep",
    ]

    assert find_public_readiness_violations(safe_paths) == []


def test_public_readiness_blocks_private_operator_guidance() -> None:
    assert violation_paths(["blueprints/agentic-architecture.md"]) == [
        "blueprints/agentic-architecture.md",
    ]


def test_public_readiness_blocks_env_files_but_allows_env_example() -> None:
    assert violation_paths([".env", ".env.local", ".env.example"]) == [".env", ".env.local"]


def test_public_readiness_blocks_codex_auth_and_config_state() -> None:
    blocked_paths = [
        ".codex/auth.json",
        ".codex/config.toml",
        ".codex/sessions/session.jsonl",
        "codex-home/auth.json",
        "codex-auth/auth.json",
        "tmp/.codex/auth.json",
    ]

    assert violation_paths(blocked_paths) == blocked_paths


def test_public_readiness_blocks_review_bundles() -> None:
    blocked_paths = [
        "stories/story_033_public_readiness_private_instructions/review_bundle/handoff.md",
        "stories/story_033_public_readiness_private_instructions/review_bundle/git_diff.patch",
    ]

    assert violation_paths(blocked_paths) == blocked_paths


def test_public_readiness_blocks_cloud_review_packets() -> None:
    blocked_paths = [
        "stories/story_033_public_readiness_private_instructions/cloud_review_packet/cloud_review_export.md",
        "stories/story_033_public_readiness_private_instructions/cloud_review_packet/cloud_review_prompt.md",
    ]

    assert violation_paths(blocked_paths) == blocked_paths


def test_public_readiness_blocks_support_queue_runtime_files() -> None:
    blocked_paths = [
        ".agentic/support_queue/pending/SUPPORT-20260605-120000.yaml",
        ".agentic/support_queue/pending/SUPPORT-20260605-120000_cloud_packet.md",
    ]

    assert violation_paths([*blocked_paths, ".agentic/support_queue/pending/.gitkeep"]) == blocked_paths


def test_public_readiness_blocks_other_runtime_artifacts() -> None:
    blocked_paths = [
        "review_to_chatgpt/handoff.md",
        "agentic_story033_review.zip",
        "stories/story_033_public_readiness_private_instructions/remote_dev_validation/remote_dev_packet.md",
        ".agentic/feature_scan/feature_scan_packet.md",
        ".agentic/feature_scan/feature_suggestions_template.yaml",
        ".agentic/local_model_scorecard/results/qwen3/run_summary.md",
        ".agentic/local_model_scorecard/results/qwen3/developer_agent_prompt_response.md",
        ".agentic/local_model_scorecard/results/qwen3/developer_agent_prompt_raw_response.json",
        "stories/story_045_local_agent_draft_runner/reports/local_agent_drafts/docs_agent_gemma-4-26b_draft.md",
        "stories/story_045_local_agent_draft_runner/reports/local_agent_drafts/docs_agent_gemma-4-26b_draft.yaml",
        "stories/story_045_local_agent_draft_runner/reports/local_agent_drafts/docs_agent_gemma-4-26b_raw_response.json",
        "stories/story_047_local_agent_prompt_slimming/reports/local_agent_context/docs_agent_gemma-4-26b_context.md",
        "stories/story_051_role_specific_context_builder/reports/role_context/developer_agent_context.md",
        "stories/story_052_codex_runtime_connector/reports/codex_tasks/developer_agent_codex_task.md",
        "stories/story_056/reports/codex_runtime/developer_agent_stdout.txt",
        "reports/debug_docs_agent_prompt_raw_response.json",
        "reports/local_model_scorecard_report.md",
        ".agentic/local_model_scorecard/scorecard_scores.yaml",
        "reports/local_model_role_recommendations.md",
        "reports/local_model_role_recommendations.yaml",
        ".agentic/improvement_queue/pending/IMP-20260605-120000.yaml",
        ".agentic/maintenance_queue/pending/MAINT-20260605-120000.yaml",
        ".agentic/feature_queue/pending/FEATURE-20260605-120000.yaml",
        ".codex/auth.json",
    ]

    assert violation_paths(blocked_paths) == blocked_paths


def test_public_readiness_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "agentic_dev.public_readiness.run_git_ls_files",
        lambda _project_path: ["README.md", ".env"],
    )

    result = run_public_readiness(tmp_path)

    assert result.passed is False
    assert result.report_path == tmp_path / "reports" / "public_readiness_report.md"
    assert result.report_path.exists()
    report = result.report_path.read_text(encoding="utf-8")
    assert "# Public Readiness Report" in report
    assert "- Status: FAIL" in report
    assert "`.env`" in report


def test_cli_public_readiness_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "agentic_dev.public_readiness.run_git_ls_files",
        lambda _project_path: ["README.md", ".env.example"],
    )
    monkeypatch.setattr("sys.argv", ["agentic", "public-readiness"])

    main()

    captured = capsys.readouterr()
    assert "Public readiness passed" in captured.out
    assert "Report written to:" in captured.out
    assert (tmp_path / "reports" / "public_readiness_report.md").exists()


def test_cli_public_readiness_exits_nonzero_on_violations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "agentic_dev.public_readiness.run_git_ls_files",
        lambda _project_path: ["blueprints/agentic-architecture.md"],
    )
    monkeypatch.setattr("sys.argv", ["agentic", "public-readiness"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 1


def test_readme_links_to_public_readiness_doc() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "docs/public_readiness.md" in readme
    assert "agentic public-readiness" in readme


def test_public_readiness_doc_and_example_exist() -> None:
    guide = Path("docs/public_readiness.md").read_text(encoding="utf-8")
    example = Path("blueprints/agentic-architecture.example.md").read_text(encoding="utf-8")

    assert "blueprints/agentic-architecture.md" in guide
    assert "blueprints/agentic-architecture.example.md" in guide
    assert "docker compose run --rm dev agentic public-readiness" in guide
    assert "must not be committed" in example
