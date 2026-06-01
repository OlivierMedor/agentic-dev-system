from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


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
    write_yaml_mapping(destination_path, item_data, allow_overwrite=destination_path == located_item.path)
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
