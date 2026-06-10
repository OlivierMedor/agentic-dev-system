from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.local_model_runtime import (
    LOCAL_AGENT_DRAFT_PROMPT_FILES,
    LocalModelRuntimeConfig,
    build_headers,
    extract_response_text,
    run_local_agent_draft,
    run_local_agent_prompt,
    run_local_model_dry_run,
    validate_local_model_runtime_config,
)
from agentic_dev.runtime_config import default_runtime_config_text


class FakeLocalModelHttpClient:
    def __init__(
        self,
        response_text: str = "LOCAL_MODEL_OK",
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        self.response_text = response_text
        self.raw_response = raw_response
        self.calls: list[dict[str, Any]] = []

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "url": url,
                "payload": payload,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            },
        )
        if self.raw_response is not None:
            return self.raw_response

        return {
            "choices": [
                {"finish_reason": "stop", "message": {"content": self.response_text}},
            ],
        }


def write_runtime_config(project_path: Path, local_model_runtime: dict[str, Any]) -> Path:
    config = yaml.safe_load(default_runtime_config_text())
    config["local_model_runtime"] = local_model_runtime
    config_path = project_path / ".agentic" / "agent_runtime.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def valid_local_model_runtime_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "provider": "local_openai_compatible",
        "base_url": "http://host.docker.internal:1234/v1",
        "model": "qwen3-coder-30b-a3b-instruct",
        "api_key_env": "LOCAL_MODEL_API_KEY",
        "timeout_seconds": 120,
        "max_output_tokens": 4096,
        "temperature": 0.2,
    }


def create_story_prompt_pack(project_path: Path, story: str = "story_045_demo") -> Path:
    prompt_pack_path = project_path / "stories" / story / "prompt_pack"
    prompt_pack_path.mkdir(parents=True, exist_ok=True)
    for prompt_relative_path in set(LOCAL_AGENT_DRAFT_PROMPT_FILES.values()):
        prompt_path = project_path / "stories" / story / prompt_relative_path
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(f"Prompt file {prompt_path.name}", encoding="utf-8")
    return prompt_pack_path


def create_story_context(project_path: Path, story: str = "story_047_demo") -> Path:
    story_path = project_path / "stories" / story
    story_path.mkdir(parents=True, exist_ok=True)
    (story_path / "story.md").write_text(
        "\n".join(
            [
                "# Story 047",
                "",
                "## Goal",
                "",
                "Slim prompt story content.",
                "",
                "## Acceptance Criteria",
                "",
                "- Add micro prompt mode.",
                "- Keep full mode working.",
                "- Keep slim mode working.",
                "- Save a context packet.",
                "- Record metadata.",
                "- Exclude runtime artifacts.",
                "",
            ],
        ),
        encoding="utf-8",
    )
    (story_path / "status.yaml").write_text("status: in_progress\n", encoding="utf-8")
    (story_path / "test_plan.yaml").write_text("unit_tests: true\n", encoding="utf-8")
    (story_path / "monitoring_plan.yaml").write_text(
        "watch_for:\n  - truncated_local_model_output\n",
        encoding="utf-8",
    )
    (story_path / "agent_plan.yaml").write_text(
        "\n".join(
            [
                "assigned_agents:",
                "  - id: docs_agent",
                "    responsibility: Update documentation related to this story.",
                "    expected_output: reports/docs_report.md",
                "",
            ],
        ),
        encoding="utf-8",
    )
    instructions_path = story_path / "instructions" / "docs_agent.md"
    instructions_path.parent.mkdir(parents=True, exist_ok=True)
    instructions_path.write_text("Docs agent instruction content.", encoding="utf-8")
    return story_path


def test_local_model_config_validation_passes_for_valid_config(tmp_path: Path) -> None:
    config_path = write_runtime_config(tmp_path, valid_local_model_runtime_config())

    result = validate_local_model_runtime_config(tmp_path)

    assert result.passed is True
    assert result.configured is True
    assert result.config_path == config_path.resolve()


def test_local_model_validation_fails_for_missing_base_url(tmp_path: Path) -> None:
    config = valid_local_model_runtime_config()
    del config["base_url"]
    write_runtime_config(tmp_path, config)

    result = validate_local_model_runtime_config(tmp_path)

    assert result.passed is False
    assert "local_model_runtime.base_url must be a non-empty string." in result.errors


def test_local_model_validation_fails_for_invalid_provider(tmp_path: Path) -> None:
    config = valid_local_model_runtime_config()
    config["provider"] = "openai"
    write_runtime_config(tmp_path, config)

    result = validate_local_model_runtime_config(tmp_path)

    assert result.passed is False
    assert "local_model_runtime.provider must be local_openai_compatible." in result.errors


def test_local_model_validation_fails_for_missing_model(tmp_path: Path) -> None:
    config = valid_local_model_runtime_config()
    del config["model"]
    write_runtime_config(tmp_path, config)

    result = validate_local_model_runtime_config(tmp_path)

    assert result.passed is False
    assert "local_model_runtime.model must be a non-empty string." in result.errors


def test_local_model_validation_fails_for_non_boolean_enabled(tmp_path: Path) -> None:
    config = valid_local_model_runtime_config()
    config["enabled"] = "yes"
    write_runtime_config(tmp_path, config)

    result = validate_local_model_runtime_config(tmp_path)

    assert result.passed is False
    assert "local_model_runtime.enabled must be a boolean." in result.errors


def test_dry_run_uses_fake_http_client_and_writes_report(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    fake_client = FakeLocalModelHttpClient()

    result = run_local_model_dry_run(tmp_path, http_client=fake_client)

    assert result.response_text == "LOCAL_MODEL_OK"
    assert result.report_path == tmp_path.resolve() / "reports" / "local_model_dry_run_report.md"
    assert result.report_path.exists()
    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert call["url"] == "http://host.docker.internal:1234/v1/chat/completions"
    assert call["payload"]["model"] == "qwen3-coder-30b-a3b-instruct"
    assert call["payload"]["messages"] == [
        {"role": "user", "content": "Reply with LOCAL_MODEL_OK only."},
    ]
    assert call["timeout_seconds"] == 120

    report = result.report_path.read_text(encoding="utf-8")
    assert "Prompt content: not recorded" in report
    assert "Secret values: not recorded" in report
    assert "did not edit source files" in report
    assert "call cloud models" in report


def test_run_prompt_saves_response_to_output_file(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    prompt_file = tmp_path / "prompt.md"
    output_file = tmp_path / "reports" / "local_agent_output.md"
    prompt_file.write_text("Summarize the story.", encoding="utf-8")
    fake_client = FakeLocalModelHttpClient("raw local response")

    result = run_local_agent_prompt(tmp_path, prompt_file, output_file, fake_client)

    assert result.response_text == "raw local response"
    assert output_file.read_text(encoding="utf-8") == "raw local response"
    assert result.raw_response_path == tmp_path.resolve() / "reports" / "local_agent_output_raw_response.json"
    assert result.raw_response_path.exists()
    raw_response = yaml.safe_load(result.raw_response_path.read_text(encoding="utf-8"))
    assert raw_response["choices"][0]["message"]["content"] == "raw local response"
    assert fake_client.calls[0]["payload"]["messages"] == [
        {"role": "user", "content": "Summarize the story."},
    ]


@pytest.mark.parametrize("response_text", ["", "   \n\t"])
def test_run_prompt_treats_empty_or_whitespace_response_as_failure(
    tmp_path: Path,
    response_text: str,
) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    prompt_file = tmp_path / "prompt.md"
    output_file = tmp_path / "reports" / "local_agent_output.md"
    prompt_file.write_text("Summarize the story.", encoding="utf-8")
    fake_client = FakeLocalModelHttpClient(response_text)

    with pytest.raises(ValueError, match="Local model returned an empty response"):
        run_local_agent_prompt(tmp_path, prompt_file, output_file, fake_client)

    raw_response_path = tmp_path.resolve() / "reports" / "local_agent_output_raw_response.json"
    assert raw_response_path.exists()
    assert not output_file.exists()


def test_extract_response_text_supports_content_list_text_parts() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "first"},
                        {"type": "output_text", "text": " second"},
                    ],
                },
            },
        ],
    }

    assert extract_response_text(response) == "first second"


def test_extract_response_text_supports_choice_text() -> None:
    response = {"choices": [{"text": "legacy text response"}]}

    assert extract_response_text(response) == "legacy text response"


def test_extract_response_text_supports_top_level_output_text() -> None:
    response = {"output_text": "responses api final text"}

    assert extract_response_text(response) == "responses api final text"


def test_extract_response_text_ignores_hidden_reasoning_only_response() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "reasoning", "text": "private chain of thought"},
                    ],
                },
                "finish_reason": "stop",
            },
        ],
    }

    assert extract_response_text(response) == ""


def test_run_prompt_does_not_apply_code_changes(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    source_file = tmp_path / "src" / "app.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("print('original')\n", encoding="utf-8")
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Rewrite src/app.py.", encoding="utf-8")
    output_file = tmp_path / "local_output.md"
    fake_client = FakeLocalModelHttpClient("print('changed')\n")

    run_local_agent_prompt(tmp_path, prompt_file, output_file, fake_client)

    assert source_file.read_text(encoding="utf-8") == "print('original')\n"
    assert output_file.read_text(encoding="utf-8") == "print('changed')\n"


@pytest.mark.parametrize(
    ("agent", "prompt_filename"),
    [
        ("developer_agent", "03_developer_agent_prompt.md"),
        ("test_agent", "04_test_agent_prompt.md"),
        ("docs_agent", "05_docs_agent_prompt.md"),
        ("reviewer_agent", "07_local_reviewer_agent_prompt.md"),
        ("maintenance_agent", "07_local_reviewer_agent_prompt.md"),
    ],
)
def test_local_agent_draft_maps_supported_agents_to_prompt_files(
    tmp_path: Path,
    agent: str,
    prompt_filename: str,
) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_prompt_pack(tmp_path)
    fake_client = FakeLocalModelHttpClient("draft response")

    result = run_local_agent_draft(
        tmp_path,
        "story_045_demo",
        agent,
        model_label="gemma-4-26b",
        prompt_mode="full",
        http_client=fake_client,
    )

    assert result.prompt_file.name == prompt_filename
    assert fake_client.calls[0]["payload"]["messages"] == [
        {"role": "user", "content": f"Prompt file {prompt_filename}"},
    ]


def test_local_agent_draft_defaults_to_slim_prompt_mode(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_context(tmp_path)
    fake_client = FakeLocalModelHttpClient("draft response")

    result = run_local_agent_draft(
        tmp_path,
        "story_047_demo",
        "docs_agent",
        model_label="gemma-4-26b",
        http_client=fake_client,
    )

    prompt = fake_client.calls[0]["payload"]["messages"][0]["content"]
    assert result.prompt_mode == "slim"
    assert result.context_file == result.prompt_file
    assert result.context_file == (
        tmp_path.resolve()
        / "stories"
        / "story_047_demo"
        / "reports"
        / "local_agent_context"
        / "docs_agent_gemma-4-26b_context.md"
    )
    assert result.context_file.exists()
    assert "Slim prompt story content." in prompt


def test_local_agent_draft_prompt_file_uses_custom_prompt_mode(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_context(tmp_path)
    prompt_file = tmp_path / "custom_prompt.md"
    prompt_file.write_text("Custom prompt content.", encoding="utf-8")
    fake_client = FakeLocalModelHttpClient("custom draft")

    result = run_local_agent_draft(
        tmp_path,
        "story_047_demo",
        "docs_agent",
        prompt_file=prompt_file,
        model_label="gemma-4-26b",
        prompt_mode="full",
        http_client=fake_client,
    )

    metadata = yaml.safe_load(result.metadata_file.read_text(encoding="utf-8"))
    assert result.prompt_mode == "custom"
    assert metadata["prompt_mode"] == "custom"
    assert metadata["prompt_file"] == str(prompt_file.resolve())
    assert "context_file" not in metadata
    assert fake_client.calls[0]["payload"]["messages"] == [
        {"role": "user", "content": "Custom prompt content."},
    ]


def test_local_agent_draft_slim_mode_creates_context_packet_with_allowed_sources(
    tmp_path: Path,
) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    story_path = create_story_context(tmp_path)
    review_bundle_file = story_path / "review_bundle" / "handoff.md"
    review_bundle_file.parent.mkdir(parents=True)
    review_bundle_file.write_text("review bundle content must be excluded", encoding="utf-8")
    cloud_packet_file = story_path / "cloud_review_packet" / "cloud_review_export.md"
    cloud_packet_file.parent.mkdir(parents=True)
    cloud_packet_file.write_text("cloud packet content must be excluded", encoding="utf-8")
    fake_client = FakeLocalModelHttpClient("draft response")

    result = run_local_agent_draft(
        tmp_path,
        "story_047_demo",
        "docs_agent",
        model_label="gemma-4-26b",
        prompt_mode="slim",
        http_client=fake_client,
    )

    assert result.context_file is not None
    context = result.context_file.read_text(encoding="utf-8")
    metadata = yaml.safe_load(result.metadata_file.read_text(encoding="utf-8"))
    assert "# Local Agent Slim Context Packet" in context
    assert "Slim prompt story content." in context
    assert "Docs agent instruction content." in context
    assert "Return final answer only in the visible assistant message content." in context
    assert "Do not use hidden/internal reasoning as the answer." in context
    assert "Keep response under 1200 words unless asked otherwise." in context
    assert "Do not wrap the entire answer in a Markdown code fence." in context
    assert "Use the requested headings exactly." in context
    assert "review bundle content must be excluded" not in context
    assert "cloud packet content must be excluded" not in context
    assert metadata["prompt_mode"] == "slim"
    assert metadata["context_file"] == str(result.context_file)
    assert metadata["context_character_count"] == len(context)
    assert str(story_path / "story.md") in metadata["source_files_used"]
    assert str(story_path / "instructions" / "docs_agent.md") in metadata["source_files_used"]
    assert "prompt_file" not in metadata


def test_local_agent_draft_micro_mode_creates_small_context_packet(
    tmp_path: Path,
) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    story_path = create_story_context(tmp_path)
    excluded_files = {
        story_path / "review_bundle" / "handoff.md": "review_bundle excluded content",
        story_path / "cloud_review_packet" / "cloud_review_export.md": (
            "cloud_review_packet excluded content"
        ),
        story_path / "remote_dev_validation" / "packet.md": (
            "remote_dev_validation excluded content"
        ),
        story_path / "reports" / "local_agent_drafts" / "old_draft.md": (
            "previous draft output excluded content"
        ),
        story_path / "reports" / "local_agent_drafts" / "old_raw_response.json": (
            "raw response excluded content"
        ),
        story_path / "prompt_pack" / "05_docs_agent_prompt.md": (
            "long prompt pack excluded content"
        ),
        story_path / "reports" / "large_report.md": "large report excluded content",
    }
    for path, content in excluded_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    fake_client = FakeLocalModelHttpClient("micro draft response")

    result = run_local_agent_draft(
        tmp_path,
        "story_047_demo",
        "docs_agent",
        model_label="gemma-4-26b",
        prompt_mode="micro",
        http_client=fake_client,
    )

    assert result.context_file is not None
    context = result.context_file.read_text(encoding="utf-8")
    metadata = yaml.safe_load(result.metadata_file.read_text(encoding="utf-8"))
    assert result.prompt_mode == "micro"
    assert "# Local Agent Micro Context Packet" in context
    assert "prompt_mode: micro" in context
    assert "story: story_047_demo" in context
    assert "agent: docs_agent" in context
    assert "Update documentation related to this story." in context
    assert "Slim prompt story content." in context
    assert "Add micro prompt mode." in context
    assert "Exclude runtime artifacts." not in context
    assert str(result.output_file) in context
    assert "Return only the final visible answer in message.content." in context
    assert "Do not put the answer only in reasoning_content." in context
    assert "Do not include hidden reasoning." in context
    assert "return a short visible explanation" in context
    assert len(context) < 2000
    for content in excluded_files.values():
        assert content not in context
    assert metadata["prompt_mode"] == "micro"
    assert metadata["context_file"] == str(result.context_file)
    assert metadata["context_character_count"] == len(context)
    assert str(story_path / "story.md") in metadata["source_files_used"]
    assert str(story_path / "agent_plan.yaml") in metadata["source_files_used"]
    assert "prompt_file" not in metadata


def test_local_agent_draft_micro_context_is_smaller_than_slim_context(
    tmp_path: Path,
) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_context(tmp_path)
    slim = run_local_agent_draft(
        tmp_path,
        "story_047_demo",
        "docs_agent",
        model_label="gemma-slim",
        prompt_mode="slim",
        http_client=FakeLocalModelHttpClient("slim draft response"),
    )
    micro = run_local_agent_draft(
        tmp_path,
        "story_047_demo",
        "docs_agent",
        model_label="gemma-micro",
        prompt_mode="micro",
        http_client=FakeLocalModelHttpClient("micro draft response"),
    )

    slim_metadata = yaml.safe_load(slim.metadata_file.read_text(encoding="utf-8"))
    micro_metadata = yaml.safe_load(micro.metadata_file.read_text(encoding="utf-8"))
    assert micro_metadata["context_character_count"] < slim_metadata["context_character_count"]


def test_local_agent_draft_micro_empty_reasoning_only_response_fails(
    tmp_path: Path,
) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_context(tmp_path)
    fake_client = FakeLocalModelHttpClient(
        raw_response={
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {
                        "content": "",
                        "reasoning_content": "internal reasoning only",
                    },
                },
            ],
        },
    )

    with pytest.raises(ValueError, match="Local model returned an empty response"):
        run_local_agent_draft(
            tmp_path,
            "story_047_demo",
            "docs_agent",
            model_label="gemma-4-26b",
            prompt_mode="micro",
            http_client=fake_client,
        )

    metadata_path = (
        tmp_path.resolve()
        / "stories"
        / "story_047_demo"
        / "reports"
        / "local_agent_drafts"
        / "docs_agent_gemma-4-26b_draft.yaml"
    )
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    assert metadata["prompt_mode"] == "micro"
    assert metadata["status"] == "empty_model_response"
    assert metadata["response_character_count"] == 0
    assert any(
        "local model returned hidden/internal reasoning" in warning
        for warning in metadata["warnings"]
    )


def test_local_agent_draft_raises_clear_error_for_missing_story(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())

    with pytest.raises(FileNotFoundError, match="Story folder does not exist"):
        run_local_agent_draft(
            tmp_path,
            "story_missing",
            "docs_agent",
            model_label="gemma-4-26b",
            http_client=FakeLocalModelHttpClient(),
        )


def test_local_agent_draft_raises_clear_error_for_missing_prompt_file(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    prompt_pack_path = tmp_path / "stories" / "story_045_demo" / "prompt_pack"
    prompt_pack_path.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="Prompt file does not exist"):
        run_local_agent_draft(
            tmp_path,
            "story_045_demo",
            "docs_agent",
            model_label="gemma-4-26b",
            prompt_mode="full",
            http_client=FakeLocalModelHttpClient(),
        )


def test_local_agent_draft_refuses_when_local_runtime_disabled(tmp_path: Path) -> None:
    config = valid_local_model_runtime_config()
    config["enabled"] = False
    write_runtime_config(tmp_path, config)
    create_story_prompt_pack(tmp_path)
    fake_client = FakeLocalModelHttpClient()

    with pytest.raises(ValueError, match="local_model_runtime.enabled must be true"):
        run_local_agent_draft(
            tmp_path,
            "story_045_demo",
            "docs_agent",
            model_label="gemma-4-26b",
            prompt_mode="full",
            http_client=fake_client,
        )

    assert fake_client.calls == []


def test_local_agent_draft_saves_markdown_output_and_metadata_yaml(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_prompt_pack(tmp_path)
    fake_client = FakeLocalModelHttpClient("## Draft\n\nUse this after review.")

    result = run_local_agent_draft(
        tmp_path,
        "story_045_demo",
        "docs_agent",
        model_label="gemma-4-26b",
        prompt_mode="full",
        http_client=fake_client,
    )

    assert result.output_file == (
        tmp_path.resolve()
        / "stories"
        / "story_045_demo"
        / "reports"
        / "local_agent_drafts"
        / "docs_agent_gemma-4-26b_draft.md"
    )
    assert result.output_file.read_text(encoding="utf-8") == "## Draft\n\nUse this after review."
    assert result.raw_response_file == (
        tmp_path.resolve()
        / "stories"
        / "story_045_demo"
        / "reports"
        / "local_agent_drafts"
        / "docs_agent_gemma-4-26b_raw_response.json"
    )
    assert result.raw_response_file.exists()
    metadata = yaml.safe_load(result.metadata_file.read_text(encoding="utf-8"))
    assert metadata["story"] == "story_045_demo"
    assert metadata["agent"] == "docs_agent"
    assert metadata["model_label"] == "gemma-4-26b"
    assert metadata["configured_model"] == "qwen3-coder-30b-a3b-instruct"
    assert metadata["prompt_mode"] == "full"
    assert metadata["prompt_file"] == str(result.prompt_file)
    assert "context_file" not in metadata
    assert metadata["output_file"] == str(result.output_file)
    assert metadata["raw_response_file"] == str(result.raw_response_file)
    assert metadata["prompt_character_count"] == len("Prompt file 05_docs_agent_prompt.md")
    assert metadata["response_character_count"] == len("## Draft\n\nUse this after review.")
    assert metadata["finish_reason"] == "stop"
    assert metadata["status"] == "draft_saved"
    assert metadata["warnings"] == []
    assert metadata["applied_to_source"] is False
    assert metadata["executed_model_output"] is False
    assert metadata["called_cloud_models"] is False
    assert metadata["called_github_apis"] is False
    assert metadata["committed_or_merged"] is False
    assert metadata["deployed"] is False
    assert "Human/Codex review required" in metadata["next_action"]


@pytest.mark.parametrize("response_text", ["", "   \n\t"])
def test_local_agent_draft_treats_empty_or_whitespace_response_as_failure(
    tmp_path: Path,
    response_text: str,
) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_prompt_pack(tmp_path)
    fake_client = FakeLocalModelHttpClient(response_text)

    with pytest.raises(ValueError, match="Local model returned an empty response"):
        run_local_agent_draft(
            tmp_path,
            "story_045_demo",
            "docs_agent",
            model_label="gemma-4-26b",
            prompt_mode="full",
            http_client=fake_client,
        )

    draft_path = (
        tmp_path.resolve()
        / "stories"
        / "story_045_demo"
        / "reports"
        / "local_agent_drafts"
        / "docs_agent_gemma-4-26b_draft.md"
    )
    metadata_path = draft_path.with_suffix(".yaml")
    raw_response_path = draft_path.with_name("docs_agent_gemma-4-26b_raw_response.json")

    assert not draft_path.exists()
    assert raw_response_path.exists()
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "empty_model_response"
    assert metadata["response_character_count"] == 0
    assert metadata["raw_response_file"] == str(raw_response_path)
    assert metadata["applied_to_source"] is False
    assert metadata["executed_model_output"] is False
    assert metadata["called_cloud_models"] is False
    assert metadata["called_github_apis"] is False
    assert metadata["committed_or_merged"] is False
    assert metadata["deployed"] is False
    assert "Inspect the raw response JSON" in metadata["next_action"]
    assert "draft_saved" not in metadata["status"]


def test_local_agent_draft_saves_nonempty_length_response_with_warning(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_context(tmp_path)
    fake_client = FakeLocalModelHttpClient(
        raw_response={
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": "Partial draft content."},
                },
            ],
        },
    )

    result = run_local_agent_draft(
        tmp_path,
        "story_047_demo",
        "docs_agent",
        model_label="gemma-4-26b",
        http_client=fake_client,
    )

    metadata = yaml.safe_load(result.metadata_file.read_text(encoding="utf-8"))
    assert result.output_file.read_text(encoding="utf-8") == "Partial draft content."
    assert result.raw_response_file.exists()
    assert result.status == "draft_saved_with_warning"
    assert result.warnings == ["model output may be truncated"]
    assert metadata["status"] == "draft_saved_with_warning"
    assert metadata["warnings"] == ["model output may be truncated"]
    assert metadata["finish_reason"] == "length"
    assert metadata["response_character_count"] == len("Partial draft content.")
    assert metadata["next_action"] == (
        "Review draft carefully or retry with slim prompt / higher output token limit."
    )


def test_local_agent_draft_empty_length_response_fails_as_empty_model_response(
    tmp_path: Path,
) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_context(tmp_path)
    fake_client = FakeLocalModelHttpClient(
        raw_response={
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": ""},
                },
            ],
        },
    )

    with pytest.raises(ValueError, match="Local model returned an empty response"):
        run_local_agent_draft(
            tmp_path,
            "story_047_demo",
            "docs_agent",
            model_label="gemma-4-26b",
            http_client=fake_client,
        )

    metadata_path = (
        tmp_path.resolve()
        / "stories"
        / "story_047_demo"
        / "reports"
        / "local_agent_drafts"
        / "docs_agent_gemma-4-26b_draft.yaml"
    )
    raw_response_path = metadata_path.with_name("docs_agent_gemma-4-26b_raw_response.json")
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    assert raw_response_path.exists()
    assert metadata["status"] == "empty_model_response"
    assert metadata["finish_reason"] == "length"
    assert metadata["response_character_count"] == 0
    assert "model output may be truncated" in metadata["warnings"]


def test_local_agent_draft_does_not_edit_source_or_execute_model_output(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_prompt_pack(tmp_path)
    source_file = tmp_path / "src" / "app.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("print('original')\n", encoding="utf-8")
    marker_file = tmp_path / "marker.txt"
    marker_file.write_text("still here\n", encoding="utf-8")
    fake_client = FakeLocalModelHttpClient(
        "Replace src/app.py with changed content and run: Remove-Item marker.txt",
    )

    result = run_local_agent_draft(
        tmp_path,
        "story_045_demo",
        "developer_agent",
        model_label="devstral",
        prompt_mode="full",
        http_client=fake_client,
    )

    assert source_file.read_text(encoding="utf-8") == "print('original')\n"
    assert marker_file.read_text(encoding="utf-8") == "still here\n"
    assert "Remove-Item marker.txt" in result.output_file.read_text(encoding="utf-8")


def test_local_agent_draft_does_not_overwrite_without_force(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_prompt_pack(tmp_path)
    run_local_agent_draft(
        tmp_path,
        "story_045_demo",
        "docs_agent",
        model_label="gemma-4-26b",
        prompt_mode="full",
        http_client=FakeLocalModelHttpClient("first"),
    )

    with pytest.raises(ValueError, match="already exists"):
        run_local_agent_draft(
            tmp_path,
            "story_045_demo",
            "docs_agent",
            model_label="gemma-4-26b",
            prompt_mode="full",
            http_client=FakeLocalModelHttpClient("second"),
        )


def test_local_agent_draft_force_overwrites_existing_output(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_prompt_pack(tmp_path)
    first = run_local_agent_draft(
        tmp_path,
        "story_045_demo",
        "docs_agent",
        model_label="gemma-4-26b",
        prompt_mode="full",
        http_client=FakeLocalModelHttpClient("first"),
    )

    second = run_local_agent_draft(
        tmp_path,
        "story_045_demo",
        "docs_agent",
        model_label="gemma-4-26b",
        prompt_mode="full",
        force=True,
        http_client=FakeLocalModelHttpClient("second"),
    )

    assert second.output_file == first.output_file
    assert second.output_file.read_text(encoding="utf-8") == "second"


def test_cli_local_agent_draft_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    create_story_prompt_pack(tmp_path)
    output_file = tmp_path / "draft.md"

    def fake_run_local_agent_draft(**kwargs: Any) -> Any:
        assert kwargs["project_path"] == Path.cwd()
        assert kwargs["story"] == "story_045_demo"
        assert kwargs["agent"] == "docs_agent"
        assert kwargs["prompt_mode"] == "slim"
        output_file.write_text("fake draft", encoding="utf-8")
        metadata_file = tmp_path / "draft.yaml"
        metadata_file.write_text("status: draft_saved\n", encoding="utf-8")
        return type(
            "DraftResult",
            (),
            {
                "output_file": output_file,
                "metadata_file": metadata_file,
                "raw_response_file": tmp_path / "draft_raw_response.json",
                "context_file": tmp_path / "context.md",
                "status": "draft_saved",
                "prompt_mode": "slim",
                "warnings": [],
            },
        )()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("agentic_dev.cli.run_local_agent_draft", fake_run_local_agent_draft)
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "local-agent",
            "draft",
            "--story",
            "story_045_demo",
            "--agent",
            "docs_agent",
        ],
    )

    main()

    captured = capsys.readouterr()
    assert "Local agent draft saved." in captured.out
    assert "Prompt mode: slim" in captured.out
    assert "Safety: draft output was saved only" in captured.out


def test_cli_local_agent_draft_accepts_micro_prompt_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_file = tmp_path / "draft.md"

    def fake_run_local_agent_draft(**kwargs: Any) -> Any:
        assert kwargs["prompt_mode"] == "micro"
        metadata_file = tmp_path / "draft.yaml"
        return type(
            "DraftResult",
            (),
            {
                "output_file": output_file,
                "metadata_file": metadata_file,
                "raw_response_file": tmp_path / "draft_raw_response.json",
                "context_file": tmp_path / "context.md",
                "status": "draft_saved",
                "prompt_mode": "micro",
                "warnings": [],
            },
        )()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("agentic_dev.cli.run_local_agent_draft", fake_run_local_agent_draft)
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "local-agent",
            "draft",
            "--story",
            "story_047_demo",
            "--agent",
            "docs_agent",
            "--prompt-mode",
            "micro",
        ],
    )

    main()

    captured = capsys.readouterr()
    assert "Prompt mode: micro" in captured.out


def test_cli_local_model_validate_prints_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_runtime_config(tmp_path, valid_local_model_runtime_config())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "local-model", "validate"])

    main()

    captured = capsys.readouterr()
    assert "Local model runtime validation passed:" in captured.out


def test_build_headers_uses_env_key_without_exposing_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_MODEL_API_KEY", "secret-value")
    config = LocalModelRuntimeConfig(
        enabled=True,
        provider="local_openai_compatible",
        base_url="http://host.docker.internal:1234/v1",
        model="qwen3-coder-30b-a3b-instruct",
        timeout_seconds=120,
        api_key_env="LOCAL_MODEL_API_KEY",
    )

    headers = build_headers(config)

    assert headers["Authorization"] == "Bearer secret-value"
    assert "LOCAL_MODEL_API_KEY" not in headers["Authorization"]


def test_readme_links_to_local_models_doc() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "docs/local_models.md" in readme
    assert "agentic local-model validate" in readme


def test_local_models_doc_mentions_tools_models_and_safety_boundaries() -> None:
    guide = Path("docs/local_models.md").read_text(encoding="utf-8")

    required_phrases = [
        "LM Studio",
        "Ollama",
        "Qwen3-Coder",
        "Devstral",
        "Gemma",
        "host.docker.internal",
        "does not apply code changes",
        "does not commit, push, merge, deploy, or call GitHub APIs",
        "Cloud models are not called",
    ]

    for phrase in required_phrases:
        assert phrase in guide


def test_readme_or_docs_link_to_local_agent_drafts_doc() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    local_models = Path("docs/local_models.md").read_text(encoding="utf-8")
    local_agent_drafts = Path("docs/local_agent_drafts.md").read_text(encoding="utf-8")

    assert "docs/local_agent_drafts.md" in readme
    assert "docs/local_agent_drafts.md" in local_models
    assert "docs/local_agent_context_packets.md" in readme
    assert "docs/local_agent_context_packets.md" in local_models
    assert "docs/local_agent_context_packets.md" in local_agent_drafts


def test_local_agent_context_packets_doc_explains_slim_mode_and_truncation() -> None:
    guide = Path("docs/local_agent_context_packets.md").read_text(encoding="utf-8")

    required_phrases = [
        "one-page work orders",
        "prompt_mode: slim",
        "prompt_mode: micro",
        "Gemma",
        "reasoning_content",
        "finish_reason: length",
        "draft_saved_with_warning",
        "empty_model_response",
        "Return only the final visible answer in message.content",
        "Human/Codex review",
        "does not execute model output",
    ]

    for phrase in required_phrases:
        assert phrase in guide


def test_local_agent_drafts_doc_mentions_models_tools_and_review_boundaries() -> None:
    guide = Path("docs/local_agent_drafts.md").read_text(encoding="utf-8")

    required_phrases = [
        "Gemma",
        "Devstral",
        "Qwen",
        "LM Studio",
        "save-only",
        "Human/Codex review",
        "human/cloud review",
        "High-risk DeFi",
        "agentic local-agent draft",
        "plain ASCII",
        "empty_model_response",
        "raw response JSON",
        "model/server mismatch",
        "prompt too large",
        "unsupported response shape",
        "model refuses to produce final content",
        "--prompt-mode slim",
        "--prompt-mode micro",
        "draft_saved_with_warning",
        "model output may be truncated",
    ]

    for phrase in required_phrases:
        assert phrase in guide
