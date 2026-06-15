from agentic_dev.artifact_policy import find_artifact_policy_violations


def violation_paths(paths: list[str]) -> list[str]:
    return [violation.path for violation in find_artifact_policy_violations(paths)]


def test_allowed_project_paths_do_not_violate_artifact_policy() -> None:
    allowed_paths = [
        "src/agentic_dev/cli.py",
        "stories/story_011_artifact_policy_guard/story.md",
        "stories/story_011_artifact_policy_guard/reports/test_report.md",
        "stories/story_011_artifact_policy_guard/prompt_pack/04_test_agent_prompt.md",
        "stories/story_011_artifact_policy_guard/agent_plan.yaml",
        "stories/story_011_artifact_policy_guard/story_runbook.md",
        "stories/story_011_artifact_policy_guard/review_bundle/.gitkeep",
        "stories/story_011_artifact_policy_guard/cloud_review_packet/.gitkeep",
        "stories/story_011_artifact_policy_guard/remote_dev_validation/.gitkeep",
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
        ".env.example",
        "blueprints/agentic-architecture.example.md",
    ]

    assert find_artifact_policy_violations(allowed_paths) == []


def test_private_operator_guidance_is_blocked() -> None:
    assert violation_paths(["blueprints/agentic-architecture.md"]) == [
        "blueprints/agentic-architecture.md",
    ]


def test_generated_review_bundle_files_are_blocked() -> None:
    blocked_paths = [
        "stories/story_011_artifact_policy_guard/review_bundle/handoff.md",
        "stories/story_011_artifact_policy_guard/review_bundle/git_diff.patch",
        "stories/story_011_artifact_policy_guard/review_bundle/pytest_output.txt",
    ]

    assert violation_paths(blocked_paths) == blocked_paths


def test_generated_cloud_review_packet_files_are_blocked() -> None:
    blocked_paths = [
        "stories/story_011_artifact_policy_guard/cloud_review_packet/cloud_review_prompt.md",
        "stories/story_011_artifact_policy_guard/cloud_review_packet/cloud_review_context.md",
    ]

    assert violation_paths(blocked_paths) == blocked_paths


def test_generated_remote_dev_validation_files_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        "stories/story_024_remote_dev_validation_bundle/remote_dev_validation/remote_dev_packet.md",
        "stories/story_024_remote_dev_validation_bundle/remote_dev_validation/remote_dev_result_template.yaml",
    ]

    assert violation_paths(
        [
            *blocked_paths,
            "stories/story_024_remote_dev_validation_bundle/remote_dev_validation/.gitkeep",
        ],
    ) == blocked_paths


def test_support_queue_runtime_files_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        ".agentic/support_queue/pending/SUPPORT-001.yaml",
        ".agentic/support_queue/pending/SUPPORT-001_cloud_packet.md",
    ]

    assert violation_paths([*blocked_paths, ".agentic/support_queue/pending/.gitkeep"]) == blocked_paths


def test_feature_scan_runtime_files_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        ".agentic/feature_scan/feature_scan_packet.md",
        ".agentic/feature_scan/feature_suggestions_template.yaml",
        ".agentic/feature_scan/feature_record_report.md",
    ]

    assert violation_paths([*blocked_paths, ".agentic/feature_scan/.gitkeep"]) == blocked_paths


def test_local_model_scorecard_results_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        ".agentic/local_model_scorecard/results/qwen3/run_summary.md",
        ".agentic/local_model_scorecard/results/qwen3/developer_agent_prompt_response.md",
        ".agentic/local_model_scorecard/results/qwen3/developer_agent_prompt_raw_response.json",
        "reports/local_model_scorecard_report.md",
        ".agentic/local_model_scorecard/scorecard_scores.yaml",
        "reports/local_model_role_recommendations.md",
        "reports/local_model_role_recommendations.yaml",
    ]

    assert violation_paths(
        [*blocked_paths, ".agentic/local_model_scorecard/results/.gitkeep"],
    ) == blocked_paths


def test_local_agent_draft_outputs_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        "stories/story_045_local_agent_draft_runner/reports/local_agent_drafts/docs_agent_gemma-4-26b_draft.md",
        "stories/story_045_local_agent_draft_runner/reports/local_agent_drafts/docs_agent_gemma-4-26b_draft.yaml",
        "stories/story_045_local_agent_draft_runner/reports/local_agent_drafts/docs_agent_gemma-4-26b_raw_response.json",
    ]

    assert violation_paths(
        [
            *blocked_paths,
            "stories/story_045_local_agent_draft_runner/reports/local_agent_drafts/.gitkeep",
        ],
    ) == blocked_paths


def test_local_agent_context_packets_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        "stories/story_047_local_agent_prompt_slimming/reports/local_agent_context/docs_agent_gemma-4-26b_context.md",
        "stories/story_047_local_agent_prompt_slimming/reports/local_agent_context/test_agent_devstral_context.md",
    ]

    assert violation_paths(
        [
            *blocked_paths,
            "stories/story_047_local_agent_prompt_slimming/reports/local_agent_context/.gitkeep",
        ],
    ) == blocked_paths


def test_role_context_packets_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        "stories/story_051_role_specific_context_builder/reports/role_context/developer_agent_context.md",
        "stories/story_051_role_specific_context_builder/reports/role_context/test_agent_context.md",
    ]

    assert violation_paths(
        [
            *blocked_paths,
            "stories/story_051_role_specific_context_builder/reports/role_context/.gitkeep",
        ],
    ) == blocked_paths


def test_codex_task_files_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        "stories/story_052_codex_runtime_connector/reports/codex_tasks/developer_agent_codex_task.md",
        "stories/story_052_codex_runtime_connector/reports/codex_tasks/test_agent_codex_task.md",
    ]

    assert violation_paths(
        [
            *blocked_paths,
            "stories/story_052_codex_runtime_connector/reports/codex_tasks/.gitkeep",
        ],
    ) == blocked_paths


def test_codex_runtime_output_files_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        "stories/story_056/reports/codex_runtime/developer_agent_stdout.txt",
        "stories/story_056/reports/codex_runtime/developer_agent_stderr.txt",
    ]

    assert violation_paths(
        [
            *blocked_paths,
            "stories/story_056/reports/codex_runtime/.gitkeep",
        ],
    ) == blocked_paths


def test_local_model_raw_response_files_are_blocked() -> None:
    blocked_paths = [
        "reports/debug_docs_agent_prompt_raw_response.json",
        "reports/nested/debug_docs_agent_prompt_raw_response.json",
        "stories/story_047_local_agent_prompt_slimming/reports/local_agent_context/docs_agent_gemma_raw_response.json",
    ]

    assert violation_paths(blocked_paths) == blocked_paths


def test_runtime_queue_item_files_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        ".agentic/improvement_queue/pending/IMP-20260605-120000.yaml",
        ".agentic/maintenance_queue/approved/MAINT-20260605-120000.yaml",
        ".agentic/feature_queue/closed/FEATURE-20260605-120000.yaml",
    ]

    assert violation_paths(
        [
            *blocked_paths,
            ".agentic/improvement_queue/pending/.gitkeep",
            ".agentic/maintenance_queue/approved/.gitkeep",
            ".agentic/feature_queue/closed/.gitkeep",
        ],
    ) == blocked_paths


def test_review_to_chatgpt_artifacts_are_blocked() -> None:
    assert violation_paths(["review_to_chatgpt/handoff.md"]) == ["review_to_chatgpt/handoff.md"]


def test_zip_artifacts_are_blocked() -> None:
    assert violation_paths(["agentic_story001_review.zip"]) == ["agentic_story001_review.zip"]


def test_environment_files_are_blocked_except_example() -> None:
    assert violation_paths([".env", ".env.local", ".env.example"]) == [".env", ".env.local"]


def test_codex_auth_and_config_state_are_blocked() -> None:
    blocked_paths = [
        ".codex/auth.json",
        ".codex/config.toml",
        ".codex/sessions/session.jsonl",
        "codex-home/auth.json",
        "codex-auth/auth.json",
        "tmp/.codex/auth.json",
    ]

    assert violation_paths(blocked_paths) == blocked_paths


def test_multiple_violations_are_all_reported() -> None:
    paths = [
        "src/agentic_dev/cli.py",
        "stories/story_011_artifact_policy_guard/review_bundle/handoff.md",
        "stories/story_011_artifact_policy_guard/cloud_review_packet/cloud_review_prompt.md",
        "stories/story_011_artifact_policy_guard/remote_dev_validation/remote_dev_packet.md",
        ".agentic/local_model_scorecard/results/qwen3/run_summary.md",
        "stories/story_045_local_agent_draft_runner/reports/local_agent_drafts/docs_agent_gemma-4-26b_draft.md",
        "stories/story_051_role_specific_context_builder/reports/role_context/developer_agent_context.md",
        "stories/story_052_codex_runtime_connector/reports/codex_tasks/developer_agent_codex_task.md",
        "stories/story_056/reports/codex_runtime/developer_agent_stdout.txt",
        "reports/debug_docs_agent_prompt_raw_response.json",
        "reports/local_model_scorecard_report.md",
        ".agentic/local_model_scorecard/scorecard_scores.yaml",
        "reports/local_model_role_recommendations.md",
        "reports/local_model_role_recommendations.yaml",
        "review_to_chatgpt/handoff.md",
        "agentic_story001_review.zip",
        ".env.local",
        ".codex/auth.json",
        ".env.example",
    ]

    assert violation_paths(paths) == [
        "stories/story_011_artifact_policy_guard/review_bundle/handoff.md",
        "stories/story_011_artifact_policy_guard/cloud_review_packet/cloud_review_prompt.md",
        "stories/story_011_artifact_policy_guard/remote_dev_validation/remote_dev_packet.md",
        ".agentic/local_model_scorecard/results/qwen3/run_summary.md",
        "stories/story_045_local_agent_draft_runner/reports/local_agent_drafts/docs_agent_gemma-4-26b_draft.md",
        "stories/story_051_role_specific_context_builder/reports/role_context/developer_agent_context.md",
        "stories/story_052_codex_runtime_connector/reports/codex_tasks/developer_agent_codex_task.md",
        "stories/story_056/reports/codex_runtime/developer_agent_stdout.txt",
        "reports/debug_docs_agent_prompt_raw_response.json",
        "reports/local_model_scorecard_report.md",
        ".agentic/local_model_scorecard/scorecard_scores.yaml",
        "reports/local_model_role_recommendations.md",
        "reports/local_model_role_recommendations.yaml",
        "review_to_chatgpt/handoff.md",
        "agentic_story001_review.zip",
        ".env.local",
        ".codex/auth.json",
    ]
