from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("docs/cloud_queue_operator_guide.md")
README_PATH = Path("README.md")
COMMAND_MAP_PATH = Path("docs/command_map.md")


def test_cloud_queue_operator_guide_exists() -> None:
    assert DOC_PATH.exists()


def test_readme_links_to_cloud_queue_operator_guide() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    assert "docs/cloud_queue_operator_guide.md" in readme
    assert "agentic cloud-queue" in readme


def test_command_map_mentions_cloud_queue_commands() -> None:
    command_map = COMMAND_MAP_PATH.read_text(encoding="utf-8")
    assert "agentic cloud-queue create" in command_map
    assert "agentic cloud-queue export" in command_map
    assert "agentic cloud-queue import" in command_map
    assert "agentic cloud-queue approve" in command_map
    assert "agentic cloud-queue status" in command_map


def test_cloud_queue_operator_guide_mentions_manual_first_flow() -> None:
    guide = DOC_PATH.read_text(encoding="utf-8")
    assert "manual-first" in guide
    assert "ChatGPT" in guide
    assert "Gemini" in guide
    assert "agentic cloud-queue export --all-ready" in guide
    assert "No paid cloud API calls" in guide or "paid cloud API calls" in guide

