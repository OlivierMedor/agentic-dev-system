from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.local_repair_loop import (
    RepairFailureKind,
    RepairOwner,
    build_repair_prompt,
    build_repair_prompt_inputs,
    classify_pytest_failure,
    classify_ruff_failure,
    run_local_repair_loop,
    validate_repair_output,
    validate_target_path,
)


def create_story_workspace(tmp_path: Path, story: str = "story_069_local_repair_loop_orchestrator") -> Path:
    story_path = tmp_path / "stories" / story
    story_path.mkdir(parents=True)
    (story_path / "story.md").write_text(
        "\n".join(
            [
                "# Story 069",
                "",
                "## Goal",
                "",
                "Automate the local repair loop.",
                "",
                "## Acceptance Criteria",
                "",
                "- Build a local repair loop orchestrator.",
                "- Preserve the local-only Qwen repair path.",
                "- Keep cloud escalation manual-only.",
                "",
            ],
        ),
        encoding="utf-8",
    )
    (story_path / "status.yaml").write_text("status: in_progress\n", encoding="utf-8")
    (story_path / "test_plan.yaml").write_text("unit_tests: true\n", encoding="utf-8")
    (story_path / "monitoring_plan.yaml").write_text("watch_for:\n  - retry_budget_exhausted\n", encoding="utf-8")
    return story_path


def write_python_target(tmp_path: Path, content: str = "def keep_api():\n    return 1\n") -> Path:
    target = tmp_path / "src" / "example.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def test_validate_repair_output_rejects_empty_output(tmp_path: Path) -> None:
    target = write_python_target(tmp_path)

    result = validate_repair_output(
        "",
        target_path=target,
        required_api_strings=(),
        strict_python=True,
    )

    assert result.passed is False
    assert result.failure_kind == RepairFailureKind.EMPTY_LOCAL_OUTPUT
    assert result.owner == RepairOwner.DEVELOPER


def test_validate_repair_output_rejects_python_fence_when_strict(tmp_path: Path) -> None:
    target = write_python_target(tmp_path)

    result = validate_repair_output(
        "```python\nprint('hello')\n```",
        target_path=target,
        required_api_strings=(),
        strict_python=True,
    )

    assert result.passed is False
    assert result.failure_kind == RepairFailureKind.MARKDOWN_FENCE_IN_STRICT_PYTHON


def test_validate_repair_output_strips_fence_when_non_strict(tmp_path: Path) -> None:
    target = tmp_path / "reports" / "notes.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old content", encoding="utf-8")

    result = validate_repair_output(
        "```markdown\nupdated content\n```",
        target_path=target,
        required_api_strings=(),
        strict_python=False,
    )

    assert result.passed is True
    assert result.stripped_code_fence is True
    assert result.normalized_output == "updated content"


def test_validate_repair_output_requires_public_api_strings(tmp_path: Path) -> None:
    target = write_python_target(tmp_path)

    result = validate_repair_output(
        "def keep_api():\n    return 2\n",
        target_path=target,
        required_api_strings=("keep_api", "ImportantType"),
        strict_python=True,
    )

    assert result.passed is False
    assert result.failure_kind == RepairFailureKind.MISSING_REQUIRED_API
    assert "ImportantType" in result.reason


def test_validate_target_path_rejects_escape_attempt(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Target path must stay inside the project"):
        validate_target_path(tmp_path, Path("..") / "escape.py")


def test_classify_ruff_failure_routes_source_failure_to_developer(tmp_path: Path) -> None:
    target = write_python_target(tmp_path)

    classification = classify_ruff_failure("src/example.py:1:1: F401 unused import", target_path=target)

    assert classification.kind == RepairFailureKind.RUFF_FAILURE
    assert classification.owner == RepairOwner.DEVELOPER


def test_classify_pytest_failure_routes_fixture_failure_to_test_owner(tmp_path: Path) -> None:
    target = write_python_target(tmp_path)

    classification = classify_pytest_failure("fixture 'db' not found", target_path=target)

    assert classification.kind == RepairFailureKind.PYTEST_FAILURE
    assert classification.owner == RepairOwner.TEST


def test_build_repair_prompt_includes_story_contract_failure_and_policy(tmp_path: Path) -> None:
    target = write_python_target(tmp_path)
    inputs = build_repair_prompt_inputs(
        story="story_069_local_repair_loop_orchestrator",
        story_contract="## story.md\n\nAcceptance criteria",
        target_path=target,
        current_file_content="def keep_api():\n    return 1\n",
        failure_output="ruff check failed",
        required_api_strings=("keep_api", "FundingVenue"),
        owner=RepairOwner.DEVELOPER,
        failure_kind=RepairFailureKind.RUFF_FAILURE,
        strict_python=True,
    )

    prompt = build_repair_prompt(inputs)

    assert "story_069_local_repair_loop_orchestrator" in prompt
    assert "def keep_api()" in prompt
    assert "ruff check failed" in prompt
    assert "keep_api" in prompt
    assert "FundingVenue" in prompt
    assert "Return the complete corrected file only." in prompt
    assert "Do not add network calls." in prompt
    assert "Do not add trading, wallet, private key, signing, or deployment logic." in prompt


def test_dry_run_writes_prompt_and_plan_but_does_not_modify_target(tmp_path: Path) -> None:
    create_story_workspace(tmp_path)
    target = write_python_target(tmp_path, "def keep_api():\n    return 1\n")

    result = run_local_repair_loop(
        tmp_path,
        "story_069_local_repair_loop_orchestrator",
        target,
        failure_output=None,
        required_api=("keep_api",),
        execute=False,
    )

    assert result.status == "dry_run"
    assert target.read_text(encoding="utf-8") == "def keep_api():\n    return 1\n"
    assert result.prompt_path.exists()
    assert result.plan_path.exists()
    assert result.result_path.exists()
    plan = yaml.safe_load(result.plan_path.read_text(encoding="utf-8"))
    assert plan["cloud_policy"] == "manual-only"
    assert plan["codex_policy"] == "disabled-by-default"


def test_execute_mode_applies_accepted_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    create_story_workspace(tmp_path)
    target = write_python_target(tmp_path, "def keep_api():\n    return 1\n")

    monkeypatch.setattr(
        "agentic_dev.local_repair_loop.invoke_local_repair_model",
        lambda project_path, prompt_text, http_client=None: "def keep_api():\n    return 2\n",
    )

    def fake_command_runner(command: list[str], cwd: Path):
        return type(
            "Result",
            (),
            {
                "command": " ".join(command),
                "returncode": 0,
                "stdout": "ok\n",
                "stderr": "",
                "passed": True,
            },
        )()

    result = run_local_repair_loop(
        tmp_path,
        "story_069_local_repair_loop_orchestrator",
        target,
        required_api=("keep_api",),
        execute=True,
        max_local_attempts=1,
        command_runner=fake_command_runner,
    )

    assert result.status == "completed"
    assert result.applied is True
    assert target.read_text(encoding="utf-8") == "def keep_api():\n    return 2"
    assert len(result.attempts) == 1
    assert result.attempts[0].validation_result.passed is True
    assert result.attempts[0].retry_budget_status == "within_budget"
    assert result.attempts[0].codex_used is False
    assert result.attempts[0].cloud_attempt_count == 0


def test_rejected_output_is_not_applied_and_writes_manual_support_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_story_workspace(tmp_path)
    target = write_python_target(tmp_path, "def keep_api():\n    return 1\n")

    monkeypatch.setattr(
        "agentic_dev.local_repair_loop.invoke_local_repair_model",
        lambda project_path, prompt_text, http_client=None: "```python\nprint('bad')\n```",
    )

    result = run_local_repair_loop(
        tmp_path,
        "story_069_local_repair_loop_orchestrator",
        target,
        required_api=("keep_api",),
        execute=True,
        max_local_attempts=1,
    )

    assert result.status == "budget_exceeded"
    assert result.applied is False
    assert target.read_text(encoding="utf-8") == "def keep_api():\n    return 1\n"
    assert result.manual_support_report_path is not None
    assert result.manual_support_report_path.exists()
    report = yaml.safe_load(result.manual_support_report_path.read_text(encoding="utf-8"))
    assert report["cloud_attempt_count"] == 0
    assert report["codex_used"] is False
    assert report["retry_budget_status"] == "exhausted"


def test_retry_budget_exceeded_creates_manual_support_report_and_does_not_call_cloud(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_story_workspace(tmp_path)
    target = write_python_target(tmp_path, "def keep_api():\n    return 1\n")

    monkeypatch.setattr(
        "agentic_dev.local_repair_loop.invoke_local_repair_model",
        lambda project_path, prompt_text, http_client=None: "missing api string",
    )

    result = run_local_repair_loop(
        tmp_path,
        "story_069_local_repair_loop_orchestrator",
        target,
        required_api=("keep_api",),
        execute=True,
        max_local_attempts=1,
    )

    assert result.status == "budget_exceeded"
    assert result.classification.kind == RepairFailureKind.RETRY_BUDGET_EXCEEDED
    assert result.classification.owner == RepairOwner.MANUAL_SUPPORT
    assert result.manual_support_report_path is not None
    assert result.manual_support_report_path.exists()


def test_cli_local_repair_loop_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    create_story_workspace(tmp_path)
    target = write_python_target(tmp_path)

    def fake_run_local_repair_loop(*args, **kwargs):
        assert args[0] == Path.cwd()
        assert args[1] == "story_069_local_repair_loop_orchestrator"
        assert args[2] == Path("src/example.py")
        assert kwargs["execute"] is False
        return type(
            "Result",
            (),
            {
                "terminal_summary": "Local repair loop for story_069_local_repair_loop_orchestrator:",
            },
        )()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("agentic_dev.cli.run_local_repair_loop", fake_run_local_repair_loop)
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "local-repair-loop",
            "--story",
            "story_069_local_repair_loop_orchestrator",
            "--target",
            "src/example.py",
        ],
    )

    main()

    captured = capsys.readouterr()
    assert "Local repair loop for story_069_local_repair_loop_orchestrator:" in captured.out
    assert target.read_text(encoding="utf-8") == "def keep_api():\n    return 1\n"
