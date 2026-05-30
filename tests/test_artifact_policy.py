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
        ".agentic/support_queue/pending/.gitkeep",
        ".env.example",
    ]

    assert find_artifact_policy_violations(allowed_paths) == []


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


def test_support_queue_runtime_files_are_blocked_except_gitkeep() -> None:
    blocked_paths = [
        ".agentic/support_queue/pending/SUPPORT-001.yaml",
        ".agentic/support_queue/pending/SUPPORT-001_cloud_packet.md",
    ]

    assert violation_paths([*blocked_paths, ".agentic/support_queue/pending/.gitkeep"]) == blocked_paths


def test_review_to_chatgpt_artifacts_are_blocked() -> None:
    assert violation_paths(["review_to_chatgpt/handoff.md"]) == ["review_to_chatgpt/handoff.md"]


def test_zip_artifacts_are_blocked() -> None:
    assert violation_paths(["agentic_story001_review.zip"]) == ["agentic_story001_review.zip"]


def test_environment_files_are_blocked_except_example() -> None:
    assert violation_paths([".env", ".env.local", ".env.example"]) == [".env", ".env.local"]


def test_multiple_violations_are_all_reported() -> None:
    paths = [
        "src/agentic_dev/cli.py",
        "stories/story_011_artifact_policy_guard/review_bundle/handoff.md",
        "stories/story_011_artifact_policy_guard/cloud_review_packet/cloud_review_prompt.md",
        "review_to_chatgpt/handoff.md",
        "agentic_story001_review.zip",
        ".env.local",
        ".env.example",
    ]

    assert violation_paths(paths) == [
        "stories/story_011_artifact_policy_guard/review_bundle/handoff.md",
        "stories/story_011_artifact_policy_guard/cloud_review_packet/cloud_review_prompt.md",
        "review_to_chatgpt/handoff.md",
        "agentic_story001_review.zip",
        ".env.local",
    ]
