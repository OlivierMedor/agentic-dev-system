from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.support_queue import (
    ANSWERED_STATUS,
    CLOSED_STATUS,
    PENDING_CLOUD_REVIEW,
    answer_support_ticket,
    close_support_ticket,
    create_support_ticket,
    create_support_ticket_cloud_packet,
    format_support_ticket_list,
    list_support_tickets,
)


STORY = "story_012_agent_support_queue"


def create_story(project_path: Path, story: str = STORY) -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "status.yaml").write_text(
        f"story_id: {story}\n"
        "status: in_progress\n"
        "ready_for_review: false\n"
        "notes: preserve this field\n",
        encoding="utf-8",
    )
    return story_path


def read_yaml(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded or {}


def test_create_support_ticket_creates_pending_yaml_and_blocks_story_status(
    tmp_path: Path,
) -> None:
    story_path = create_story(tmp_path)

    result = create_support_ticket(
        project_path=tmp_path,
        story=STORY,
        agent="test_agent",
        blocker_type="requirements",
        question="Which error path should be preferred?",
        details="The story text is ambiguous about fallback behavior.",
        severity="high",
    )

    assert result.ticket_path == (
        tmp_path / ".agentic" / "support_queue" / "pending" / f"{result.ticket_id}.yaml"
    )
    assert result.ticket_path.exists()

    ticket = read_yaml(result.ticket_path)
    assert ticket["ticket_id"] == result.ticket_id
    assert ticket["story"] == STORY
    assert ticket["agent"] == "test_agent"
    assert ticket["blocker_type"] == "requirements"
    assert ticket["question"] == "Which error path should be preferred?"
    assert ticket["details"] == "The story text is ambiguous about fallback behavior."
    assert ticket["severity"] == "high"
    assert ticket["status"] == PENDING_CLOUD_REVIEW
    assert ticket["preferred_responder"] == "cloud_model"
    assert ticket["escalation_rule"] == "ask_human_if_cloud_model_is_uncertain"
    assert "created_at" in ticket

    assert result.story_status_path == story_path / "status.yaml"
    story_status = read_yaml(result.story_status_path)
    assert story_status["story_id"] == STORY
    assert story_status["status"] == "blocked"
    assert story_status["ready_for_review"] is False
    assert story_status["blocked_by"] == result.ticket_id
    assert story_status["notes"] == "preserve this field"


def test_list_support_tickets_lists_pending_tickets(tmp_path: Path) -> None:
    create_support_ticket(
        project_path=tmp_path,
        story=STORY,
        agent="test_agent",
        blocker_type="scope",
        question="Should the command move or copy tickets?",
    )

    result = list_support_tickets(tmp_path)

    assert len(result.tickets_by_queue["pending"]) == 1
    pending_ticket = result.tickets_by_queue["pending"][0]
    assert pending_ticket.story == STORY
    assert pending_ticket.agent == "test_agent"
    assert pending_ticket.status == PENDING_CLOUD_REVIEW
    assert result.tickets_by_queue["answered"] == []
    assert result.tickets_by_queue["escalated_to_human"] == []
    assert result.tickets_by_queue["closed"] == []

    rendered = format_support_ticket_list(result)
    assert "Support tickets:" in rendered
    assert "pending:" in rendered
    assert pending_ticket.ticket_id in rendered
    assert f"story={STORY}" in rendered
    assert "agent=test_agent" in rendered


def test_create_support_ticket_cloud_packet_writes_markdown_instructions(
    tmp_path: Path,
) -> None:
    ticket = create_support_ticket(
        project_path=tmp_path,
        story=STORY,
        agent="test_agent",
        blocker_type="command_failure",
        question="How should the agent handle a failed docker command?",
    )

    result = create_support_ticket_cloud_packet(tmp_path, ticket.ticket_id)

    assert result.ticket_id == ticket.ticket_id
    assert result.ticket_path == ticket.ticket_path
    assert result.packet_path.exists()
    assert result.packet_path.suffix == ".md"

    packet = result.packet_path.read_text(encoding="utf-8")
    assert "# Support Ticket Cloud Packet" in packet
    assert "Answer the agent's question if you are confident." in packet
    assert "Do not invent missing facts." in packet
    assert "Return `NEEDS_HUMAN` if the answer requires human" in packet
    assert "Return `REQUEST_MORE_CONTEXT` if more project context is required." in packet
    assert "How should the agent handle a failed docker command?" in packet
    assert "preferred_responder: cloud_model" in packet


def test_answer_support_ticket_records_answer_and_marks_ticket_answered(
    tmp_path: Path,
) -> None:
    ticket = create_support_ticket(
        project_path=tmp_path,
        story=STORY,
        agent="test_agent",
        blocker_type="requirements",
        question="Which file should the tests cover?",
    )
    create_support_ticket_cloud_packet(tmp_path, ticket.ticket_id)
    answer_file = tmp_path / "answer.md"
    answer_file.write_text("Cover the CLI and artifact policy paths.\n", encoding="utf-8")

    result = answer_support_ticket(
        project_path=tmp_path,
        ticket_id=ticket.ticket_id,
        answer_file=answer_file,
        answered_by="cloud_model",
    )

    assert result.ticket_id == ticket.ticket_id
    assert result.source_path == ticket.ticket_path
    assert result.destination_path == (
        tmp_path / ".agentic" / "support_queue" / "answered" / f"{ticket.ticket_id}.yaml"
    )
    assert not ticket.ticket_path.exists()
    assert result.destination_path.exists()

    answered_ticket = read_yaml(result.destination_path)
    assert answered_ticket["status"] == ANSWERED_STATUS
    assert answered_ticket["answered_by"] == "cloud_model"
    assert answered_ticket["answer"] == "Cover the CLI and artifact policy paths."
    assert "answered_at" in answered_ticket

    assert (
        tmp_path
        / ".agentic"
        / "support_queue"
        / "answered"
        / f"{ticket.ticket_id}.cloud-packet.md"
    ).exists()
    assert not (
        tmp_path
        / ".agentic"
        / "support_queue"
        / "pending"
        / f"{ticket.ticket_id}.cloud-packet.md"
    ).exists()


def test_close_support_ticket_marks_ticket_closed(tmp_path: Path) -> None:
    ticket = create_support_ticket(
        project_path=tmp_path,
        story=STORY,
        agent="test_agent",
        blocker_type="scope",
        question="Can this ticket be closed without an answer?",
    )
    create_support_ticket_cloud_packet(tmp_path, ticket.ticket_id)

    result = close_support_ticket(tmp_path, ticket.ticket_id)

    assert result.ticket_id == ticket.ticket_id
    assert result.destination_path == (
        tmp_path / ".agentic" / "support_queue" / "closed" / f"{ticket.ticket_id}.yaml"
    )
    assert not ticket.ticket_path.exists()
    assert result.destination_path.exists()

    closed_ticket = read_yaml(result.destination_path)
    assert closed_ticket["status"] == CLOSED_STATUS
    assert "closed_at" in closed_ticket
    assert (
        tmp_path
        / ".agentic"
        / "support_queue"
        / "closed"
        / f"{ticket.ticket_id}.cloud-packet.md"
    ).exists()


def test_missing_ticket_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Support ticket was not found") as error:
        create_support_ticket_cloud_packet(tmp_path, "SUPPORT-404")

    assert "SUPPORT-404" in str(error.value)


def test_missing_answer_file_raises_clear_error(tmp_path: Path) -> None:
    ticket = create_support_ticket(
        project_path=tmp_path,
        story=STORY,
        agent="test_agent",
        blocker_type="requirements",
        question="Where should the answer file live?",
    )
    missing_answer = tmp_path / "missing-answer.md"

    with pytest.raises(FileNotFoundError, match="Answer file does not exist") as error:
        answer_support_ticket(
            project_path=tmp_path,
            ticket_id=ticket.ticket_id,
            answer_file=missing_answer,
        )

    assert str(missing_answer.resolve()) in str(error.value)


def test_cli_support_ticket_create_and_list_use_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "support-ticket",
            "create",
            "--story",
            STORY,
            "--agent",
            "test_agent",
            "--blocker-type",
            "requirements",
            "--question",
            "Which command should I run?",
        ],
    )

    main()

    create_output = capsys.readouterr().out
    ticket_path = next((tmp_path / ".agentic" / "support_queue" / "pending").glob("SUPPORT-*.yaml"))
    ticket_id = ticket_path.stem
    assert "Support ticket created:" in create_output
    assert ticket_id in create_output
    assert "Story status updated:" in create_output

    monkeypatch.setattr("sys.argv", ["agentic", "support-ticket", "list"])

    main()

    list_output = capsys.readouterr().out
    assert "Support tickets:" in list_output
    assert "pending:" in list_output
    assert ticket_id in list_output
    assert f"story={STORY}" in list_output


def test_cli_support_ticket_cloud_packet_answer_and_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    ticket = create_support_ticket(
        project_path=tmp_path,
        story=STORY,
        agent="test_agent",
        blocker_type="command_failure",
        question="How should the cloud model respond?",
    )
    answer_file = tmp_path / "answer.txt"
    answer_file.write_text("Respond with the concrete command and rationale.\n", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "support-ticket", "cloud-packet", "--ticket", ticket.ticket_id],
    )
    main()
    cloud_packet_output = capsys.readouterr().out
    assert "Cloud packet created for:" in cloud_packet_output
    assert ticket.ticket_id in cloud_packet_output

    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "support-ticket",
            "answer",
            "--ticket",
            ticket.ticket_id,
            "--answer-file",
            str(answer_file),
        ],
    )
    main()
    answer_output = capsys.readouterr().out
    assert "Support ticket answered:" in answer_output
    assert ticket.ticket_id in answer_output

    monkeypatch.setattr(
        "sys.argv",
        ["agentic", "support-ticket", "close", "--ticket", ticket.ticket_id],
    )
    main()
    close_output = capsys.readouterr().out
    assert "Support ticket closed:" in close_output
    assert ticket.ticket_id in close_output
