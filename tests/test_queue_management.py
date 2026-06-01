from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.queue_management import (
    QUEUE_STATUSES,
    create_queue_item,
    format_queue_item,
    format_queue_list,
    list_queue_items,
    promote_queue_item_to_story,
    set_queue_item_status,
    show_queue_item,
)


QUEUE_FOLDER_BY_TYPE = {
    "improvement": "improvement_queue",
    "maintenance": "maintenance_queue",
    "feature": "feature_queue",
}

QUEUE_PREFIX_BY_TYPE = {
    "improvement": "IMP",
    "maintenance": "MAINT",
    "feature": "FEATURE",
}

REQUIRED_FIELDS = {
    "id",
    "queue_type",
    "title",
    "source_story",
    "category",
    "priority",
    "status",
    "details",
    "created_at",
    "next_action",
}


def read_yaml(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded or {}


def write_minimal_blueprint(tmp_path: Path) -> Path:
    blueprint_path = tmp_path / "blueprints" / "blueprint.yaml"
    blueprint_path.parent.mkdir(parents=True)
    blueprint_path.write_text(
        """name: Test Blueprint
stories:
  - id: STORY-001
    slug: story_001_existing
    title: Existing Story
    goal: Keep the first story in the plan.
    why: It gives promotion a starting point.
    acceptance_criteria:
      - Existing criterion.
    not_in_scope:
      - Existing exclusion.
    definition_of_done:
      - Existing done item.
""",
        encoding="utf-8",
    )
    return blueprint_path


def create_sample_item(
    tmp_path: Path,
    queue_type: str = "improvement",
    title: str = "Improve the local report",
) -> str:
    result = create_queue_item(
        project_path=tmp_path,
        queue_type=queue_type,
        title=title,
        source_story="story_019_queue_management",
        category="testing",
        priority="high",
        details="Add coverage for queue commands.",
    )
    return result.item_id


def create_approved_sample_item(
    tmp_path: Path,
    queue_type: str = "improvement",
    title: str = "Improve the local report",
) -> str:
    item_id = create_sample_item(tmp_path, queue_type=queue_type, title=title)
    set_queue_item_status(tmp_path, item_id, "approved", "Approved for promotion.")
    return item_id


@pytest.mark.parametrize(
    ("queue_type", "expected_folder", "expected_prefix"),
    [
        ("improvement", "improvement_queue", "IMP"),
        ("maintenance", "maintenance_queue", "MAINT"),
        ("feature", "feature_queue", "FEATURE"),
    ],
)
def test_queue_create_creates_item_in_pending_folder(
    tmp_path: Path,
    queue_type: str,
    expected_folder: str,
    expected_prefix: str,
) -> None:
    result = create_queue_item(
        project_path=tmp_path,
        queue_type=queue_type,
        title=f"New {queue_type} item",
        source_story="story_019_queue_management",
        category="coverage",
        priority="medium",
        details="Capture future work without expanding this story.",
    )

    assert result.item_id.startswith(f"{expected_prefix}-")
    assert result.item_path == (
        tmp_path / ".agentic" / expected_folder / "pending" / f"{result.item_id}.yaml"
    )
    assert result.item_path.exists()

    item = read_yaml(result.item_path)
    assert REQUIRED_FIELDS.issubset(item)
    assert item["id"] == result.item_id
    assert item["queue_type"] == queue_type
    assert item["title"] == f"New {queue_type} item"
    assert item["source_story"] == "story_019_queue_management"
    assert item["category"] == "coverage"
    assert item["priority"] == "medium"
    assert item["status"] == "pending"
    assert item["details"] == "Capture future work without expanding this story."
    assert item["created_at"]
    assert item["next_action"]


def test_queue_create_rejects_invalid_queue_type(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid queue type: research") as error:
        create_queue_item(
            project_path=tmp_path,
            queue_type="research",
            title="Research queue should not exist",
        )

    assert "improvement, maintenance, feature" in str(error.value)


def test_queue_list_returns_items_across_statuses(tmp_path: Path) -> None:
    pending_id = create_sample_item(tmp_path, title="Pending idea")
    approved_id = create_sample_item(tmp_path, title="Approved idea")
    rejected_id = create_sample_item(tmp_path, title="Rejected idea")
    parked_id = create_sample_item(tmp_path, title="Parked idea")
    closed_id = create_sample_item(tmp_path, title="Closed idea")

    set_queue_item_status(tmp_path, approved_id, "approved", "Approved for later planning.")
    set_queue_item_status(tmp_path, rejected_id, "rejected", "Not worth pursuing.")
    set_queue_item_status(tmp_path, parked_id, "parked", "Wait for more context.")
    set_queue_item_status(tmp_path, closed_id, "closed", "Already handled elsewhere.")

    result = list_queue_items(tmp_path, queue_type="improvement", status="all")

    assert [item.item_id for item in result.items_by_type_and_status["improvement"]["pending"]] == [
        pending_id
    ]
    assert [item.item_id for item in result.items_by_type_and_status["improvement"]["approved"]] == [
        approved_id
    ]
    assert [item.item_id for item in result.items_by_type_and_status["improvement"]["rejected"]] == [
        rejected_id
    ]
    assert [item.item_id for item in result.items_by_type_and_status["improvement"]["parked"]] == [
        parked_id
    ]
    assert [item.item_id for item in result.items_by_type_and_status["improvement"]["closed"]] == [
        closed_id
    ]

    rendered = format_queue_list(result)
    assert "Queue items:" in rendered
    for status in QUEUE_STATUSES:
        assert f"  {status}:" in rendered
    assert pending_id in rendered
    assert approved_id in rendered
    assert rejected_id in rendered
    assert parked_id in rendered
    assert closed_id in rendered


def test_queue_list_handles_empty_queues_gracefully(tmp_path: Path) -> None:
    result = list_queue_items(tmp_path)

    for queue_type in QUEUE_FOLDER_BY_TYPE:
        for status in QUEUE_STATUSES:
            assert result.items_by_type_and_status[queue_type][status] == []

    rendered = format_queue_list(result)
    assert "No queue items found for the selected filters." in rendered
    assert "    - none" in rendered


def test_queue_show_returns_one_item(tmp_path: Path) -> None:
    item_id = create_sample_item(tmp_path, queue_type="feature", title="Add queue dashboard")

    result = show_queue_item(tmp_path, item_id)

    assert result.item_id == item_id
    assert result.queue_type == "feature"
    assert result.status == "pending"
    assert result.data["title"] == "Add queue dashboard"

    rendered = format_queue_item(result)
    assert f"Queue item: {item_id}" in rendered
    assert "Type: feature" in rendered
    assert "Status: pending" in rendered
    assert "Title: Add queue dashboard" in rendered


def test_queue_show_raises_clear_error_for_missing_item(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Queue item was not found") as error:
        show_queue_item(tmp_path, "IMP-404")

    assert "IMP-404" in str(error.value)


def test_queue_set_status_moves_item_to_approved_and_records_decision_note(
    tmp_path: Path,
) -> None:
    item_id = create_sample_item(tmp_path)
    pending_path = tmp_path / ".agentic" / "improvement_queue" / "pending" / f"{item_id}.yaml"

    result = set_queue_item_status(
        project_path=tmp_path,
        item_id=item_id,
        status="approved",
        decision_note="Approved for a future story.",
    )

    approved_path = tmp_path / ".agentic" / "improvement_queue" / "approved" / f"{item_id}.yaml"
    assert result.old_status == "pending"
    assert result.new_status == "approved"
    assert result.source_path == pending_path
    assert result.destination_path == approved_path
    assert not pending_path.exists()
    assert approved_path.exists()

    item = read_yaml(approved_path)
    assert item["status"] == "approved"
    assert item["decision_note"] == "Approved for a future story."
    assert item["decision_history"][-1]["from"] == "pending"
    assert item["decision_history"][-1]["to"] == "approved"
    assert item["decision_history"][-1]["decision_note"] == "Approved for a future story."
    assert item["status_changed_at"]
    assert item["next_action"]


def test_queue_set_status_moves_item_to_rejected(tmp_path: Path) -> None:
    item_id = create_sample_item(tmp_path, queue_type="maintenance")

    result = set_queue_item_status(
        project_path=tmp_path,
        item_id=item_id,
        status="rejected",
        decision_note="Rejected because the task is out of scope.",
        queue_type="maintenance",
    )

    rejected_path = tmp_path / ".agentic" / "maintenance_queue" / "rejected" / f"{item_id}.yaml"
    pending_path = tmp_path / ".agentic" / "maintenance_queue" / "pending" / f"{item_id}.yaml"
    assert result.new_status == "rejected"
    assert not pending_path.exists()
    assert rejected_path.exists()
    assert read_yaml(rejected_path)["decision_note"] == "Rejected because the task is out of scope."


def test_queue_set_status_rejects_invalid_status(tmp_path: Path) -> None:
    item_id = create_sample_item(tmp_path)

    with pytest.raises(ValueError, match="Invalid queue status: waiting") as error:
        set_queue_item_status(tmp_path, item_id, "waiting")

    assert "pending, approved, rejected, parked, closed" in str(error.value)


@pytest.mark.parametrize(
    ("queue_type", "title", "expected_slug"),
    [
        ("improvement", "Simplify review bundle output", "story_002_simplify_review_bundle_output"),
        ("maintenance", "Refresh stale dependency pins", "story_002_refresh_stale_dependency_pins"),
        ("feature", "Add queue dashboard", "story_002_add_queue_dashboard"),
    ],
)
def test_approved_queue_item_can_be_promoted_to_story(
    tmp_path: Path,
    queue_type: str,
    title: str,
    expected_slug: str,
) -> None:
    blueprint_path = write_minimal_blueprint(tmp_path)
    item_id = create_approved_sample_item(tmp_path, queue_type=queue_type, title=title)

    result = promote_queue_item_to_story(tmp_path, item_id)

    assert result.item_id == item_id
    assert result.queue_type == queue_type
    assert result.old_status == "approved"
    assert result.new_status == "approved"
    assert result.story_id == "STORY-002"
    assert result.story_slug == expected_slug
    assert result.blueprint_path == blueprint_path.resolve()
    assert result.story_path == tmp_path.resolve() / "stories" / expected_slug
    assert result.story_path.exists()

    blueprint = read_yaml(blueprint_path)
    promoted_story = blueprint["stories"][-1]
    assert promoted_story["id"] == "STORY-002"
    assert promoted_story["slug"] == expected_slug
    assert promoted_story["title"] == title
    assert promoted_story["acceptance_criteria"]
    assert promoted_story["not_in_scope"]
    assert promoted_story["definition_of_done"]
    assert promoted_story["test_plan"]["unit_tests"]["required"] is True
    assert promoted_story["monitoring_plan"]["logs_required"] is True

    story_markdown = (result.story_path / "story.md").read_text(encoding="utf-8")
    assert f"# STORY-002: {title}" in story_markdown
    assert "## Acceptance Criteria" in story_markdown
    assert "## Not In Scope" in story_markdown
    assert "## Definition of Done" in story_markdown
    assert (result.story_path / "test_plan.yaml").exists()
    assert (result.story_path / "monitoring_plan.yaml").exists()

    assert result.story_report_path.exists()
    assert result.project_report_path.exists()
    report = result.story_report_path.read_text(encoding="utf-8")
    assert "Queue Promotion Report" in report
    assert "The command did not call cloud models." in report

    promoted_item = read_yaml(result.destination_path)
    assert promoted_item["promoted_story_id"] == "STORY-002"
    assert promoted_item["promoted_story_slug"] == expected_slug


def test_pending_queue_item_cannot_be_promoted_by_default(tmp_path: Path) -> None:
    write_minimal_blueprint(tmp_path)
    item_id = create_sample_item(tmp_path, title="Pending idea")

    with pytest.raises(ValueError, match="cannot be promoted without --allow-pending") as error:
        promote_queue_item_to_story(tmp_path, item_id)

    assert item_id in str(error.value)
    assert not (tmp_path / "stories").exists()


def test_pending_queue_item_can_be_promoted_with_allow_pending(tmp_path: Path) -> None:
    write_minimal_blueprint(tmp_path)
    item_id = create_sample_item(tmp_path, title="Manual override promotion")

    result = promote_queue_item_to_story(tmp_path, item_id, allow_pending=True)

    assert result.allowed_pending is True
    assert result.old_status == "pending"
    assert result.new_status == "pending"
    assert result.story_id == "STORY-002"
    assert result.story_slug == "story_002_manual_override_promotion"
    assert result.destination_path == (
        tmp_path.resolve() / ".agentic" / "improvement_queue" / "pending" / f"{item_id}.yaml"
    )
    assert read_yaml(result.destination_path)["promoted_story_id"] == "STORY-002"


def test_promote_queue_item_raises_clear_error_for_missing_item(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Queue item was not found") as error:
        promote_queue_item_to_story(tmp_path, "IMP-404")

    assert "IMP-404" in str(error.value)


def test_promote_queue_item_uses_next_story_id_and_safe_slug(tmp_path: Path) -> None:
    write_minimal_blueprint(tmp_path)
    existing_story_path = tmp_path / "stories" / "story_009_existing_workspace"
    existing_story_path.mkdir(parents=True)
    (existing_story_path / "story.md").write_text(
        "# STORY-009: Existing Workspace\n",
        encoding="utf-8",
    )
    item_id = create_approved_sample_item(tmp_path, title="Add CSV / JSON export!!")

    result = promote_queue_item_to_story(tmp_path, item_id)

    assert result.story_id == "STORY-010"
    assert result.story_slug == "story_010_add_csv_json_export"
    blueprint = read_yaml(tmp_path / "blueprints" / "blueprint.yaml")
    assert blueprint["stories"][-1]["id"] == "STORY-010"
    assert blueprint["stories"][-1]["slug"] == "story_010_add_csv_json_export"


def test_close_after_promotion_moves_item_to_closed(tmp_path: Path) -> None:
    write_minimal_blueprint(tmp_path)
    item_id = create_approved_sample_item(tmp_path, title="Close promoted item")
    approved_path = (
        tmp_path / ".agentic" / "improvement_queue" / "approved" / f"{item_id}.yaml"
    )

    result = promote_queue_item_to_story(tmp_path, item_id, close_after_promotion=True)

    closed_path = tmp_path / ".agentic" / "improvement_queue" / "closed" / f"{item_id}.yaml"
    assert result.post_promotion_status == "closed"
    assert result.new_status == "closed"
    assert result.destination_path == closed_path.resolve()
    assert not approved_path.exists()
    assert closed_path.exists()
    closed_item = read_yaml(closed_path)
    assert closed_item["status"] == "closed"
    assert closed_item["promoted_story_id"] == "STORY-002"
    assert closed_item["decision_history"][-1]["to"] == "closed"


def test_promote_cli_uses_current_directory_without_git_or_cloud_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_minimal_blueprint(tmp_path)
    item_id = create_approved_sample_item(tmp_path, title="Promote without repository")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "queue",
            "promote-to-story",
            "--item",
            item_id,
        ],
    )

    main()

    output = capsys.readouterr().out
    assert "Queue item promoted:" in output
    assert "STORY-002" in output
    assert "story_002_promote_without_repository" in output
    assert not (tmp_path / ".git").exists()
    assert (tmp_path / "stories" / "story_002_promote_without_repository").exists()


def test_queue_cli_commands_do_not_require_git_or_cloud_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "queue",
            "create",
            "--type",
            "improvement",
            "--title",
            "Local queue item",
            "--source-story",
            "story_019_queue_management",
        ],
    )

    main()

    create_output = capsys.readouterr().out
    item_path = next((tmp_path / ".agentic" / "improvement_queue" / "pending").glob("IMP-*.yaml"))
    item_id = item_path.stem
    assert "Queue item created:" in create_output
    assert item_id in create_output
    assert not (tmp_path / ".git").exists()

    monkeypatch.setattr("sys.argv", ["agentic", "queue", "list"])

    main()

    list_output = capsys.readouterr().out
    assert "Queue items:" in list_output
    assert item_id in list_output

