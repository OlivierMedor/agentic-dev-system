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
    recommend_local_model_roles,
    run_local_model_scorecard,
    scaffold_local_model_scorecard_scores,
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


def write_fake_scorecard_response(project_path: Path, model_label: str, role: str) -> Path:
    response_path = (
        project_path
        / ".agentic"
        / "local_model_scorecard"
        / "results"
        / model_label
        / f"{role}_prompt_response.md"
    )
    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(f"{model_label} {role} response\n", encoding="utf-8")
    return response_path


def complete_score_entry(
    model_label: str,
    role: str,
    overall_fit_for_role: int,
    *,
    safety_compliance: int = 4,
    hallucination_control: int = 4,
    correctness: int = 4,
    instruction_following: int = 4,
) -> dict[str, object]:
    return {
        "model_label": model_label,
        "role": role,
        "response_file": (
            f".agentic/local_model_scorecard/results/{model_label}/"
            f"{role}_prompt_response.md"
        ),
        "instruction_following": instruction_following,
        "correctness": correctness,
        "hallucination_control": hallucination_control,
        "code_quality": 4,
        "test_quality": 4,
        "safety_compliance": safety_compliance,
        "clarity": 4,
        "overall_fit_for_role": overall_fit_for_role,
        "speed_notes": "",
        "reviewer_notes": "human scored",
    }


def write_scorecard_scores(project_path: Path, entries: list[dict[str, object]]) -> Path:
    scores_path = (
        project_path / ".agentic" / "local_model_scorecard" / "scorecard_scores.yaml"
    )
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    scores_path.write_text(
        yaml.safe_dump({"scorecard_scores_version": 1, "scores": entries}, sort_keys=False),
        encoding="utf-8",
    )
    return scores_path


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


def test_scorecard_scaffold_scores_creates_scores_from_fake_results(tmp_path: Path) -> None:
    write_fake_scorecard_response(tmp_path, "qwen3-coder-30b", "developer_agent")
    write_fake_scorecard_response(tmp_path, "devstral-small-2", "test_agent")

    result = scaffold_local_model_scorecard_scores(tmp_path)

    assert result.scores_path == (
        tmp_path.resolve() / ".agentic" / "local_model_scorecard" / "scorecard_scores.yaml"
    )
    loaded = yaml.safe_load(result.scores_path.read_text(encoding="utf-8"))
    assert len(loaded["scores"]) == 2
    assert loaded["scores"][0]["model_label"] == "devstral-small-2"
    assert loaded["scores"][0]["role"] == "test_agent"
    assert loaded["scores"][0]["instruction_following"] is None
    assert loaded["scores"][0]["overall_fit_for_role"] is None
    assert "reviewer_notes" in loaded["scores"][0]


def test_scorecard_scaffold_scores_does_not_overwrite_without_force(tmp_path: Path) -> None:
    write_fake_scorecard_response(tmp_path, "qwen3-coder-30b", "developer_agent")
    result = scaffold_local_model_scorecard_scores(tmp_path)
    result.scores_path.write_text("keep: true\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Use --force"):
        scaffold_local_model_scorecard_scores(tmp_path)

    assert result.scores_path.read_text(encoding="utf-8") == "keep: true\n"


def test_scorecard_scaffold_scores_force_overwrites_existing_scores(tmp_path: Path) -> None:
    write_fake_scorecard_response(tmp_path, "qwen3-coder-30b", "developer_agent")
    result = scaffold_local_model_scorecard_scores(tmp_path)
    result.scores_path.write_text("keep: true\n", encoding="utf-8")

    scaffold_local_model_scorecard_scores(tmp_path, force=True)

    assert "qwen3-coder-30b" in result.scores_path.read_text(encoding="utf-8")


def test_scorecard_recommend_does_not_claim_winner_without_complete_scores(
    tmp_path: Path,
) -> None:
    write_scorecard_scores(
        tmp_path,
        [
            {
                "model_label": "qwen3-coder-30b",
                "role": "developer_agent",
                "response_file": ".agentic/local_model_scorecard/results/qwen/developer.md",
                "instruction_following": None,
                "correctness": None,
                "hallucination_control": None,
                "code_quality": None,
                "test_quality": None,
                "safety_compliance": None,
                "clarity": None,
                "overall_fit_for_role": None,
                "speed_notes": "",
                "reviewer_notes": "",
            },
        ],
    )

    result = recommend_local_model_roles(tmp_path)

    assert result.recommendations == {}
    assert len(result.incomplete_entries) == 1
    report = result.markdown_report_path.read_text(encoding="utf-8")
    assert "No complete scores are available. No role winner is claimed." in report
    assert "qwen3-coder-30b" in report


def test_scorecard_recommend_creates_reports_from_complete_scores(tmp_path: Path) -> None:
    write_scorecard_scores(
        tmp_path,
        [
            complete_score_entry("qwen3-coder-30b", "developer_agent", 5),
            complete_score_entry("gemma-4-26b", "developer_agent", 4),
        ],
    )

    result = recommend_local_model_roles(tmp_path)

    assert result.markdown_report_path == (
        tmp_path.resolve() / "reports" / "local_model_role_recommendations.md"
    )
    assert result.yaml_report_path == (
        tmp_path.resolve() / "reports" / "local_model_role_recommendations.yaml"
    )
    assert result.recommendations["developer_agent"]["best_model"]["model_label"] == (
        "qwen3-coder-30b"
    )
    assert result.recommendations["developer_agent"]["runner_up"]["model_label"] == (
        "gemma-4-26b"
    )
    report = result.markdown_report_path.read_text(encoding="utf-8")
    assert "Best model: `qwen3-coder-30b`" in report
    assert "Runner-up: `gemma-4-26b`" in report
    assert "human owner controls runtime assignment" in report


def test_scorecard_recommend_uses_overall_fit_first(tmp_path: Path) -> None:
    write_scorecard_scores(
        tmp_path,
        [
            complete_score_entry(
                "safe-runner-up",
                "reviewer_agent",
                4,
                safety_compliance=5,
                hallucination_control=5,
                correctness=5,
                instruction_following=5,
            ),
            complete_score_entry(
                "overall-fit-winner",
                "reviewer_agent",
                5,
                safety_compliance=1,
                hallucination_control=1,
                correctness=1,
                instruction_following=1,
            ),
        ],
    )

    result = recommend_local_model_roles(tmp_path)

    assert result.recommendations["reviewer_agent"]["best_model"]["model_label"] == (
        "overall-fit-winner"
    )


def test_scorecard_recommend_uses_tie_breakers_in_order(tmp_path: Path) -> None:
    write_scorecard_scores(
        tmp_path,
        [
            complete_score_entry(
                "safety-winner",
                "maintenance_agent",
                4,
                safety_compliance=5,
                hallucination_control=1,
                correctness=1,
                instruction_following=1,
            ),
            complete_score_entry(
                "hallucination-runner-up",
                "maintenance_agent",
                4,
                safety_compliance=4,
                hallucination_control=5,
                correctness=5,
                instruction_following=5,
            ),
            complete_score_entry(
                "correctness-third",
                "maintenance_agent",
                4,
                safety_compliance=4,
                hallucination_control=4,
                correctness=5,
                instruction_following=5,
            ),
        ],
    )

    result = recommend_local_model_roles(tmp_path)

    assert result.recommendations["maintenance_agent"]["best_model"]["model_label"] == (
        "safety-winner"
    )
    assert result.recommendations["maintenance_agent"]["runner_up"]["model_label"] == (
        "hallucination-runner-up"
    )


def test_scorecard_recommend_reports_incomplete_entries(tmp_path: Path) -> None:
    write_scorecard_scores(
        tmp_path,
        [
            complete_score_entry("devstral-small-2", "test_agent", 4),
            {
                **complete_score_entry("gemma-4-26b", "test_agent", 5),
                "safety_compliance": None,
            },
        ],
    )

    result = recommend_local_model_roles(tmp_path)

    assert len(result.incomplete_entries) == 1
    assert result.recommendations["test_agent"]["best_model"]["model_label"] == (
        "devstral-small-2"
    )
    report = result.markdown_report_path.read_text(encoding="utf-8")
    assert "`gemma-4-26b` / `test_agent` ignored" in report
    assert "safety_compliance must be a number from 1 to 5" in report


def test_cli_scorecard_scaffold_scores_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_scorecard_response(tmp_path, "qwen3-coder-30b", "developer_agent")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "local-model", "scorecard-scaffold-scores"])

    main()

    captured = capsys.readouterr()
    assert "Local model scorecard scores scaffold created." in captured.out
    assert (tmp_path / ".agentic" / "local_model_scorecard" / "scorecard_scores.yaml").exists()


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
    assert "docs/local_model_role_assignment.md" in readme
    assert "agentic local-model scorecard-create" in readme
    assert "agentic local-model scorecard-scaffold-scores" in readme
    assert "agentic local-model scorecard-recommend" in readme


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
        "scorecard-scaffold-scores",
        "scorecard-recommend",
        "docs/local_model_role_assignment.md",
        "plain ASCII",
        "requested headings exactly",
    ]

    for phrase in required_phrases:
        assert phrase in guide


def test_local_model_role_assignment_doc_exists_and_mentions_models_roles_and_safety() -> None:
    guide = Path("docs/local_model_role_assignment.md").read_text(encoding="utf-8")

    required_phrases = [
        "Qwen3 Coder",
        "Devstral",
        "Gemma",
        "Qwen2.5 Coder",
        "role assignment",
        "developer_agent",
        "test_agent",
        "docs_agent",
        "reviewer_agent",
        "maintenance_agent",
        "overall_fit_for_role",
        "safety_compliance",
        "High-risk DeFi",
        "cloud models",
        "human owner controls runtime assignment",
    ]

    for phrase in required_phrases:
        assert phrase in guide


def test_local_model_score_files_and_recommendation_reports_are_gitignored() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    required_patterns = [
        ".agentic/local_model_scorecard/results/",
        ".agentic/local_model_scorecard/scorecard_scores.yaml",
        "reports/local_model_role_recommendations.md",
        "reports/local_model_role_recommendations.yaml",
    ]

    for pattern in required_patterns:
        assert pattern in gitignore
