from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.local_execution import parse_execution_response, run_local_execution
from agentic_dev.runtime_config import default_runtime_config_text


STORY = "story_060"


class FakeLocalExecutionHttpClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
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
        if not self.responses:
            raise AssertionError("Unexpected local model call")
        return {"choices": [{"finish_reason": "stop", "message": {"content": self.responses.pop(0)}}]}


def write_runtime_config(
    project_path: Path,
    *,
    role_defaults: dict[str, str] | None = None,
    global_default_model: str | None = "gemma",
) -> None:
    config = yaml.safe_load(default_runtime_config_text())
    config["local_model_runtime"]["enabled"] = True
    config["local_execution"] = {
        "global_default_model": global_default_model,
        "role_defaults": (
            {
                "planner": "qwen3",
                "developer": "gemma",
            }
            if role_defaults is None
            else role_defaults
        ),
    }
    config_path = project_path / ".agentic" / "agent_runtime.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def create_story(project_path: Path) -> Path:
    story_path = project_path / "stories" / STORY
    (story_path / "reports").mkdir(parents=True)
    (story_path / "instructions").mkdir()
    (story_path / "story.md").write_text(
        """# Story 060

## Goal

Enable local execution.

## Why This Matters

Local models should execute assigned roles.

## Acceptance Criteria

- Execute roles in blueprint order.
- Save per-role outputs.
""",
        encoding="utf-8",
    )
    (story_path / "status.yaml").write_text(
        yaml.safe_dump({"story_id": STORY, "slug": "blueprint-local-execution", "status": "prepared"}, sort_keys=False),
        encoding="utf-8",
    )
    for name in ("planner_agent", "developer_agent", "docs_agent"):
        (story_path / "instructions" / f"{name}.md").write_text(
            f"# {name}\n\n## Role\n\nStay in role.\n",
            encoding="utf-8",
        )

    agent_plan = {
        "story": STORY,
        "status": "pending_execution",
        "execution_order": ["planner_agent", "developer_agent"],
        "assigned_agents": [
            {
                "id": "planner_agent",
                "role": "planner",
                "display_name": "Planner Agent",
                "responsibility": "Plan the work.",
                "instruction_file": "instructions/planner_agent.md",
                "expected_output": "reports/planner_report.md",
                "model": "qwen3-override",
                "writable_paths": ["stories/**/reports/**"],
            },
            {
                "id": "developer_agent",
                "role": "developer",
                "display_name": "Developer Agent",
                "responsibility": "Implement the work.",
                "instruction_file": "instructions/developer_agent.md",
                "expected_output": "reports/developer_report.md",
                "writable_paths": ["src/**", "stories/**/reports/**"],
            },
            {
                "id": "docs_agent",
                "role": "documentation",
                "display_name": "Docs Agent",
                "responsibility": "Update documentation.",
                "instruction_file": "instructions/docs_agent.md",
                "expected_output": "reports/docs_report.md",
                "model": "qwen/qwen3-coder-30b",
                "writable_paths": ["README.md", "docs/**", "stories/story_060/reports/**"],
            },
        ],
    }
    (story_path / "agent_plan.yaml").write_text(
        yaml.safe_dump(agent_plan, sort_keys=False),
        encoding="utf-8",
    )
    return story_path


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def create_symlink(target: Path, link: Path, *, target_is_directory: bool = False) -> None:
    try:
        os.symlink(target, link, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"symlink creation is unavailable: {error}")


def test_parse_execution_response_accepts_raw_yaml() -> None:
    parsed = parse_execution_response("report: |\n  ok\nfiles: []\n")

    assert parsed == {"report": "ok\n", "files": []}


def test_parse_execution_response_accepts_yaml_fence() -> None:
    parsed = parse_execution_response("```yaml\nreport: |\n  ok\nfiles: []\n```\n")

    assert parsed == {"report": "ok\n", "files": []}


def test_parse_execution_response_accepts_yml_fence() -> None:
    parsed = parse_execution_response("```yml\nreport: |\n  ok\nfiles: []\n```\n")

    assert parsed == {"report": "ok\n", "files": []}


def test_parse_execution_response_accepts_unlabelled_fence() -> None:
    parsed = parse_execution_response("```\nreport: |\n  ok\nfiles: []\n```\n")

    assert parsed == {"report": "ok\n", "files": []}


def test_parse_execution_response_rejects_malformed_fenced_yaml() -> None:
    with pytest.raises(ValueError, match="not valid YAML"):
        parse_execution_response("```yaml\nreport: |\n  ok\nfiles:\n  - path: README.md\n    content: [\n```\n")


def test_parse_execution_response_rejects_prose_before_fenced_yaml() -> None:
    with pytest.raises(ValueError, match="not valid YAML"):
        parse_execution_response("Here is the YAML:\n```yaml\nreport: |\n  ok\nfiles: []\n```\n")


def test_parse_execution_response_rejects_prose_after_fenced_yaml() -> None:
    with pytest.raises(
        ValueError,
        match="contained prose or extra content outside the outer YAML fence",
    ):
        parse_execution_response("```yaml\nreport: |\n  ok\nfiles: []\n```\nThanks.\n")


def test_parse_execution_response_preserves_internal_code_fence_in_block_scalar() -> None:
    parsed = parse_execution_response(
        "```yaml\nreport: |\n  Summary\nfiles:\n  - path: docs/example.md\n    content: |\n      ```python\n      print('ok')\n      ```\n```\n",
    )

    assert parsed["files"] == [
        {
            "path": "docs/example.md",
            "content": "```python\nprint('ok')\n```",
        }
    ]


def test_local_execute_dry_run_resolves_models_by_priority(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, role_defaults={"developer": "gemma-role"}, global_default_model="gemma-global")
    create_story(tmp_path)

    result = run_local_execution(tmp_path, STORY, dry_run=True)

    assert result.status == "dry_run"
    assert [(role.role, role.model, role.source) for role in result.roles] == [
        ("planner", "qwen3-override", "blueprint override"),
        ("developer", "gemma-role", "runtime role default"),
        ("documentation", "qwen/qwen3-coder-30b", "blueprint override"),
    ]


def test_local_execute_runs_in_order_and_writes_state_and_artifacts(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Planner report\nfiles: []\n",
            "report: |\n  Developer report\nfiles:\n  - path: src/app.py\n    content: |\n      print('ok')\n",
            "report: |\n  Docs report\nfiles:\n  - path: README.md\n    content: |\n      # Updated\n  - path: docs/guide.md\n    content: |\n      guide\n",
        ]
    )

    result = run_local_execution(tmp_path, STORY, http_client=client)

    assert result.status == "completed"
    assert [call["payload"]["model"] for call in client.calls] == [
        "qwen3-override",
        "gemma",
        "qwen/qwen3-coder-30b",
    ]
    assert "Role: planner" in client.calls[0]["payload"]["messages"][0]["content"]
    assert "Role: developer" in client.calls[1]["payload"]["messages"][0]["content"]
    assert "Role: documentation" in client.calls[2]["payload"]["messages"][0]["content"]
    assert (story_path / "reports" / "local_execution" / "planner" / "output.md").exists()
    assert (story_path / "reports" / "local_execution" / "developer" / "output.md").exists()
    assert (story_path / "reports" / "local_execution" / "documentation" / "output.md").exists()
    assert (story_path / "reports" / "planner_report.md").read_text(encoding="utf-8") == "Planner report\n"
    assert (story_path / "reports" / "developer_report.md").read_text(encoding="utf-8") == "Developer report\n"
    assert (story_path / "reports" / "docs_report.md").read_text(encoding="utf-8") == "Docs report\n"
    assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "print('ok')"
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "# Updated\n"
    assert (tmp_path / "docs" / "guide.md").read_text(encoding="utf-8") == "guide"

    state = read_yaml(story_path / "reports" / "local_execution" / "state.yaml")
    assert state["status"] == "completed"
    assert state["completed_roles"] == ["planner", "developer", "documentation"]
    planner_execution = read_yaml(story_path / "reports" / "local_execution" / "planner" / "execution.yaml")
    assert planner_execution["provider"] == "local"
    assert planner_execution["model"] == "qwen3-override"
    assert planner_execution["attempt"] == 1
    assert planner_execution["status"] == "completed"
    assert planner_execution["prompt_hash"]
    assert planner_execution["context_files"] == [f"stories/{STORY}/reports/role_context/planner_agent_context.md"]


def test_local_execute_records_missing_context_input_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)

    def skip_context_build(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr("agentic_dev.local_execution.build_role_context", skip_context_build)
    client = FakeLocalExecutionHttpClient([])

    result = run_local_execution(tmp_path, STORY, role="developer", http_client=client)

    assert result.status == "blocked"
    assert client.calls == []
    state = read_yaml(story_path / "reports" / "local_execution" / "state.yaml")
    assert state["status"] == "blocked"
    assert state["status"] != "running"
    execution = read_yaml(story_path / "reports" / "local_execution" / "developer" / "execution.yaml")
    assert execution["status"] == "blocked"
    assert execution["failure_type"] == "context_preparation_error"
    assert "developer_agent_context.md" in execution["summary"]


def test_local_execute_records_context_building_failure_and_resume_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)

    def fail_context_build(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("context builder unavailable")

    monkeypatch.setattr("agentic_dev.local_execution.build_role_context", fail_context_build)
    first_result = run_local_execution(tmp_path, STORY, role="developer", http_client=FakeLocalExecutionHttpClient([]))

    assert first_result.status == "blocked"
    first_state = read_yaml(story_path / "reports" / "local_execution" / "state.yaml")
    assert first_state["status"] == "blocked"
    assert first_state["blocked_roles"] == ["developer"]
    first_execution = read_yaml(story_path / "reports" / "local_execution" / "developer" / "execution.yaml")
    assert first_execution["attempt"] == 1
    assert first_execution["failure_type"] == "context_preparation_error"
    assert "context builder unavailable" in first_execution["summary"]

    monkeypatch.undo()
    second_client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Developer report\nfiles:\n  - path: src/app.py\n    content: |\n      print('resume')\n",
        ]
    )
    second_result = run_local_execution(tmp_path, STORY, role="developer", resume=True, http_client=second_client)

    assert second_result.status == "completed"
    assert len(second_client.calls) == 1
    final_state = read_yaml(story_path / "reports" / "local_execution" / "state.yaml")
    assert final_state["status"] == "completed"
    assert final_state["blocked_roles"] == []
    final_execution = read_yaml(story_path / "reports" / "local_execution" / "developer" / "execution.yaml")
    assert final_execution["attempt"] == 2
    assert final_execution["status"] == "completed"


def test_local_execute_resume_skips_completed_roles(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    first_client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Planner report\nfiles: []\n",
            "not: valid: yaml\n",
        ]
    )

    first_result = run_local_execution(tmp_path, STORY, http_client=first_client)

    assert first_result.status == "blocked"
    first_state = read_yaml(story_path / "reports" / "local_execution" / "state.yaml")
    assert first_state["completed_roles"] == ["planner"]
    assert first_state["blocked_roles"] == ["developer"]

    second_client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Developer report\nfiles:\n  - path: src/app.py\n    content: |\n      print('resume')\n",
            "report: |\n  Docs report\nfiles:\n  - path: README.md\n    content: |\n      resumed\n",
        ]
    )
    second_result = run_local_execution(tmp_path, STORY, resume=True, http_client=second_client)

    assert second_result.status == "completed"
    assert len(second_client.calls) == 2
    assert second_client.calls[0]["payload"]["model"] == "gemma"
    assert second_client.calls[1]["payload"]["model"] == "qwen/qwen3-coder-30b"
    final_state = read_yaml(story_path / "reports" / "local_execution" / "state.yaml")
    assert final_state["completed_roles"] == ["planner", "developer", "documentation"]
    assert final_state["blocked_roles"] == []
    assert read_yaml(story_path / "reports" / "local_execution" / "developer" / "execution.yaml")["attempt"] == 2


def test_local_execute_blocks_unauthorized_writes_and_preserves_evidence(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Planner report\nfiles: []\n",
            "report: |\n  Developer report\nfiles:\n  - path: README.md\n    content: |\n      bad\n",
        ]
    )

    result = run_local_execution(tmp_path, STORY, http_client=client)

    assert result.status == "blocked"
    execution = read_yaml(story_path / "reports" / "local_execution" / "developer" / "execution.yaml")
    assert execution["failure_type"] == "file_boundary_violation"
    assert "README.md" in execution["unauthorized_paths"]
    assert (story_path / "reports" / "local_execution" / "developer" / "output.md").exists()
    assert not (tmp_path / "README.md").exists()


def test_local_execute_docs_agent_allows_readme_and_docs_writes(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Docs report\nfiles:\n  - path: README.md\n    content: |\n      docs readme\n  - path: docs/code_tour.md\n    content: |\n      code tour\n",
        ]
    )

    result = run_local_execution(tmp_path, STORY, role="documentation", http_client=client)

    assert result.status == "completed"
    execution = read_yaml(story_path / "reports" / "local_execution" / "documentation" / "execution.yaml")
    assert execution["status"] == "completed"
    assert execution["failure_type"] is None
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "docs readme\n"
    assert (tmp_path / "docs" / "code_tour.md").read_text(encoding="utf-8") == "code tour"


def test_local_execute_allows_normal_resolved_writable_path(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    create_story(tmp_path)
    client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Developer report\nfiles:\n  - path: src/app.py\n    content: |\n      print('ok')\n",
        ]
    )

    result = run_local_execution(tmp_path, STORY, role="developer", http_client=client)

    assert result.status == "completed"
    assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "print('ok')"


def test_local_execute_blocks_allowed_directory_symlink_escape(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}_outside"
    outside.mkdir()
    src_path = tmp_path / "src"
    src_path.mkdir()
    create_symlink(outside, src_path / "linked", target_is_directory=True)
    client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Developer report\nfiles:\n  - path: src/linked/escape.py\n    content: |\n      escaped\n",
        ]
    )

    result = run_local_execution(tmp_path, STORY, role="developer", http_client=client)

    assert result.status == "blocked"
    execution = read_yaml(story_path / "reports" / "local_execution" / "developer" / "execution.yaml")
    assert execution["failure_type"] == "file_boundary_violation"
    assert "escapes project root" in execution["summary"]
    assert not (outside / "escape.py").exists()


def test_local_execute_blocks_direct_symlink_file_target(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}_outside.py"
    outside.write_text("original\n", encoding="utf-8")
    src_path = tmp_path / "src"
    src_path.mkdir()
    create_symlink(outside, src_path / "linked.py")
    client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Developer report\nfiles:\n  - path: src/linked.py\n    content: |\n      escaped\n",
        ]
    )

    result = run_local_execution(tmp_path, STORY, role="developer", http_client=client)

    assert result.status == "blocked"
    execution = read_yaml(story_path / "reports" / "local_execution" / "developer" / "execution.yaml")
    assert execution["failure_type"] == "file_boundary_violation"
    assert outside.read_text(encoding="utf-8") == "original\n"


def test_local_execute_blocks_multi_file_symlink_escape_without_partial_writes(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}_outside.py"
    outside.write_text("original\n", encoding="utf-8")
    src_path = tmp_path / "src"
    src_path.mkdir()
    create_symlink(outside, src_path / "linked.py")
    client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Developer report\nfiles:\n  - path: src/good.py\n    content: |\n      good\n  - path: src/linked.py\n    content: |\n      escaped\n",
        ]
    )

    result = run_local_execution(tmp_path, STORY, role="developer", http_client=client)

    assert result.status == "blocked"
    execution = read_yaml(story_path / "reports" / "local_execution" / "developer" / "execution.yaml")
    assert execution["failure_type"] == "file_boundary_violation"
    assert not (tmp_path / "src" / "good.py").exists()
    assert not (story_path / "reports" / "developer_report.md").exists()
    assert outside.read_text(encoding="utf-8") == "original\n"


def test_local_execute_docs_agent_blocks_src_and_tests_writes(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    client = FakeLocalExecutionHttpClient(
        [
            "report: |\n  Docs report\nfiles:\n  - path: src/unsafe.py\n    content: |\n      bad\n  - path: tests/test_unsafe.py\n    content: |\n      bad\n",
        ]
    )

    result = run_local_execution(tmp_path, STORY, role="documentation", http_client=client)

    assert result.status == "blocked"
    execution = read_yaml(story_path / "reports" / "local_execution" / "documentation" / "execution.yaml")
    assert execution["failure_type"] == "file_boundary_violation"
    assert execution["unauthorized_paths"] == ["src/unsafe.py", "tests/test_unsafe.py"]
    assert not (tmp_path / "src" / "unsafe.py").exists()
    assert not (tmp_path / "tests" / "test_unsafe.py").exists()


def test_local_execute_classifies_fenced_yaml_parse_failure_as_malformed_response(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    response_text = "```yaml\nreport: |\n  Broken\nfiles:\n  - path: README.md\n    content: [\n```\n"
    client = FakeLocalExecutionHttpClient([response_text])

    result = run_local_execution(tmp_path, STORY, role="documentation", http_client=client)

    assert result.status == "blocked"
    execution = read_yaml(story_path / "reports" / "local_execution" / "documentation" / "execution.yaml")
    assert execution["failure_type"] == "malformed_response"
    assert "not valid YAML" in execution["summary"]
    assert (story_path / "reports" / "local_execution" / "documentation" / "output.md").read_text(
        encoding="utf-8",
    ) == response_text


def test_local_execute_does_not_fall_back_to_codex_when_model_is_unresolved(tmp_path: Path) -> None:
    write_runtime_config(tmp_path, role_defaults={}, global_default_model=None)
    story_path = create_story(tmp_path)
    agent_plan = read_yaml(story_path / "agent_plan.yaml")
    del agent_plan["assigned_agents"][0]["model"]
    (story_path / "agent_plan.yaml").write_text(yaml.safe_dump(agent_plan, sort_keys=False), encoding="utf-8")

    result = run_local_execution(tmp_path, STORY, role="developer", http_client=FakeLocalExecutionHttpClient([]))

    assert result.status == "blocked"
    execution = read_yaml(story_path / "reports" / "local_execution" / "state.yaml")
    assert execution["blocked_roles"] == ["developer"]
    assert execution["executions"]["developer"]["failure_type"] == "unresolved_model"


def test_local_execute_reports_runtime_disabled_when_local_runtime_is_disabled(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    config = yaml.safe_load((tmp_path / ".agentic" / "agent_runtime.yaml").read_text(encoding="utf-8"))
    config["local_model_runtime"]["enabled"] = False
    (tmp_path / ".agentic" / "agent_runtime.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
    )

    result = run_local_execution(tmp_path, STORY, role="documentation", http_client=FakeLocalExecutionHttpClient([]))

    assert result.status == "blocked"
    execution = read_yaml(story_path / "reports" / "local_execution" / "documentation" / "execution.yaml")
    assert execution["failure_type"] == "runtime_disabled"


def test_local_execute_reports_configuration_error_for_invalid_runtime_config(tmp_path: Path) -> None:
    write_runtime_config(tmp_path)
    story_path = create_story(tmp_path)
    config = yaml.safe_load((tmp_path / ".agentic" / "agent_runtime.yaml").read_text(encoding="utf-8"))
    config["local_model_runtime"]["timeout_seconds"] = "bad"
    (tmp_path / ".agentic" / "agent_runtime.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
    )

    result = run_local_execution(tmp_path, STORY, role="documentation", http_client=FakeLocalExecutionHttpClient([]))

    assert result.status == "blocked"
    execution = read_yaml(story_path / "reports" / "local_execution" / "documentation" / "execution.yaml")
    assert execution["failure_type"] == "configuration_error"


def test_cli_local_execute_dry_run_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_runtime_config(tmp_path)
    create_story(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "local-execute", "--story", STORY, "--dry-run"])

    main()

    output = capsys.readouterr().out
    assert f"Local execution for {STORY}:" in output
    assert "planner: qwen3-override (blueprint override)" in output
    assert "developer: gemma (runtime role default)" in output
    assert "documentation: qwen/qwen3-coder-30b (blueprint override)" in output
