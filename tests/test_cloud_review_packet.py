from pathlib import Path

import pytest

from agentic_dev.cli import main
from agentic_dev.cloud_review_packet import create_cloud_review_packet


STORY = "story_010_cloud_review_packet"


@pytest.fixture(autouse=True)
def mock_validate_review_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    from agentic_dev.review_state.service import ReviewBundleValidation
    monkeypatch.setattr(
        "agentic_dev.cloud_review_packet.validate_review_bundle",
        lambda *args, **kwargs: ReviewBundleValidation(True, [], None, Path(), Path())
    )

def create_story(project_path: Path, story: str = STORY, story_content: str = None) -> Path:
    if story_content is None:
        story_content = f"# {story}\n\nstory_id: {story}\n\n## Acceptance Criteria\n\n- valid criteria\n"

    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True, exist_ok=True)
    (story_path / "story.md").write_text(story_content, encoding="utf-8")
    
    blueprints_path = project_path / "blueprints"
    blueprints_path.mkdir(exist_ok=True)
    bp_file = blueprints_path / "blueprint.yaml"
    if not bp_file.exists():
        bp_file.write_text("stories:\n  - slug: " + story + "\n    story_id: " + story + "\n    title: " + story + "\n", encoding="utf-8")
    else:
        # append
        bp = bp_file.read_text(encoding="utf-8")
        if story not in bp:
            bp_file.write_text(bp + "  - slug: " + story + "\n    story_id: " + story + "\n    title: " + story + "\n", encoding="utf-8")
    
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir(exist_ok=True)
    (review_bundle_path / "manifest.yaml").write_text(
        "schema_version: 2\n"
        "repository:\n  head_sha: abcdef\n"
        "committed_diff:\n  staged_files: []\n"
        "working_tree:\n  classification: clean\n"
        "validation:\n  strict_clean_passed: true\n  host_container_git_match: true\n"
        "host:\n  status: passed\n  matched: true\n"
    )
    (story_path / "status.yaml").write_text("ready_for_review: true\n")
    (story_path / "reports").mkdir(exist_ok=True)
    (story_path / "reports" / "quality_gate_result.yaml").write_text("status: READY_FOR_REVIEW\n")
    (story_path / "reports" / "finalize_story_result.yaml").write_text(
        "status: ready_for_review\nready_for_review: true\n",
        encoding="utf-8",
    )
    
    return story_path


def read_packet_file(story_path: Path, filename: str) -> str:
    return (story_path / "cloud_review_packet" / filename).read_text(encoding="utf-8")


def test_cloud_review_packet_validates_story_folder_exists(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Story folder does not exist") as error:
        create_cloud_review_packet(tmp_path, STORY)

    assert STORY in str(error.value)


def test_cloud_review_packet_requires_story_file(tmp_path: Path) -> None:
    story_path = tmp_path / "stories" / STORY
    story_path.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="Required story file does not exist") as error:
        create_cloud_review_packet(tmp_path, STORY)

    assert str(story_path / "story.md") in str(error.value)


def test_cloud_review_packet_creates_expected_files(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)

    result = create_cloud_review_packet(tmp_path, STORY)

    generated_packet_files = {
        "cloud_review_prompt.md",
        "cloud_review_context.md",
        "cloud_review_checklist.md",
        "cloud_review_result_template.md",
    }
    expected_files = generated_packet_files | {"cloud_review_export.md"}
    packet_path = story_path / "cloud_review_packet"

    assert result.story == STORY
    assert result.story_path == story_path
    assert result.packet_path == packet_path
    assert {path.name for path in result.generated_files} == generated_packet_files

    for filename in expected_files:
        assert (packet_path / filename).exists()


def test_cloud_review_export_combines_review_packet_files(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)

    create_cloud_review_packet(tmp_path, STORY)

    export = read_packet_file(story_path, "cloud_review_export.md")
    prompt = read_packet_file(story_path, "cloud_review_prompt.md")
    context = read_packet_file(story_path, "cloud_review_context.md")
    checklist = read_packet_file(story_path, "cloud_review_checklist.md")
    result_template = read_packet_file(story_path, "cloud_review_result_template.md")

    assert "paste or upload to the main cloud model" in export
    assert "Do not call cloud models automatically" in export
    assert prompt.rstrip() in export
    assert context.rstrip() in export
    assert checklist.rstrip() in export
    assert result_template.rstrip() in export


def test_cloud_review_prompt_includes_required_review_instructions(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)

    create_cloud_review_packet(tmp_path, STORY)

    prompt = read_packet_file(story_path, "cloud_review_prompt.md")
    assert "Architecture" in prompt
    assert "Correctness" in prompt
    assert "Test coverage" in prompt
    assert "Maintainability" in prompt
    assert "Security" in prompt
    assert "Scope control" in prompt
    assert "Merge readiness" in prompt
    assert "Do not invent missing facts" in prompt
    assert "APPROVE" in prompt
    assert "APPROVE_WITH_NOTES" in prompt
    assert "REQUEST_CHANGES" in prompt


def test_cloud_review_context_includes_story_and_present_evidence(tmp_path: Path) -> None:
    story_content = f"# {STORY}\n\nstory_id: {STORY}\n\nCloud review packet acceptance criteria.\n"
    story_path = create_story(tmp_path, story_content=story_content)
    reports_path = story_path / "reports"
    reports_path.mkdir(exist_ok=True)
    (reports_path / "quality_gate_result.yaml").write_text(
        "status: READY_FOR_REVIEW\nready_for_review: true\n",
        encoding="utf-8",
    )
    (reports_path / "finalize_story_result.yaml").write_text(
        "status: ready_for_review\nready_for_review: true\n",
        encoding="utf-8",
    )
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir(exist_ok=True)
    (review_bundle_path / "handoff.md").write_text(
        "# Handoff\n\nTests and ruff passed.\n",
        encoding="utf-8",
    )
    (review_bundle_path / "git_status.txt").write_text(
        "M src/agentic_dev/cloud_review_packet.py\n",
        encoding="utf-8",
    )
    (review_bundle_path / "git_diff.patch").write_text(
        "diff --git a/src/agentic_dev/cloud_review_packet.py b/src/agentic_dev/cloud_review_packet.py\n",
        encoding="utf-8",
    )
    (review_bundle_path / "git_diff_staged.patch").write_text(
        "diff --git a/README.md b/README.md\n",
        encoding="utf-8",
    )
    (review_bundle_path / "committed_diff_metadata.txt").write_text(
        "# Committed PR Diff Metadata\n\nBase SHA: `abc123`\nHead SHA: `def456`\n",
        encoding="utf-8",
    )
    (review_bundle_path / "committed_diff_stat.txt").write_text(
        "Command: git diff --stat abc123..HEAD\n",
        encoding="utf-8",
    )
    (review_bundle_path / "committed_changed_files.txt").write_text(
        "Command: git diff --name-only abc123..HEAD\nsrc/agentic_dev/cloud_review_packet.py\n",
        encoding="utf-8",
    )
    (review_bundle_path / "committed_diff.patch").write_text(
        "Command: git diff abc123..HEAD\n",
        encoding="utf-8",
    )
    (review_bundle_path / "untracked_file_contents.md").write_text(
        "## `src/agentic_dev/local_execution.py`\n\n```text\ncontent\n```\n",
        encoding="utf-8",
    )

    create_cloud_review_packet(tmp_path, STORY)

    context = read_packet_file(story_path, "cloud_review_context.md")
    assert "Cloud review packet acceptance criteria." in context
    assert "## Quality gate result" in context
    assert "status: READY_FOR_REVIEW" in context
    assert "## Finalize story result" in context
    assert "status: ready_for_review" in context
    assert "## Review bundle handoff" in context
    assert "Tests and ruff passed." in context
    assert "## Git status summary" in context
    assert "M src/agentic_dev/cloud_review_packet.py" in context
    assert "## Git diff patch" in context
    assert "diff --git a/src/agentic_dev/cloud_review_packet.py" in context
    assert "## Git staged diff" in context
    assert "diff --git a/README.md" in context
    assert "## Committed PR diff metadata" in context
    assert "Base SHA: `abc123`" in context
    assert "## Committed PR diff stat" in context
    assert "## Committed PR changed files" in context
    assert "## Committed PR diff patch" in context
    assert "## Untracked file contents" in context
    assert "src/agentic_dev/local_execution.py" in context


def test_cloud_review_context_includes_story_implementation_scope_and_no_not_in_scope_heading(
    tmp_path: Path,
) -> None:
    story_content = (
        "# STORY-062\n\nstory_id: story_010_cloud_review_packet\n\n"
        "## Implementation Review Scope\n\n"
        "- agentic demo-subtasks\n"
        "- deterministic fake-model mode\n"
        "- real local-model mode using the existing runtime adapter\n"
    )
    story_path = create_story(tmp_path, story_content=story_content)

    create_cloud_review_packet(tmp_path, STORY)

    context = read_packet_file(story_path, "cloud_review_context.md")
    assert "## Implementation Review Scope" in context
    assert "agentic demo-subtasks" in context
    assert "deterministic fake-model mode" in context
    assert "## Not In Scope" not in context


def test_cloud_review_context_mentions_missing_optional_evidence_clearly(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)

    result = create_cloud_review_packet(tmp_path, STORY)

    context = read_packet_file(story_path, "cloud_review_context.md")
    assert "## Missing optional evidence" in context
    assert "`agent_plan.yaml` was not found." in context
    assert "`review_bundle/handoff.md` was not found." in context
    assert "agent_plan.yaml" in result.missing_optional_files
    assert "review_bundle/handoff.md" in result.missing_optional_files


def test_existing_cloud_review_packet_files_are_not_overwritten_by_default(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)
    packet_path = story_path / "cloud_review_packet"
    packet_path.mkdir(exist_ok=True)
    prompt_path = packet_path / "cloud_review_prompt.md"
    prompt_path.write_text("keep this prompt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Use --force to overwrite"):
        create_cloud_review_packet(tmp_path, STORY)

    assert prompt_path.read_text(encoding="utf-8") == "keep this prompt\n"


def test_force_regenerates_existing_cloud_review_packet_files(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    packet_path = story_path / "cloud_review_packet"
    packet_path.mkdir(exist_ok=True)
    prompt_path = packet_path / "cloud_review_prompt.md"
    prompt_path.write_text("old prompt\n", encoding="utf-8")

    create_cloud_review_packet(tmp_path, STORY, force=True)

    prompt = prompt_path.read_text(encoding="utf-8")
    assert "old prompt" not in prompt
    assert "APPROVE_WITH_NOTES" in prompt
    assert (packet_path / "cloud_review_context.md").exists()
    assert (packet_path / "cloud_review_checklist.md").exists()
    assert (packet_path / "cloud_review_result_template.md").exists()


def test_cli_cloud_review_packet_requires_story_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "cloud-review-packet"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_cli_cloud_review_packet_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "cloud-review-packet", "--story", STORY])

    main()

    assert (story_path / "cloud_review_packet" / "cloud_review_prompt.md").exists()


def test_cloud_review_packet_validation_failure_raises_value_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    review_bundle_path = story_path / "review_bundle"
    review_bundle_path.mkdir(exist_ok=True)
    (review_bundle_path / "manifest.yaml").write_text("schema_version: 1\n", encoding="utf-8")

    # Mock validate_review_bundle to return invalid
    from agentic_dev.review_state.service import ReviewBundleValidation
    
    def mock_validate(project_path, story, **kwargs):
        return ReviewBundleValidation(
            valid=False,
            reasons=["HEAD changed after review bundle generation", "corrupt manifest checksum"],
            manifest=None,
            manifest_path=review_bundle_path / "manifest.yaml",
            checksum_path=review_bundle_path / "validation" / "checksums.yaml"
        )
        
    monkeypatch.setattr("agentic_dev.cloud_review_packet.validate_review_bundle", mock_validate)

    with pytest.raises(ValueError, match="Review bundle validation failed: HEAD changed after review bundle generation; corrupt manifest checksum"):
        create_cloud_review_packet(tmp_path, STORY)


def test_cloud_review_packet_accepts_normalization_noise_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    
    # Modify manifest to have normalization_noise_only classification
    manifest_path = story_path / "review_bundle" / "manifest.yaml"
    manifest_content = manifest_path.read_text(encoding="utf-8")
    manifest_content = manifest_content.replace(
        "classification: clean",
        "classification: normalization_noise_only"
    )
    manifest_path.write_text(manifest_content, encoding="utf-8")
    
    # Ensure validation passes
    result = create_cloud_review_packet(tmp_path, STORY)
    assert (result.packet_path / "cloud_review_prompt.md").exists()


def test_cloud_review_packet_rejects_non_canonical_quality_gate_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story(tmp_path)
    
    # Modify quality gate status to something non-canonical but passing-like
    qg_path = story_path / "reports" / "quality_gate_result.yaml"
    qg_path.write_text("status: PASS\n", encoding="utf-8")
    
    with pytest.raises(ValueError, match="quality gate status is not passing"):
        create_cloud_review_packet(tmp_path, STORY)


def test_cloud_review_packet_rejects_missing_finalize_result(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    (story_path / "reports" / "finalize_story_result.yaml").unlink()

    with pytest.raises(ValueError, match="Missing mandatory evidence: reports/finalize_story_result.yaml"):
        create_cloud_review_packet(tmp_path, STORY)


def test_cloud_review_packet_rejects_non_ready_finalize_result(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    (story_path / "reports" / "finalize_story_result.yaml").write_text(
        "status: request_changes\nready_for_review: false\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="finalize-story status is not ready_for_review"):
        create_cloud_review_packet(tmp_path, STORY)


def test_cloud_review_packet_rejects_unknown_title(tmp_path: Path) -> None:
    create_story(tmp_path, story_content="# UNKNOWN: title\n\n## Acceptance Criteria\n\n- fine\n")
    with pytest.raises(ValueError, match="title starts with UNKNOWN"):
        create_cloud_review_packet(tmp_path, STORY)

def test_cloud_review_packet_rejects_todo_sections(tmp_path: Path) -> None:
    create_story(tmp_path, story_content=f"# {STORY}\n\nstory_id: {STORY}\n\n## Acceptance Criteria\n\n- TODO\n")
    with pytest.raises(ValueError, match="contains only TODO"):
        create_cloud_review_packet(tmp_path, STORY)

def test_cloud_review_packet_rejects_missing_blueprint(tmp_path: Path) -> None:
    create_story(tmp_path)
    (tmp_path / "blueprints" / "blueprint.yaml").unlink()
    with pytest.raises(ValueError, match="no authoritative requirements source can be resolved"):
        create_cloud_review_packet(tmp_path, STORY)

def test_cloud_review_packet_rejects_blueprint_id_mismatch(tmp_path: Path) -> None:
    create_story(tmp_path, story_content="# OTHER_TITLE\n\nstory_id: WRONG_ID\n\n## Acceptance Criteria\n\n- Fine\n")
    with pytest.raises(ValueError, match="does not match blueprint identity"):
        create_cloud_review_packet(tmp_path, STORY)

def test_cloud_review_packet_includes_blueprint_and_cleanliness_stats(tmp_path: Path) -> None:
    story_path = create_story(tmp_path)
    create_cloud_review_packet(tmp_path, STORY)
    context = read_packet_file(story_path, "cloud_review_context.md")
    assert "## Blueprint requirements" in context
    assert "## Cleanliness Summary" in context
    assert "policy_cleanliness: clean" in context
