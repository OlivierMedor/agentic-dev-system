from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.local_model_scorecard import (
    PROMPT_FILES,
    SCORECARD_DIMENSIONS,
    create_local_model_scorecard,
    create_local_model_scorecard_report,
    run_local_model_scorecard,
)
from agentic_dev.runtime_config import default_runtime_config_text


class FakeLocalModelHttpClient:
    def __init__(self, response_text: str = "scorecard response") -> None:
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


def write_runtime_config(project_path: Path, enabled: bool = True) -> Path:
    config = yaml.safe_load(default_runtime_config_text())
    config["local_model_runtime"] = {
        "enabled": enabled,
        "provider": "local_openai_compatible",
        "base_url": "http://host.docker.internal:1234/v1",
        "model": "qwen3-coder-30b-a3b-instruct",
        "api_key_env": "LOCAL_MODEL_API_KEY",
        "timeout_seconds": 120,
        "max_output_tokens": 4096,
        "temperature": 0.2,
    }
    config_path = project_path / ".agentic" / "agent_runtime.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def test_scorecard_create_creates_prompt_files(tmp_path: Path) -> None:
    result = create_local_model_scorecard(tmp_path)
    prompts_path = tmp_path / ".agentic" / "local_model_scorecard" / "prompts"

    for filename in PROMPT_FILES:
        prompt = prompts_path / filename
        assert prompt.exists()
        prompt_text = prompt.read_text(encoding="utf-8")
        assert "Required Output" in prompt_text
        assert "Safety Check" in prompt_text

    assert result.scorecard_path == tmp_path / ".agentic" / "local_model_scorecard"


def test_scorecard_create_creates_scorecard_template(tmp_path: Path) -> None:
    create_local_model_scorecard(tmp_path)

    template = yaml.safe_load(
        (tmp_path / ".agentic" / "local_model_scorecard" / "scorecard_template.yaml").read_text(
            encoding="utf-8",
        ),
    )

    assert template["dimensions"] == SCORECARD_DIMENSIONS
    assert "Developer Agent" in template["recommended_role_mapping"]
    assert "overall_fit_for_role" in template["scores"][0]


def test_scorecard_create_does_not_overwrite_without_force(tmp_path: Path) -> None:
    create_local_model_scorecard(tmp_path)
    prompt = (
        tmp_path
        / ".agentic"
        / "local_model_scorecard"
        / "prompts"
        / "developer_agent_prompt.md"
    )
    prompt.write_text("keep this prompt\n", encoding="utf-8")

    result = create_local_model_scorecard(tmp_path)

    assert prompt.read_text(encoding="utf-8") == "keep this prompt\n"
    assert prompt in result.skipped_files


def test_scorecard_create_force_overwrites_existing_files(tmp_path: Path) -> None:
    create_local_model_scorecard(tmp_path)
    prompt = (
        tmp_path
        / ".agentic"
        / "local_model_scorecard"
        / "prompts"
        / "developer_agent_prompt.md"
    )
    prompt.write_text("keep this prompt\n", encoding="utf-8")

    create_local_model_scorecard(tmp_path, force=True)

    assert "Local Model Scorecard Prompt: Developer Agent" in prompt.read_text(
        encoding="utf-8",
    )


def test_scorecard_run_uses_fake_http_client_and_saves_responses(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    create_local_model_scorecard(tmp_path)
    fake_client = FakeLocalModelHttpClient("raw model answer")

    result = run_local_model_scorecard(tmp_path, "qwen3-coder-30b", http_client=fake_client)

    assert result.result_path == (
        tmp_path.resolve()
        / ".agentic"
        / "local_model_scorecard"
        / "results"
        / "qwen3-coder-30b"
    )
    assert len(result.prompt_runs) == len(PROMPT_FILES)
    assert len(fake_client.calls) == len(PROMPT_FILES)
    for prompt_run in result.prompt_runs:
        assert prompt_run.response_path.read_text(encoding="utf-8") == "raw model answer"
        assert prompt_run.raw_response_path.exists()

    summary = result.run_summary_path.read_text(encoding="utf-8")
    assert "Prompt responses saved: 5" in summary
    assert "did not edit source files" in summary
    assert "call cloud models" in summary


def test_scorecard_run_refuses_when_local_model_runtime_disabled(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, enabled=False)
    create_local_model_scorecard(tmp_path)
    fake_client = FakeLocalModelHttpClient()

    with pytest.raises(ValueError, match="local_model_runtime.enabled must be true"):
        run_local_model_scorecard(tmp_path, "devstral", http_client=fake_client)

    assert fake_client.calls == []


def test_scorecard_run_does_not_edit_source_files(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    create_local_model_scorecard(tmp_path)
    source_file = tmp_path / "src" / "app.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("print('original')\n", encoding="utf-8")
    fake_client = FakeLocalModelHttpClient("Replace src/app.py with print('changed')")

    run_local_model_scorecard(tmp_path, "gemma", http_client=fake_client)

    assert source_file.read_text(encoding="utf-8") == "print('original')\n"


def test_scorecard_report_creates_report(tmp_path: Path) -> None:
    create_local_model_scorecard(tmp_path)
    result_folder = tmp_path / ".agentic" / "local_model_scorecard" / "results" / "qwen25"
    result_folder.mkdir(parents=True)
    (result_folder / "developer_agent_prompt_response.md").write_text(
        "response\n",
        encoding="utf-8",
    )

    result = create_local_model_scorecard_report(tmp_path)

    assert result.report_path == tmp_path.resolve() / "reports" / "local_model_scorecard_report.md"
    report = result.report_path.read_text(encoding="utf-8")
    assert "# Local Model Scorecard Report" in report
    assert "`qwen25`" in report
    assert "developer_agent_prompt_response.md" in report
    assert "Do not claim a winner" in report


def test_cli_scorecard_create_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "local-model", "scorecard-create"])

    main()

    captured = capsys.readouterr()
    assert "Local model scorecard created at:" in captured.out
    assert (
        tmp_path / ".agentic" / "local_model_scorecard" / "prompts" / "test_agent_prompt.md"
    ).exists()


def test_readme_links_to_local_model_scorecard_doc() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "docs/local_model_scorecard.md" in readme
    assert "agentic local-model scorecard-create" in readme


def test_local_model_scorecard_doc_mentions_models_tools_and_safety_boundaries() -> None:
    guide = Path("docs/local_model_scorecard.md").read_text(encoding="utf-8")

    required_phrases = [
        "Qwen3 Coder",
        "Devstral",
        "Qwen2.5 Coder",
        "Gemma",
        "LM Studio",
        "Ollama",
        "must not be applied to source code automatically",
        "must not run shell commands from model output",
        "must not call cloud models",
        "cloud/human review is still needed",
    ]

    for phrase in required_phrases:
        assert phrase in guide
