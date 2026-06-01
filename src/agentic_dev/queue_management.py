from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Any

import yaml

from agentic_dev.story_generator import (
    DEFAULT_BLUEPRINT_RELATIVE_PATH,
    create_story_workspace,
    load_blueprint,
)


QUEUE_TYPES = ("improvement", "maintenance", "feature")
QUEUE_STATUSES = ("pending", "approved", "rejected", "parked", "closed")
ALL_QUEUE_TYPES = (*QUEUE_TYPES, "all")
ALL_QUEUE_STATUSES = (*QUEUE_STATUSES, "all")

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

NEXT_ACTION_BY_STATUS = {
    "pending": "Review and decide whether this should become future work.",
    "approved": "Consider this item when planning future stories.",
    "rejected": "No further action is planned unless the decision changes.",
    "parked": "Revisit when context, priority, or capacity changes.",
    "closed": "No further action is required.",
}


@dataclass(frozen=True)
class QueueCreateResult:
    item_id: str
    item_path: Path
    data: dict[str, Any]


@dataclass(frozen=True)
class QueueItemSummary:
    item_id: str
    queue_type: str
    title: str
    source_story: str
    category: str
    priority: str
    status: str
    path: Path


@dataclass(frozen=True)
class QueueListResult:
    items_by_type_and_status: dict[str, dict[str, list[QueueItemSummary]]]


@dataclass(frozen=True)
class QueueShowResult:
    item_id: str
    queue_type: str
    status: str
    path: Path
    data: dict[str, Any]


@dataclass(frozen=True)
class QueueSetStatusResult:
    item_id: str
    queue_type: str
    old_status: str
    new_status: str
    source_path: Path
    destination_path: Path
    data: dict[str, Any]


@dataclass(frozen=True)
class QueuePromoteToStoryResult:
    item_id: str
    queue_type: str
    old_status: str
    new_status: str
    source_path: Path
    destination_path: Path
    story_id: str
    story_slug: str
    story_path: Path
    blueprint_path: Path
    story_report_path: Path
    project_report_path: Path
    created_paths: list[Path]
    allowed_pending: bool
    post_promotion_status: str | None
    data: dict[str, Any]


@dataclass(frozen=True)
class LocatedQueueItem:
    queue_type: str
    status: str
    path: Path
    data: dict[str, Any]


def create_queue_item(
    project_path: Path,
    queue_type: str,
    title: str,
    source_story: str | None = None,
    category: str | None = None,
    priority: str = "medium",
    details: str | None = None,
) -> QueueCreateResult:
    project_path = project_path.resolve()
    validate_queue_type(queue_type)
    directories = ensure_queue_directories(project_path, queue_type)
    item_id = generate_item_id(queue_type, directories)
    item_path = directories["pending"] / item_filename(item_id)

    item = {
        "id": item_id,
        "queue_type": queue_type,
        "title": title,
        "source_story": source_story or "",
        "category": category or "",
        "priority": priority,
        "status": "pending",
        "details": details or "",
        "created_at": timestamp_now(),
        "next_action": NEXT_ACTION_BY_STATUS["pending"],
    }
    write_yaml_mapping(item_path, item, allow_overwrite=False)

    return QueueCreateResult(item_id=item_id, item_path=item_path, data=item)


def list_queue_items(
    project_path: Path,
    queue_type: str = "all",
    status: str = "all",
) -> QueueListResult:
    project_path = project_path.resolve()
    selected_types = selected_queue_types(queue_type)
    selected_statuses = selected_queue_statuses(status)
    items_by_type_and_status: dict[str, dict[str, list[QueueItemSummary]]] = {}

    for selected_type in selected_types:
        directories = ensure_queue_directories(project_path, selected_type)
        status_items: dict[str, list[QueueItemSummary]] = {}
        for selected_status in selected_statuses:
            item_paths = sorted(
                path
                for path in directories[selected_status].glob("*.yaml")
                if path.is_file() and path.name != ".gitkeep"
            )
            status_items[selected_status] = [
                summarize_queue_item(selected_type, selected_status, path) for path in item_paths
            ]
        items_by_type_and_status[selected_type] = status_items

    return QueueListResult(items_by_type_and_status=items_by_type_and_status)


def show_queue_item(
    project_path: Path,
    item_id: str,
    queue_type: str | None = None,
) -> QueueShowResult:
    located_item = find_queue_item(project_path.resolve(), item_id, queue_type)

    return QueueShowResult(
        item_id=text_value(located_item.data, "id", item_id),
        queue_type=located_item.queue_type,
        status=located_item.status,
        path=located_item.path,
        data=located_item.data,
    )


def set_queue_item_status(
    project_path: Path,
    item_id: str,
    status: str,
    decision_note: str | None = None,
    queue_type: str | None = None,
) -> QueueSetStatusResult:
    project_path = project_path.resolve()
    validate_queue_status(status)
    located_item = find_queue_item(project_path, item_id, queue_type)
    directories = ensure_queue_directories(project_path, located_item.queue_type)

    item_data = dict(located_item.data)
    old_status = located_item.status
    changed_at = timestamp_now()
    item_data["status"] = status
    item_data["next_action"] = NEXT_ACTION_BY_STATUS[status]
    item_data["status_changed_at"] = changed_at

    item_data["decision_note"] = decision_note or ""

    history_entry = {
        "from": old_status,
        "to": status,
        "changed_at": changed_at,
        "decision_note": decision_note or "",
    }
    history = item_data.get("decision_history")
    if not isinstance(history, list):
        history = []
    history.append(history_entry)
    item_data["decision_history"] = history

    destination_path = directories[status] / item_filename(text_value(item_data, "id", item_id))
    write_yaml_mapping(
        destination_path,
        item_data,
        allow_overwrite=destination_path == located_item.path,
    )
    remove_source_if_moved(located_item.path, destination_path)

    return QueueSetStatusResult(
        item_id=text_value(item_data, "id", item_id),
        queue_type=located_item.queue_type,
        old_status=old_status,
        new_status=status,
        source_path=located_item.path,
        destination_path=destination_path,
        data=item_data,
    )


def promote_queue_item_to_story(
    project_path: Path,
    item_id: str,
    queue_type: str | None = None,
    allow_pending: bool = False,
    close_after_promotion: bool = False,
    park_after_promotion: bool = False,
) -> QueuePromoteToStoryResult:
    project_path = project_path.resolve()
    if close_after_promotion and park_after_promotion:
        raise ValueError("Use only one post-promotion move option: closed or parked.")

    located_item = find_queue_item(project_path, item_id, queue_type)
    if located_item.status != "approved":
        if located_item.status == "pending" and allow_pending:
            pass
        elif located_item.status == "pending":
            raise ValueError(
                "Queue item is pending and cannot be promoted without --allow-pending: "
                f"{item_id}",
            )
        else:
            raise ValueError(
                "Queue item must be approved before promotion. "
                f"{item_id} currently has status {located_item.status}.",
            )

    if text_value(located_item.data, "promoted_story_id", ""):
        raise ValueError(
            "Queue item has already been promoted to "
            f"{text_value(located_item.data, 'promoted_story_id', 'a story')}.",
        )

    blueprint_path = project_path / DEFAULT_BLUEPRINT_RELATIVE_PATH
    blueprint = load_blueprint(blueprint_path)
    stories = blueprint.get("stories")
    if not isinstance(stories, list):
        raise ValueError("Blueprint must include a top-level 'stories' list.")

    story_number = next_story_number(project_path, stories)
    title = text_value(located_item.data, "title", "").strip() or item_id
    story_id = format_story_id(story_number)
    story_slug = unique_story_slug(project_path, stories, story_number, title)
    story = build_promoted_story(story_id, story_slug, title, located_item)
    story_path = project_path / "stories" / story_slug
    if story_path.exists():
        raise ValueError(f"Story workspace already exists: {story_path}")

    append_story_to_blueprint(blueprint_path, blueprint, story)
    created_paths = create_story_workspace(project_path, story)

    promoted_at = timestamp_now()
    post_promotion_status = selected_post_promotion_status(
        close_after_promotion,
        park_after_promotion,
    )
    item_data = build_promoted_queue_item_data(
        located_item=located_item,
        item_id=item_id,
        story_id=story_id,
        story_slug=story_slug,
        promoted_at=promoted_at,
        post_promotion_status=post_promotion_status,
    )
    destination_path = write_promoted_queue_item(
        project_path=project_path,
        located_item=located_item,
        item_data=item_data,
        post_promotion_status=post_promotion_status,
    )

    result = QueuePromoteToStoryResult(
        item_id=text_value(item_data, "id", item_id),
        queue_type=located_item.queue_type,
        old_status=located_item.status,
        new_status=text_value(item_data, "status", located_item.status),
        source_path=located_item.path,
        destination_path=destination_path,
        story_id=story_id,
        story_slug=story_slug,
        story_path=story_path,
        blueprint_path=blueprint_path,
        story_report_path=story_path / "reports" / "promotion_report.md",
        project_report_path=project_path / "reports" / "queue_promotion_report.md",
        created_paths=created_paths,
        allowed_pending=located_item.status == "pending" and allow_pending,
        post_promotion_status=post_promotion_status,
        data=item_data,
    )
    write_promotion_reports(result, located_item.data)
    return result


def count_queue_items(project_path: Path) -> dict[str, dict[str, int]]:
    project_path = project_path.resolve()
    counts: dict[str, dict[str, int]] = {}

    for queue_type in QUEUE_TYPES:
        directories = queue_directories(project_path, queue_type)
        status_counts: dict[str, int] = {}
        total = 0
        for status in QUEUE_STATUSES:
            status_path = directories[status]
            count = count_yaml_files(status_path)
            status_counts[status] = count
            total += count
        status_counts["total"] = total
        counts[queue_type] = status_counts

    return counts


def format_queue_list(result: QueueListResult) -> str:
    lines = ["Queue items:"]
    found_any = False

    for queue_type in QUEUE_TYPES:
        status_items = result.items_by_type_and_status.get(queue_type)
        if status_items is None:
            continue

        lines.extend(["", f"{queue_type}:"])
        for status in QUEUE_STATUSES:
            items = status_items.get(status)
            if items is None:
                continue

            lines.append(f"  {status}:")
            if not items:
                lines.append("    - none")
                continue

            found_any = True
            for item in items:
                lines.append(
                    "    - "
                    f"{item.item_id} | priority={item.priority} | category={item.category} "
                    f"| source={item.source_story} | title={item.title}"
                )

    if not found_any:
        lines.append("")
        lines.append("No queue items found for the selected filters.")

    return "\n".join(lines)


def format_queue_item(result: QueueShowResult) -> str:
    item = result.data
    lines = [
        f"Queue item: {result.item_id}",
        f"Path: {result.path}",
        "",
        f"Type: {result.queue_type}",
        f"Status: {result.status}",
        f"Title: {text_value(item, 'title', '')}",
        f"Source story: {text_value(item, 'source_story', '') or 'none'}",
        f"Category: {text_value(item, 'category', '') or 'none'}",
        f"Priority: {text_value(item, 'priority', '') or 'none'}",
        f"Created at: {text_value(item, 'created_at', '') or 'unknown'}",
        f"Next action: {text_value(item, 'next_action', '') or 'none'}",
        "",
        "Details:",
        text_value(item, "details", "") or "none",
    ]

    decision_note = text_value(item, "decision_note", "")
    if decision_note:
        lines.extend(["", "Decision note:", decision_note])

    return "\n".join(lines)


def format_queue_promotion(result: QueuePromoteToStoryResult) -> str:
    lines = [
        f"Queue item promoted: {result.item_id}",
        f"Story: {result.story_id} ({result.story_slug})",
        f"Blueprint: {result.blueprint_path}",
        f"Story path: {result.story_path}",
        f"Promotion report: {result.story_report_path}",
        f"Project report: {result.project_report_path}",
        f"Queue status: {result.old_status} -> {result.new_status}",
    ]
    if result.allowed_pending:
        lines.append("Pending override: used --allow-pending")
    if result.post_promotion_status:
        lines.append(f"Post-promotion move: {result.post_promotion_status}")

    return "\n".join(lines)


def ensure_all_queue_directories(project_path: Path) -> dict[str, dict[str, Path]]:
    return {
        queue_type: ensure_queue_directories(project_path, queue_type)
        for queue_type in QUEUE_TYPES
    }


def ensure_queue_directories(project_path: Path, queue_type: str) -> dict[str, Path]:
    validate_queue_type(queue_type)
    directories = queue_directories(project_path, queue_type)

    directories["root"].mkdir(parents=True, exist_ok=True)
    for status in QUEUE_STATUSES:
        directories[status].mkdir(parents=True, exist_ok=True)

    return directories


def queue_directories(project_path: Path, queue_type: str) -> dict[str, Path]:
    validate_queue_type(queue_type)
    queue_root = project_path / ".agentic" / QUEUE_FOLDER_BY_TYPE[queue_type]
    directories = {"root": queue_root}

    for status in QUEUE_STATUSES:
        directories[status] = queue_root / status

    return directories


def generate_item_id(queue_type: str, directories: dict[str, Path]) -> str:
    prefix = QUEUE_PREFIX_BY_TYPE[queue_type]
    base_id = f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    candidate = base_id
    counter = 1

    while item_exists(directories, candidate):
        candidate = f"{base_id}-{counter:02d}"
        counter += 1

    return candidate


def item_exists(directories: dict[str, Path], item_id: str) -> bool:
    filename = item_filename(item_id)
    return any((directories[status] / filename).exists() for status in QUEUE_STATUSES)


def summarize_queue_item(
    fallback_queue_type: str,
    fallback_status: str,
    item_path: Path,
) -> QueueItemSummary:
    item_data = load_yaml_mapping(item_path)

    return QueueItemSummary(
        item_id=text_value(item_data, "id", item_path.stem),
        queue_type=text_value(item_data, "queue_type", fallback_queue_type),
        title=text_value(item_data, "title", "untitled"),
        source_story=text_value(item_data, "source_story", "none") or "none",
        category=text_value(item_data, "category", "none") or "none",
        priority=text_value(item_data, "priority", "unknown"),
        status=text_value(item_data, "status", fallback_status),
        path=item_path,
    )


def find_queue_item(
    project_path: Path,
    item_id: str,
    queue_type: str | None = None,
) -> LocatedQueueItem:
    selected_types = selected_queue_types(queue_type or "all")

    for selected_type in selected_types:
        directories = ensure_queue_directories(project_path, selected_type)
        for status in QUEUE_STATUSES:
            item_path = directories[status] / item_filename(item_id)
            if item_path.exists():
                data = load_yaml_mapping(item_path)
                return LocatedQueueItem(
                    queue_type=selected_type,
                    status=status,
                    path=item_path,
                    data=data,
                )

    type_hint = f" in {queue_type} queue" if queue_type else ""
    raise FileNotFoundError(f"Queue item was not found{type_hint}: {item_id}")


def next_story_number(project_path: Path, stories: list[Any]) -> int:
    numbers: list[int] = []

    for story in stories:
        if isinstance(story, dict):
            numbers.extend(story_numbers_from_text(text_value(story, "id", "")))
            numbers.extend(story_numbers_from_text(text_value(story, "slug", "")))

    stories_path = project_path / "stories"
    if stories_path.exists():
        for story_path in stories_path.iterdir():
            if not story_path.is_dir():
                continue
            numbers.extend(story_numbers_from_text(story_path.name))
            story_markdown = story_path / "story.md"
            if story_markdown.exists():
                numbers.extend(story_numbers_from_text(read_text_prefix(story_markdown)))

    return max(numbers, default=0) + 1


def format_story_id(story_number: int) -> str:
    if story_number < 1:
        raise ValueError(f"Invalid story number: {story_number}")

    return f"STORY-{story_number:03d}"


def safe_story_slug_text(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug or "queue_item"


def unique_story_slug(
    project_path: Path,
    stories: list[Any],
    story_number: int,
    title: str,
) -> str:
    used_slugs = {
        text_value(story, "slug", "")
        for story in stories
        if isinstance(story, dict)
    }
    base = f"story_{story_number:03d}_{safe_story_slug_text(title)}"
    candidate = base
    counter = 2

    while candidate in used_slugs or (project_path / "stories" / candidate).exists():
        candidate = f"{base}_{counter}"
        counter += 1

    return candidate


def story_numbers_from_text(value: str) -> list[int]:
    numbers: list[int] = []
    for match in re.finditer(r"\bSTORY-(\d+)\b|(?:^|/)story_(\d+)(?:_|$)", value):
        raw_number = match.group(1) or match.group(2)
        if raw_number:
            numbers.append(int(raw_number))

    return numbers


def read_text_prefix(path: Path, character_limit: int = 500) -> str:
    return path.read_text(encoding="utf-8", errors="replace")[:character_limit]


def build_promoted_story(
    story_id: str,
    story_slug: str,
    title: str,
    located_item: LocatedQueueItem,
) -> dict[str, Any]:
    details = text_value(located_item.data, "details", "").strip()
    category = text_value(located_item.data, "category", "").strip()
    source_story = text_value(located_item.data, "source_story", "").strip()
    queue_context = (
        f"{located_item.queue_type} queue item "
        f"{text_value(located_item.data, 'id', '')}"
    )
    source_context = f" Source story: {source_story}." if source_story else ""
    category_context = f" Category: {category}." if category else ""
    goal = details or f"Implement the approved queue item: {title}."

    return {
        "id": story_id,
        "slug": story_slug,
        "title": title,
        "goal": goal,
        "why": (
            f"This story was promoted from {queue_context} so it can be "
            f"planned, implemented, tested, and reviewed through the standard workflow."
            f"{source_context}{category_context}"
        ),
        "acceptance_criteria": [
            f"Implement the approved queue item: {title}.",
            "Add or update tests that cover the promoted behavior.",
            "Update documentation when the user-facing workflow changes.",
            "Keep the work scoped to the promoted queue item.",
        ],
        "not_in_scope": [
            "No unrelated changes.",
            "No automatic cloud model calls.",
            "No automatic story execution.",
            "No automatic merge or deployment.",
        ],
        "definition_of_done": [
            "pytest passes.",
            "ruff passes.",
            "artifact-policy passes.",
            "runtime-config validate passes.",
            "The promoted queue item is implemented and reviewed.",
            "finalize-story marks this story ready for review.",
        ],
        "test_plan": {
            "test_layers_version": 1,
            "unit_tests": {
                "required": True,
                "action": "add_or_update",
                "frequency": "every_commit",
                "evidence_or_reason": "Add or update unit tests for the promoted queue item.",
            },
            "integration_tests": {
                "required": True,
                "action": "confirm_existing",
                "frequency": "every_pull_request",
                "evidence_or_reason": (
                    "Confirm existing integration coverage still covers the affected workflow."
                ),
            },
            "mock_e2e_tests": {
                "required": True,
                "action": "confirm_existing",
                "frequency": "before_merge",
                "evidence_or_reason": (
                    "Confirm mock E2E coverage remains valid for the local workflow."
                ),
            },
            "live_read_only_checks": {
                "required": False,
                "action": "not_applicable_with_reason",
                "frequency": "scheduled_or_before_release",
                "evidence_or_reason": (
                    "The promoted story should not require live service access by default."
                ),
            },
            "remote_dev_smoke_tests": {
                "required": False,
                "action": "not_applicable_with_reason",
                "frequency": "after_remote_dev_deploy",
                "evidence_or_reason": (
                    "No remote dev environment is assumed for promoted queue items."
                ),
            },
        },
        "monitoring_plan": {
            "logs_required": True,
            "watch_for": [
                "implementation_failure",
                "regression",
                "missing_test_coverage",
                "unexpected_scope_expansion",
            ],
        },
    }


def append_story_to_blueprint(
    blueprint_path: Path,
    blueprint: dict[str, Any],
    story: dict[str, Any],
) -> None:
    stories = blueprint.get("stories")
    if not isinstance(stories, list):
        raise ValueError("Blueprint must include a top-level 'stories' list.")

    if any(
        isinstance(existing_story, dict)
        and text_value(existing_story, "id", "") == text_value(story, "id", "")
        for existing_story in stories
    ):
        raise ValueError(f"Blueprint already contains story id: {text_value(story, 'id', '')}")

    if any(
        isinstance(existing_story, dict)
        and text_value(existing_story, "slug", "") == text_value(story, "slug", "")
        for existing_story in stories
    ):
        raise ValueError(f"Blueprint already contains story slug: {text_value(story, 'slug', '')}")

    if (
        stories_is_last_top_level_section(blueprint_path)
        and stories_uses_block_sequence(blueprint_path)
    ):
        story_yaml = yaml.safe_dump([story], sort_keys=False).rstrip()
        indented_story_yaml = "\n".join(f"  {line}" for line in story_yaml.splitlines())
        current_text = blueprint_path.read_text(encoding="utf-8")
        updated_text = f"{current_text.rstrip()}\n\n{indented_story_yaml}\n"
        blueprint_path.write_text(updated_text, encoding="utf-8")
        return

    updated_blueprint = dict(blueprint)
    updated_blueprint["stories"] = [*stories, story]
    write_yaml_mapping(blueprint_path, updated_blueprint)


def stories_is_last_top_level_section(blueprint_path: Path) -> bool:
    last_top_level_key = ""
    for line in blueprint_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line.startswith((" ", "\t", "-")):
            continue
        match = re.match(r"([A-Za-z0-9_-]+):", line)
        if match:
            last_top_level_key = match.group(1)

    return last_top_level_key == "stories"


def stories_uses_block_sequence(blueprint_path: Path) -> bool:
    for line in blueprint_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("stories:"):
            return line.strip() == "stories:"

    return False


def selected_post_promotion_status(
    close_after_promotion: bool,
    park_after_promotion: bool,
) -> str | None:
    if close_after_promotion:
        return "closed"

    if park_after_promotion:
        return "parked"

    return None


def build_promoted_queue_item_data(
    located_item: LocatedQueueItem,
    item_id: str,
    story_id: str,
    story_slug: str,
    promoted_at: str,
    post_promotion_status: str | None,
) -> dict[str, Any]:
    item_data = dict(located_item.data)
    item_data["promoted_story_id"] = story_id
    item_data["promoted_story_slug"] = story_slug
    item_data["promoted_at"] = promoted_at

    if post_promotion_status is None:
        return item_data

    item_data["status"] = post_promotion_status
    item_data["next_action"] = NEXT_ACTION_BY_STATUS[post_promotion_status]
    item_data["status_changed_at"] = promoted_at

    history = item_data.get("decision_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "from": located_item.status,
            "to": post_promotion_status,
            "changed_at": promoted_at,
            "decision_note": f"Promoted to {story_id} ({story_slug}).",
        },
    )
    item_data["decision_history"] = history

    return item_data


def write_promoted_queue_item(
    project_path: Path,
    located_item: LocatedQueueItem,
    item_data: dict[str, Any],
    post_promotion_status: str | None,
) -> Path:
    destination_status = post_promotion_status or located_item.status
    directories = ensure_queue_directories(project_path, located_item.queue_type)
    destination_path = directories[destination_status] / item_filename(
        text_value(item_data, "id", located_item.path.stem),
    )
    write_yaml_mapping(
        destination_path,
        item_data,
        allow_overwrite=destination_path == located_item.path,
    )
    remove_source_if_moved(located_item.path, destination_path)
    return destination_path


def write_promotion_reports(
    result: QueuePromoteToStoryResult,
    original_item_data: dict[str, Any],
) -> None:
    report = format_promotion_report(result, original_item_data)
    result.story_report_path.parent.mkdir(parents=True, exist_ok=True)
    result.story_report_path.write_text(report, encoding="utf-8")
    result.project_report_path.parent.mkdir(parents=True, exist_ok=True)
    result.project_report_path.write_text(report, encoding="utf-8")


def format_promotion_report(
    result: QueuePromoteToStoryResult,
    original_item_data: dict[str, Any],
) -> str:
    pending_override = "yes" if result.allowed_pending else "no"
    post_status = result.post_promotion_status or "unchanged"

    return f"""# Queue Promotion Report

## Summary

- Queue item: {result.item_id}
- Queue type: {result.queue_type}
- Queue status: {result.old_status} -> {result.new_status}
- Promoted story: {result.story_id}
- Story slug: {result.story_slug}
- Pending override used: {pending_override}
- Post-promotion status: {post_status}

## Paths

- Blueprint: {result.blueprint_path}
- Story workspace: {result.story_path}
- Queue item source: {result.source_path}
- Queue item current path: {result.destination_path}

## Queue Item

- Title: {text_value(original_item_data, "title", "")}
- Source story: {text_value(original_item_data, "source_story", "") or "none"}
- Category: {text_value(original_item_data, "category", "") or "none"}
- Priority: {text_value(original_item_data, "priority", "") or "none"}

## Notes

- The command created the story workspace but did not execute agents.
- The command did not call cloud models.
- The command did not commit, push, merge, or deploy.
"""


def selected_queue_types(queue_type: str) -> tuple[str, ...]:
    if queue_type == "all":
        return QUEUE_TYPES

    validate_queue_type(queue_type)
    return (queue_type,)


def selected_queue_statuses(status: str) -> tuple[str, ...]:
    if status == "all":
        return QUEUE_STATUSES

    validate_queue_status(status)
    return (status,)


def validate_queue_type(queue_type: str) -> None:
    if queue_type not in QUEUE_TYPES:
        valid_types = ", ".join(QUEUE_TYPES)
        raise ValueError(f"Invalid queue type: {queue_type}. Expected one of: {valid_types}.")


def validate_queue_status(status: str) -> None:
    if status not in QUEUE_STATUSES:
        valid_statuses = ", ".join(QUEUE_STATUSES)
        raise ValueError(f"Invalid queue status: {status}. Expected one of: {valid_statuses}.")


def count_yaml_files(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0

    return sum(
        1
        for item_path in path.glob("*.yaml")
        if item_path.is_file() and item_path.name != ".gitkeep"
    )


def item_filename(item_id: str) -> str:
    return f"{item_id}.yaml"


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file_handle:
        loaded = yaml.safe_load(file_handle)

    if loaded is None:
        return {}

    if not isinstance(loaded, dict):
        raise ValueError(f"YAML file must contain a mapping: {path}")

    return loaded


def write_yaml_mapping(path: Path, data: dict[str, Any], allow_overwrite: bool = True) -> None:
    if path.exists() and not allow_overwrite:
        raise ValueError(f"File already exists: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def remove_source_if_moved(source_path: Path, destination_path: Path) -> None:
    if source_path != destination_path and source_path.exists():
        source_path.unlink()


def text_value(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key)
    if value is None:
        return default

    return str(value)


def timestamp_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
