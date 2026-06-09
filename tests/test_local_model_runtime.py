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
        http_client=fake_client,
    )

    assert result.prompt_file.name == prompt_filename
    assert fake_client.calls[0]["payload"]["messages"] == [
        {"role": "user", "content": f"Prompt file {prompt_filename}"},
    ]


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
    assert metadata["prompt_file"] == str(result.prompt_file)
    assert metadata["output_file"] == str(result.output_file)
    assert metadata["raw_response_file"] == str(result.raw_response_file)
    assert metadata["prompt_character_count"] == len("Prompt file 05_docs_agent_prompt.md")
    assert metadata["response_character_count"] == len("## Draft\n\nUse this after review.")
    assert metadata["finish_reason"] == "stop"
    assert metadata["status"] == "draft_saved"
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
        http_client=FakeLocalModelHttpClient("first"),
    )

    with pytest.raises(ValueError, match="already exists"):
        run_local_agent_draft(
            tmp_path,
            "story_045_demo",
            "docs_agent",
            model_label="gemma-4-26b",
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
        http_client=FakeLocalModelHttpClient("first"),
    )

    second = run_local_agent_draft(
        tmp_path,
        "story_045_demo",
        "docs_agent",
        model_label="gemma-4-26b",
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
    assert "Safety: draft output was saved only" in captured.out


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

    assert "docs/local_agent_drafts.md" in readme
    assert "docs/local_agent_drafts.md" in local_models


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
    ]

    for phrase in required_phrases:
        assert phrase in guide
