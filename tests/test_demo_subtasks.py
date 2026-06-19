from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.demo_subtasks import (
    DEMO_STORY,
    DEPENDENCY_FAILURE_SCENARIO,
    FAKE_MODE,
    FakeDemoLocalModelHttpClient,
    LOCAL_MODE,
    RESUME_SCENARIO,
    SUCCESS_SCENARIO,
    materialize_demo_project,
    run_demo_subtasks,
)
from agentic_dev.local_execution import run_local_execution


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_demo_subtasks_success_fake_mode_creates_and_cleans_sandbox(tmp_path: Path) -> None:
    result = run_demo_subtasks(tmp_path, mode=FAKE_MODE, scenario=SUCCESS_SCENARIO)

    assert result.exit_code == 0
    assert result.status == "completed"
    assert result.validation is not None
    assert result.validation.passed is True
    assert result.fake_call_count == 4
    assert not result.sandbox_path.exists()


def test_demo_subtasks_keep_workspace_preserves_state_and_generated_files(tmp_path: Path) -> None:
    result = run_demo_subtasks(
        tmp_path,
        mode=FAKE_MODE,
        scenario=SUCCESS_SCENARIO,
        keep_workspace=True,
    )

    assert result.exit_code == 0
    assert result.sandbox_path.exists()
    state = read_yaml(result.sandbox_path / "stories" / DEMO_STORY / "reports" / "local_execution" / "state.yaml")
    assert state["completed_tasks"] == [
        "calculator-module",
        "calculator-tests",
        "calculator-cli",
        "validation-report",
    ]
    assert (result.sandbox_path / "calculator" / "core.py").exists()
    assert (result.sandbox_path / "tests" / "test_calculator.py").exists()


def test_demo_subtasks_oversized_blocks_before_fake_model_call(tmp_path: Path) -> None:
    result = run_demo_subtasks(tmp_path, mode=FAKE_MODE, scenario="oversized", keep_workspace=True)

    assert result.exit_code == 0
    assert result.status == "blocked"
    assert result.fake_call_count == 0
    state = read_yaml(result.sandbox_path / "stories" / DEMO_STORY / "reports" / "local_execution" / "state.yaml")
    assert state["tasks"]["calculator-module"]["status"] == "cloud_redecomposition_required"
    assert state["cloud_redecomposition_required_tasks"] == ["calculator-module"]
    assert not (result.sandbox_path / "calculator").exists()


def test_demo_subtasks_resume_skips_completed_tasks_and_reuses_handoffs(tmp_path: Path) -> None:
    result = run_demo_subtasks(tmp_path, mode=FAKE_MODE, scenario=RESUME_SCENARIO, keep_workspace=True)

    assert result.exit_code == 0
    assert result.first_pass_status == "blocked"
    assert result.status == "completed"
    state = read_yaml(result.sandbox_path / "stories" / DEMO_STORY / "reports" / "local_execution" / "state.yaml")
    assert state["tasks"]["calculator-module"]["attempt"] == 1
    assert state["tasks"]["calculator-tests"]["attempt"] == 2
    context = (
        result.sandbox_path
        / "stories"
        / DEMO_STORY
        / "reports"
        / "local_execution"
        / "tasks"
        / "calculator-tests"
        / "context.md"
    ).read_text(encoding="utf-8")
    assert "Completed calculator-module." in context


def test_demo_subtasks_dependency_failure_blocks_downstream_tasks(tmp_path: Path) -> None:
    result = run_demo_subtasks(
        tmp_path,
        mode=FAKE_MODE,
        scenario=DEPENDENCY_FAILURE_SCENARIO,
        keep_workspace=True,
    )

    assert result.exit_code == 0
    assert result.status == "blocked"
    state = read_yaml(result.sandbox_path / "stories" / DEMO_STORY / "reports" / "local_execution" / "state.yaml")
    assert state["tasks"]["calculator-module"]["status"] == "failed"
    assert state["tasks"]["calculator-tests"]["failure_type"] == "blocked_by_dependency"
    assert state["tasks"]["calculator-cli"]["failure_type"] == "blocked_by_dependency"


def test_demo_subtasks_local_mode_reports_runtime_unavailable_by_default(tmp_path: Path) -> None:
    result = run_demo_subtasks(tmp_path, mode=LOCAL_MODE, scenario=SUCCESS_SCENARIO)

    assert result.exit_code == 1
    assert result.runtime_guidance is not None
    assert "Ollama or LM Studio-compatible" in result.runtime_guidance


def test_demo_subtasks_workspace_root_must_stay_inside_safe_temp_roots(tmp_path: Path) -> None:
    unsafe_root = Path.cwd() / "unsafe-root"
    with pytest.raises(ValueError, match="safe temp root"):
        run_demo_subtasks(tmp_path, workspace_root=unsafe_root)


def test_demo_subtasks_sandbox_rejects_absolute_escape_without_partial_writes(tmp_path: Path) -> None:
    sandbox_root = tmp_path / "sandbox"
    materialize_demo_project(tmp_path, sandbox_root, mode=FAKE_MODE, scenario=SUCCESS_SCENARIO)
    client = FakeDemoLocalModelHttpClient(
        SUCCESS_SCENARIO,
        overrides={
            "calculator-module": yaml.safe_dump(
                {
                    "report": "bad\n",
                    "files": [
                        {"path": "calculator/good.py", "content": "good\n"},
                        {"path": "/escape.py", "content": "bad\n"},
                    ],
                },
                sort_keys=False,
            )
        },
    )

    result = run_local_execution(sandbox_root, DEMO_STORY, http_client=client)

    assert result.status == "blocked"
    assert not (sandbox_root / "calculator" / "good.py").exists()


def test_demo_subtasks_sandbox_rejects_symlink_escape_without_partial_writes(tmp_path: Path) -> None:
    sandbox_root = tmp_path / "sandbox"
    materialize_demo_project(tmp_path, sandbox_root, mode=FAKE_MODE, scenario=SUCCESS_SCENARIO)
    outside = tmp_path / "outside"
    outside.mkdir()
    calculator_path = sandbox_root / "calculator"
    calculator_path.mkdir(parents=True)
    try:
        (calculator_path / "linked").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    client = FakeDemoLocalModelHttpClient(
        SUCCESS_SCENARIO,
        overrides={
            "calculator-module": yaml.safe_dump(
                {
                    "report": "bad\n",
                    "files": [
                        {"path": "calculator/good.py", "content": "good\n"},
                        {"path": "calculator/linked/escape.py", "content": "bad\n"},
                    ],
                },
                sort_keys=False,
            )
        },
    )

    result = run_local_execution(sandbox_root, DEMO_STORY, http_client=client)

    assert result.status == "blocked"
    assert not (sandbox_root / "calculator" / "good.py").exists()
    assert not (outside / "escape.py").exists()


def test_demo_subtasks_cli_defaults_to_fake_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.argv", ["agentic", "demo-subtasks", "--project", str(tmp_path)])

    main()

    output = capsys.readouterr().out
    assert "Mode: fake" in output
    assert "Scenario: success" in output
    assert "Final result: exit_code=0" in output


def test_demo_subtasks_cli_explicit_local_mode_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "demo-subtasks",
            "--project",
            str(tmp_path),
            "--mode",
            "local",
            "--scenario",
            "success",
        ],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 1


def test_demo_subtasks_cli_invalid_workspace_root_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentic",
            "demo-subtasks",
            "--project",
            str(tmp_path),
            "--workspace-root",
            str(Path.cwd() / "unsafe-root"),
        ],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 1
