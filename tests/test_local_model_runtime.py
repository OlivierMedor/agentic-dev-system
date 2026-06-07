from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.local_model_runtime import (
    LocalModelRuntimeConfig,
    build_headers,
    run_local_agent_prompt,
    run_local_model_dry_run,
    validate_local_model_runtime_config,
)
from agentic_dev.runtime_config import default_runtime_config_text


class FakeLocalModelHttpClient:
    def __init__(self, response_text: str = "LOCAL_MODEL_OK") -> None:
        self.response_text = response_text
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
        return {"choices": [{"message": {"content": self.response_text}}]}


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
    assert fake_client.calls[0]["payload"]["messages"] == [
        {"role": "user", "content": "Summarize the story."},
    ]


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
