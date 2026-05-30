from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


SUPPORT_QUEUE_FOLDERS = (
    "pending",
    "answered",
    "escalated_to_human",
    "closed",
)

PENDING_CLOUD_REVIEW = "pending_cloud_review"
ANSWERED_STATUS = "answered"
CLOSED_STATUS = "closed"


@dataclass(frozen=True)
class SupportTicketCreateResult:
    ticket_id: str
    ticket_path: Path
    story_status_path: Path | None


@dataclass(frozen=True)
class SupportTicketSummary:
    ticket_id: str
    story: str
    agent: str
    status: str
    severity: str
    queue: str
    path: Path


@dataclass(frozen=True)
class SupportTicketListResult:
    tickets_by_queue: dict[str, list[SupportTicketSummary]]


@dataclass(frozen=True)
class SupportTicketCloudPacketResult:
    ticket_id: str
    ticket_path: Path
    packet_path: Path


@dataclass(frozen=True)
class SupportTicketAnswerResult:
    ticket_id: str
    source_path: Path
    destination_path: Path
    answered_by: str


@dataclass(frozen=True)
class SupportTicketCloseResult:
    ticket_id: str
    source_path: Path
    destination_path: Path


@dataclass(frozen=True)
class LocatedTicket:
    queue: str
    path: Path
    data: dict[str, Any]


def create_support_ticket(
    project_path: Path,
    story: str,
    agent: str,
    blocker_type: str,
    question: str,
    details: str | None = None,
    severity: str = "medium",
) -> SupportTicketCreateResult:
    project_path = project_path.resolve()
    directories = ensure_support_queue_directories(project_path)
    ticket_id = generate_ticket_id(directories)
    ticket_path = directories["pending"] / ticket_filename(ticket_id)

    ticket = {
        "ticket_id": ticket_id,
        "story": story,
        "agent": agent,
        "blocker_type": blocker_type,
        "severity": severity,
        "question": question,
        "details": details or "",
        "status": PENDING_CLOUD_REVIEW,
        "preferred_responder": "cloud_model",
        "escalation_rule": "ask_human_if_cloud_model_is_uncertain",
        "created_at": timestamp_now(),
    }
    write_yaml_mapping(ticket_path, ticket, allow_overwrite=False)

    story_status_path = block_story_if_present(project_path, story, ticket_id)

    return SupportTicketCreateResult(
        ticket_id=ticket_id,
        ticket_path=ticket_path,
        story_status_path=story_status_path,
    )


def list_support_tickets(project_path: Path) -> SupportTicketListResult:
    project_path = project_path.resolve()
    directories = ensure_support_queue_directories(project_path)
    tickets_by_queue: dict[str, list[SupportTicketSummary]] = {}

    for queue_name in SUPPORT_QUEUE_FOLDERS:
        queue_path = directories[queue_name]
        ticket_paths = sorted(
            path for path in queue_path.glob("*.yaml") if path.is_file() and path.name != ".gitkeep"
        )
        tickets_by_queue[queue_name] = [summarize_ticket(queue_name, path) for path in ticket_paths]

    return SupportTicketListResult(tickets_by_queue=tickets_by_queue)


def create_support_ticket_cloud_packet(
    project_path: Path,
    ticket_id: str,
) -> SupportTicketCloudPacketResult:
    project_path = project_path.resolve()
    located_ticket = find_ticket(project_path, ticket_id)
    packet_path = located_ticket.path.with_name(f"{located_ticket.path.stem}.cloud-packet.md")

    packet_path.write_text(build_cloud_packet(located_ticket.data), encoding="utf-8")

    return SupportTicketCloudPacketResult(
        ticket_id=ticket_id,
        ticket_path=located_ticket.path,
        packet_path=packet_path,
    )


def answer_support_ticket(
    project_path: Path,
    ticket_id: str,
    answer_file: Path,
    answered_by: str = "cloud_model",
) -> SupportTicketAnswerResult:
    project_path = project_path.resolve()
    answer_path = answer_file.resolve()
    if not answer_path.exists():
        raise FileNotFoundError(f"Answer file does not exist: {answer_path}")
    if not answer_path.is_file():
        raise ValueError(f"Answer file is not a file: {answer_path}")

    located_ticket = find_ticket(project_path, ticket_id)
    ticket_data = dict(located_ticket.data)
    ticket_data["status"] = ANSWERED_STATUS
    ticket_data["answered_by"] = answered_by
    ticket_data["answered_at"] = timestamp_now()
    ticket_data["answer"] = read_text(answer_path).strip()

    if not ticket_data["answer"]:
        raise ValueError(f"Answer file is empty: {answer_path}")

    destination_path = ensure_support_queue_directories(project_path)["answered"] / ticket_filename(ticket_id)
    write_yaml_mapping(destination_path, ticket_data, allow_overwrite=destination_path == located_ticket.path)

    move_related_packet(located_ticket.path, destination_path)
    remove_source_if_moved(located_ticket.path, destination_path)

    return SupportTicketAnswerResult(
        ticket_id=ticket_id,
        source_path=located_ticket.path,
        destination_path=destination_path,
        answered_by=answered_by,
    )


def close_support_ticket(project_path: Path, ticket_id: str) -> SupportTicketCloseResult:
    project_path = project_path.resolve()
    located_ticket = find_ticket(project_path, ticket_id)
    ticket_data = dict(located_ticket.data)
    ticket_data["status"] = CLOSED_STATUS
    ticket_data["closed_at"] = timestamp_now()

    destination_path = ensure_support_queue_directories(project_path)["closed"] / ticket_filename(ticket_id)
    write_yaml_mapping(destination_path, ticket_data, allow_overwrite=destination_path == located_ticket.path)

    move_related_packet(located_ticket.path, destination_path)
    remove_source_if_moved(located_ticket.path, destination_path)

    return SupportTicketCloseResult(
        ticket_id=ticket_id,
        source_path=located_ticket.path,
        destination_path=destination_path,
    )


def format_support_ticket_list(result: SupportTicketListResult) -> str:
    lines = ["Support tickets:"]

    for queue_name in SUPPORT_QUEUE_FOLDERS:
        lines.extend(["", f"{queue_name}:"])
        tickets = result.tickets_by_queue.get(queue_name, [])
        if not tickets:
            lines.append("  - none")
            continue

        for ticket in tickets:
            lines.append(
                "  - "
                f"{ticket.ticket_id} | story={ticket.story} | agent={ticket.agent} "
                f"| severity={ticket.severity} | status={ticket.status}"
            )

    return "\n".join(lines)


def ensure_support_queue_directories(project_path: Path) -> dict[str, Path]:
    support_queue_path = project_path / ".agentic" / "support_queue"
    directories = {"support_queue": support_queue_path}

    support_queue_path.mkdir(parents=True, exist_ok=True)
    for queue_name in SUPPORT_QUEUE_FOLDERS:
        queue_path = support_queue_path / queue_name
        queue_path.mkdir(parents=True, exist_ok=True)
        directories[queue_name] = queue_path

    return directories


def generate_ticket_id(directories: dict[str, Path]) -> str:
    base_id = f"SUPPORT-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    candidate = base_id
    counter = 1

    while ticket_exists(directories, candidate):
        candidate = f"{base_id}-{counter:02d}"
        counter += 1

    return candidate


def ticket_exists(directories: dict[str, Path], ticket_id: str) -> bool:
    filename = ticket_filename(ticket_id)
    return any((directories[queue_name] / filename).exists() for queue_name in SUPPORT_QUEUE_FOLDERS)


def block_story_if_present(project_path: Path, story: str, ticket_id: str) -> Path | None:
    story_path = project_path / "stories" / story
    if not story_path.exists() or not story_path.is_dir():
        return None

    status_path = story_path / "status.yaml"
    status = load_yaml_mapping(status_path)
    status["story_id"] = status.get("story_id") or story
    status["status"] = "blocked"
    status["ready_for_review"] = False
    status["blocked_by"] = ticket_id

    write_yaml_mapping(status_path, status)
    return status_path


def summarize_ticket(queue_name: str, ticket_path: Path) -> SupportTicketSummary:
    ticket_data = load_yaml_mapping(ticket_path)

    return SupportTicketSummary(
        ticket_id=text_value(ticket_data, "ticket_id", ticket_path.stem),
        story=text_value(ticket_data, "story", "unknown"),
        agent=text_value(ticket_data, "agent", "unknown"),
        status=text_value(ticket_data, "status", queue_name),
        severity=text_value(ticket_data, "severity", "unknown"),
        queue=queue_name,
        path=ticket_path,
    )


def find_ticket(project_path: Path, ticket_id: str) -> LocatedTicket:
    directories = ensure_support_queue_directories(project_path)

    for queue_name in SUPPORT_QUEUE_FOLDERS:
        ticket_path = directories[queue_name] / ticket_filename(ticket_id)
        if ticket_path.exists():
            return LocatedTicket(
                queue=queue_name,
                path=ticket_path,
                data=load_yaml_mapping(ticket_path),
            )

    raise FileNotFoundError(f"Support ticket was not found: {ticket_id}")


def build_cloud_packet(ticket_data: dict[str, Any]) -> str:
    yaml_block = yaml.safe_dump(ticket_data, sort_keys=False).rstrip()

    return f"""# Support Ticket Cloud Packet

## Instructions

- Answer the agent's question if you are confident.
- Use only the ticket context in this packet.
- Do not invent missing facts.
- Return `NEEDS_HUMAN` if the answer requires human or project-owner judgment.
- Return `REQUEST_MORE_CONTEXT` if more project context is required.

## Required response format

Return exactly one of these top-level labels:

- `ANSWER`
- `NEEDS_HUMAN`
- `REQUEST_MORE_CONTEXT`

Then provide a concise explanation or answer beneath that label.

## Ticket context

```yaml
{yaml_block}
```
"""


def move_related_packet(source_ticket_path: Path, destination_ticket_path: Path) -> None:
    source_packet_path = source_ticket_path.with_name(f"{source_ticket_path.stem}.cloud-packet.md")
    if not source_packet_path.exists():
        return

    destination_packet_path = destination_ticket_path.with_name(
        f"{destination_ticket_path.stem}.cloud-packet.md"
    )
    destination_packet_path.write_text(read_text(source_packet_path), encoding="utf-8")

    if destination_packet_path != source_packet_path:
        source_packet_path.unlink()


def remove_source_if_moved(source_path: Path, destination_path: Path) -> None:
    if source_path != destination_path and source_path.exists():
        source_path.unlink()


def ticket_filename(ticket_id: str) -> str:
    return f"{ticket_id}.yaml"


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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def text_value(mapping: dict[str, Any], key: str, default: str) -> str:
    value = mapping.get(key)
    if value is None:
        return default

    return str(value)


def timestamp_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
