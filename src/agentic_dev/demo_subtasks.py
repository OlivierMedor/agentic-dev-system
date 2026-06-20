from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentic_dev.local_execution import LocalExecutionResult, run_local_execution
from agentic_dev.local_model_runtime import LocalModelHttpClient
from agentic_dev.runtime_config import default_runtime_config_text, load_runtime_config


DEMO_STORY = "demo_subtasks"
FAKE_MODE = "fake"
LOCAL_MODE = "local"
DEMO_MODES = {FAKE_MODE, LOCAL_MODE}
SUCCESS_SCENARIO = "success"
OVERSIZED_SCENARIO = "oversized"
RESUME_SCENARIO = "resume"
DEPENDENCY_FAILURE_SCENARIO = "dependency-failure"
DEMO_SCENARIOS = {
    SUCCESS_SCENARIO,
    OVERSIZED_SCENARIO,
    RESUME_SCENARIO,
    DEPENDENCY_FAILURE_SCENARIO,
}
SAFE_TEMP_ROOTS = {
    Path(tempfile.gettempdir()).resolve(),
    Path("C:/tmp").resolve(),
}
TASK_SEQUENCE = [
    "calculator-module",
    "calculator-tests",
    "calculator-cli",
    "validation-report",
]


class FakeDemoStop(RuntimeError):
    """Intentional fake-mode interruption used to demonstrate resume."""


@dataclass(frozen=True)
class DemoValidationResult:
    pytest_passed: bool
    cli_passed: bool
    pytest_output: str
    cli_output: str
    validation_path: Path

    @property
    def passed(self) -> bool:
        return self.pytest_passed and self.cli_passed


@dataclass(frozen=True)
class DemoSubtasksResult:
    mode: str
    scenario: str
    sandbox_path: Path
    status: str
    local_execution: LocalExecutionResult
    cleanup_result: str
    preserved_workspace: bool
    fake_call_count: int
    validation: DemoValidationResult | None
    runtime_guidance: str | None = None
    first_pass_status: str | None = None

    @property
    def exit_code(self) -> int:
        if self.mode == LOCAL_MODE and self.runtime_guidance is not None:
            return 1
        if self.scenario == SUCCESS_SCENARIO:
            return 0 if self.validation is not None and self.validation.passed else 1
        if self.scenario == RESUME_SCENARIO:
            return 0 if self.validation is not None and self.validation.passed else 1
        if self.scenario == OVERSIZED_SCENARIO:
            return 0 if self.status == "blocked" else 1
        if self.scenario == DEPENDENCY_FAILURE_SCENARIO:
            return 0 if self.status == "blocked" else 1
        return 1

    @property
    def terminal_summary(self) -> str:
        lines = [
            "Demo subtasks:",
            f"Mode: {self.mode}",
            f"Scenario: {self.scenario}",
            f"Sandbox: {self.sandbox_path}",
        ]
        if self.first_pass_status is not None:
            lines.append(f"Resume first pass: {self.first_pass_status}")
        for task in self.local_execution.subtasks or []:
            lines.append(
                "Task: "
                f"{task.task_id}; role={task.role}; model={task.model or 'UNRESOLVED'}; "
                f"state={task.status}; context={task.estimated_input_tokens or 'unknown'}/"
                f"{task.usable_input_tokens or 'unknown'}",
            )
        lines.append(f"Execution state: {self.status}")
        lines.append(f"Fake adapter calls: {self.fake_call_count}")
        if self.validation is not None:
            lines.append(
                "Validation: "
                f"pytest={'passed' if self.validation.pytest_passed else 'failed'}; "
                f"cli={'passed' if self.validation.cli_passed else 'failed'}",
            )
        if self.runtime_guidance is not None:
            lines.append(f"Runtime guidance: {self.runtime_guidance}")
        lines.append(f"Cleanup: {self.cleanup_result}")
        lines.append(f"Final result: exit_code={self.exit_code}")
        return "\n".join(lines)


class FakeDemoLocalModelHttpClient(LocalModelHttpClient):
    def __init__(
        self,
        scenario: str,
        *,
        stop_after_task: str | None = None,
        overrides: dict[str, str | Exception] | None = None,
    ) -> None:
        self.scenario = scenario
        self.stop_after_task = stop_after_task
        self.overrides = overrides or {}
        self.calls: list[dict[str, Any]] = []

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        prompt = extract_prompt_text(payload)
        task_id = extract_task_id(prompt)
        call_index = len(self.calls) + 1
        self.calls.append(
            {
                "url": url,
                "model": payload.get("model"),
                "timeout_seconds": timeout_seconds,
                "task_id": task_id,
            },
        )
        if task_id in self.overrides:
            override = self.overrides[task_id]
            if isinstance(override, Exception):
                raise override
            return fake_http_response(override)
        if self.stop_after_task == task_id:
            raise FakeDemoStop(f"Intentional stop after {task_id}")
        if self.scenario == SUCCESS_SCENARIO:
            return fake_http_response(success_response(task_id, call_index))
        if self.scenario == RESUME_SCENARIO:
            return fake_http_response(success_response(task_id, call_index))
        if self.scenario == DEPENDENCY_FAILURE_SCENARIO:
            if task_id == "calculator-module":
                return fake_http_response("report: broken\nfiles:\n  - path: [\n")
            raise AssertionError(f"Unexpected dependency-failure task call: {task_id}")
        raise AssertionError(f"Unexpected fake scenario model call: {self.scenario}")


def run_demo_subtasks(
    project_path: Path,
    *,
    mode: str = FAKE_MODE,
    scenario: str = SUCCESS_SCENARIO,
    keep_workspace: bool = False,
    workspace_root: Path | None = None,
    http_client: LocalModelHttpClient | None = None,
) -> DemoSubtasksResult:
    if mode not in DEMO_MODES:
        raise ValueError(f"Unsupported demo mode: {mode}")
    if scenario not in DEMO_SCENARIOS:
        raise ValueError(f"Unsupported demo scenario: {scenario}")

    sandbox_root = create_demo_sandbox(workspace_root)
    cleanup_result = "pending"
    local_result: LocalExecutionResult | None = None
    validation: DemoValidationResult | None = None
    runtime_guidance: str | None = None
    fake_call_count = 0
    first_pass_status: str | None = None

    try:
        materialize_demo_project(project_path.resolve(), sandbox_root, mode=mode, scenario=scenario)

        if scenario == OVERSIZED_SCENARIO:
            local_result = run_local_execution(
                sandbox_root,
                DEMO_STORY,
                http_client=http_client if mode == LOCAL_MODE else FakeDemoLocalModelHttpClient(scenario),
            )
            fake_call_count = 0 if mode == FAKE_MODE else 0
        elif scenario == RESUME_SCENARIO and mode == FAKE_MODE and http_client is None:
            first_client = FakeDemoLocalModelHttpClient(
                scenario,
                overrides={"calculator-tests": ValueError("intentional resume pause")},
            )
            first_result = run_local_execution(sandbox_root, DEMO_STORY, http_client=first_client)
            first_pass_status = first_result.status
            second_client = FakeDemoLocalModelHttpClient(scenario)
            local_result = run_local_execution(
                sandbox_root,
                DEMO_STORY,
                resume=True,
                http_client=second_client,
            )
            fake_call_count = len(first_client.calls) + len(second_client.calls)
        else:
            effective_client = http_client
            if mode == FAKE_MODE and effective_client is None:
                effective_client = FakeDemoLocalModelHttpClient(scenario)
            local_result = run_local_execution(
                sandbox_root,
                DEMO_STORY,
                http_client=effective_client,
            )
            if isinstance(effective_client, FakeDemoLocalModelHttpClient):
                fake_call_count = len(effective_client.calls)

        assert local_result is not None
        persist_demo_metadata(
            sandbox_root,
            mode=mode,
            scenario=scenario,
            local_result=local_result,
            fake_call_count=fake_call_count,
            first_pass_status=first_pass_status,
        )

        if scenario in {SUCCESS_SCENARIO, RESUME_SCENARIO} and local_result.status == "completed":
            validation = run_demo_validation(sandbox_root)
            persist_demo_validation(sandbox_root, validation)

        if mode == LOCAL_MODE and runtime_unavailable(local_result):
            runtime_guidance = (
                "Local runtime is unavailable. Configure `.agentic/agent_runtime.yaml` with "
                "`local_model_runtime.enabled: true` and an Ollama or LM Studio-compatible "
                "OpenAI-style endpoint, then rerun `agentic demo-subtasks --mode local`."
            )
    finally:
        cleanup_result = cleanup_demo_sandbox(sandbox_root, keep_workspace=keep_workspace)

    return DemoSubtasksResult(
        mode=mode,
        scenario=scenario,
        sandbox_path=sandbox_root,
        status=local_result.status if local_result is not None else "failed",
        local_execution=local_result if local_result is not None else failed_demo_result(sandbox_root),
        cleanup_result=cleanup_result,
        preserved_workspace=keep_workspace,
        fake_call_count=fake_call_count,
        validation=validation,
        runtime_guidance=runtime_guidance,
        first_pass_status=first_pass_status,
    )


def failed_demo_result(sandbox_root: Path) -> LocalExecutionResult:
    story_path = sandbox_root / "stories" / DEMO_STORY
    return LocalExecutionResult(
        story=DEMO_STORY,
        story_path=story_path,
        status="failed",
        state_path=story_path / "reports" / "local_execution" / "state.yaml",
        roles=[],
        subtasks=[],
    )


def create_demo_sandbox(workspace_root: Path | None) -> Path:
    root = validate_workspace_root(workspace_root) if workspace_root is not None else None
    sandbox = Path(tempfile.mkdtemp(prefix="agentic-demo-subtasks-", dir=root))
    return sandbox.resolve()


def validate_workspace_root(workspace_root: Path) -> str:
    resolved = workspace_root.resolve()
    if not any(is_relative_to(resolved, safe_root) for safe_root in SAFE_TEMP_ROOTS):
        roots = ", ".join(str(root) for root in sorted(SAFE_TEMP_ROOTS))
        raise ValueError(f"Workspace root must stay inside a safe temp root: {roots}")
    resolved.mkdir(parents=True, exist_ok=True)
    return str(resolved)


def materialize_demo_project(
    source_project_path: Path,
    sandbox_root: Path,
    *,
    mode: str,
    scenario: str,
) -> None:
    write_demo_runtime_config(source_project_path, sandbox_root, mode=mode)
    (sandbox_root / "blueprints").mkdir(parents=True, exist_ok=True)
    (sandbox_root / "stories" / DEMO_STORY / "instructions").mkdir(parents=True, exist_ok=True)
    (sandbox_root / "stories" / DEMO_STORY / "reports").mkdir(parents=True, exist_ok=True)

    story_path = sandbox_root / "stories" / DEMO_STORY
    (story_path / "story.md").write_text(demo_story_markdown(), encoding="utf-8")
    (story_path / "status.yaml").write_text(
        "story_id: demo_subtasks\nslug: demo-subtasks\nstatus: prepared\nready_for_review: false\n",
        encoding="utf-8",
    )
    (story_path / "test_plan.yaml").write_text(
        yaml.safe_dump(
            {
                "test_layers_version": 1,
                "unit_tests": layer_plan("Generated calculator tests validate fake/local parity."),
                "integration_tests": layer_plan("Demo scenarios exercise the end-to-end sandbox."),
                "mock_e2e_tests": layer_plan("Fake mode runs without network or local runtime."),
                "live_read_only_checks": skipped_layer_plan("Optional local runtime only."),
                "remote_dev_smoke_tests": skipped_layer_plan("No remote deployment is involved."),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (story_path / "monitoring_plan.yaml").write_text(
        yaml.safe_dump(
            {
                "logs_required": [
                    "demo_workspace_location",
                    "selected_demo_mode",
                    "selected_demo_scenario",
                    "demo_task_execution_order",
                    "task_context_estimate",
                    "task_context_budget",
                ],
                "watch_for": [
                    "sandbox_escape_attempt",
                    "unsafe_multi_file_partial_write",
                    "fake_mode_nondeterminism",
                    "local_runtime_fallback_attempt",
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (story_path / "instructions" / "developer_agent.md").write_text(
        "# Developer Agent\n\n## Role\n\nImplement calculator source files inside the sandbox only.\n",
        encoding="utf-8",
    )
    (story_path / "instructions" / "test_agent.md").write_text(
        "# Test Agent\n\n## Role\n\nWrite calculator tests and validation notes inside the sandbox only.\n",
        encoding="utf-8",
    )
    (sandbox_root / "blueprints" / "blueprint.yaml").write_text(
        yaml.safe_dump({"stories": [demo_blueprint_story(scenario)]}, sort_keys=False),
        encoding="utf-8",
    )


def write_demo_runtime_config(source_project_path: Path, sandbox_root: Path, *, mode: str) -> None:
    config = yaml.safe_load(default_runtime_config_text())
    config["local_execution"]["global_default_model"] = (
        "demo-fake-model" if mode == FAKE_MODE else config["local_execution"]["global_default_model"]
    )
    config["local_execution"]["role_defaults"] = {
        "developer": "demo-fake-model",
        "test": "demo-fake-model",
    }

    if mode == LOCAL_MODE:
        try:
            _, source_runtime = load_runtime_config(source_project_path)
        except (FileNotFoundError, ValueError):
            source_runtime = {}
        local_runtime = source_runtime.get("local_model_runtime")
        if isinstance(local_runtime, dict):
            config["local_model_runtime"] = local_runtime
            model_name = local_runtime.get("model")
            if isinstance(model_name, str) and model_name.strip():
                config["local_execution"]["global_default_model"] = model_name.strip()
                config["local_execution"]["role_defaults"] = {
                    "developer": model_name.strip(),
                    "test": model_name.strip(),
                }
    else:
        config["local_model_runtime"]["enabled"] = True
        config["local_model_runtime"]["base_url"] = "http://fake.local/v1"
        config["local_model_runtime"]["model"] = "demo-fake-model"

    config_path = sandbox_root / ".agentic" / "agent_runtime.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def demo_blueprint_story(scenario: str) -> dict[str, Any]:
    oversized = scenario == OVERSIZED_SCENARIO
    return {
        "id": "STORY-DEMO",
        "story_id": "demo_subtasks",
        "slug": "demo-subtasks",
        "title": "Demo subtasks",
        "goal": "Demonstrate end-to-end dependency-aware local subtask execution in a temporary sandbox.",
        "acceptance_criteria": [
            "AC-001: Calculator module is generated inside the sandbox.",
            "AC-002: Calculator tests are generated inside the sandbox.",
            "AC-003: Calculator CLI is generated inside the sandbox.",
            "AC-004: Final validation evidence is persisted inside the sandbox.",
        ],
        "subtasks": [
            demo_subtask(
                "calculator-module",
                "Create calculator module",
                role="developer",
                depends_on=[],
                prior_task_outputs=[],
                oversized=oversized,
                expected_outputs=["calculator/__init__.py", "calculator/core.py"],
                summaries=[
                    "Implement only add and subtract helpers for this demo.",
                    "Use integer inputs and integer return values for add and subtract.",
                ],
                validation=[
                    "Return complete file contents for calculator/__init__.py and calculator/core.py.",
                    "Export only add and subtract from calculator/__init__.py.",
                    "Implement def add(left: int, right: int) -> int and def subtract(left: int, right: int) -> int.",
                    "Produce a concise handoff summary for downstream tasks.",
                ],
            ),
            demo_subtask(
                "calculator-tests",
                "Create calculator tests",
                role="test",
                depends_on=["calculator-module"],
                prior_task_outputs=["calculator-module"],
                oversized=False,
                expected_outputs=["tests/test_calculator.py"],
                summaries=[
                    "Write pytest tests for add and subtract only.",
                    "The generated CLI contract is validated separately and should not change the test scope.",
                ],
                validation=[
                    "Return complete file contents for tests/test_calculator.py.",
                    "Add pytest coverage for add(2, 3) == 5 and subtract(5, 3) == 2.",
                    "Produce a concise handoff summary for downstream tasks.",
                ],
            ),
            demo_subtask(
                "calculator-cli",
                "Create calculator CLI",
                role="developer",
                depends_on=["calculator-module"],
                prior_task_outputs=["calculator-module"],
                oversized=False,
                expected_outputs=["calculator/cli.py"],
                summaries=[
                    "Implement a minimal CLI that adds two integers.",
                    "The CLI must support exactly: python -m calculator.cli 2 3 and print 5 with no label.",
                ],
                validation=[
                    "Return complete file contents for calculator/cli.py.",
                    "Accept exactly two positional integer arguments named left and right.",
                    "Call add(left, right) and print the numeric result only.",
                    "Do not require an operation selector argument.",
                    "Produce a concise handoff summary for downstream tasks.",
                ],
            ),
            demo_subtask(
                "validation-report",
                "Write validation report",
                role="test",
                depends_on=["calculator-tests", "calculator-cli"],
                prior_task_outputs=["calculator-tests", "calculator-cli"],
                oversized=False,
                expected_outputs=["stories/demo_subtasks/reports/final_validation.md"],
                summaries=[
                    "Summarize the expected validation commands for pytest and the CLI smoke test.",
                    "The CLI smoke test command is python -m calculator.cli 2 3 and it must print 5.",
                ],
                validation=[
                    "Return complete file contents for stories/demo_subtasks/reports/final_validation.md.",
                    "Mention pytest -q and python -m calculator.cli 2 3 as the final validation commands.",
                    "Produce a concise handoff summary for downstream tasks.",
                ],
            ),
        ],
    }


def demo_subtask(
    task_id: str,
    title: str,
    *,
    role: str,
    depends_on: list[str],
    prior_task_outputs: list[str],
    oversized: bool,
    expected_outputs: list[str],
    summaries: list[str] | None = None,
    validation: list[str] | None = None,
) -> dict[str, Any]:
    max_input_tokens = 1100 if oversized else 6000
    reserved_output_tokens = 1000 if oversized else 1000
    return {
        "id": task_id,
        "title": title,
        "role": role,
        "depends_on": depends_on,
        "requirement_ids": ["AC-001", "AC-002", "AC-003", "AC-004"],
        "required_context": {
            "files": ["stories/demo_subtasks/story.md", "stories/demo_subtasks/instructions/*.md"],
            "summaries": [
                "Keep all writes inside the temporary demo sandbox.",
                "Use dependency handoffs from completed tasks when available.",
                *(summaries or []),
            ],
            "prior_task_outputs": prior_task_outputs,
            "architecture_decisions": [
                "No cloud fallback.",
                "No Codex fallback.",
            ],
        },
        "writable_paths": [
            "calculator/**",
            "tests/**",
            "stories/demo_subtasks/reports/**",
        ],
        "expected_outputs": expected_outputs,
        "validation": validation or ["Produce a concise handoff summary for downstream tasks."],
        "context_budget": {
            "max_input_tokens": max_input_tokens,
            "reserved_output_tokens": reserved_output_tokens,
            "required_context_must_fit": True,
            "allow_required_context_trimming": False,
            "oversized_task_policy": "reject_for_cloud_redecomposition",
        },
    }


def layer_plan(reason: str) -> dict[str, Any]:
    return {
        "required": True,
        "action": "add_or_update",
        "frequency": "every_commit",
        "evidence_or_reason": reason,
    }


def skipped_layer_plan(reason: str) -> dict[str, Any]:
    return {
        "required": False,
        "action": "not_applicable_with_reason",
        "frequency": "manual_only",
        "evidence_or_reason": reason,
    }


def demo_story_markdown() -> str:
    return """# STORY-DEMO: Demo subtasks

## Goal

Generate a small calculator application entirely inside a disposable sandbox.

## Acceptance Criteria

- AC-001: Calculator module is generated inside the sandbox.
- AC-002: Calculator tests are generated inside the sandbox.
- AC-003: Calculator CLI is generated inside the sandbox.
- AC-004: Final validation evidence is persisted inside the sandbox.
"""


def fake_http_response(content: str) -> dict[str, Any]:
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": content},
            }
        ]
    }


def success_response(task_id: str, call_index: int) -> str:
    files_by_task = {
        "calculator-module": [
            {
                "path": "calculator/__init__.py",
                "content": "from .core import add, subtract\n",
            },
            {
                "path": "calculator/core.py",
                "content": (
                    "def add(left: int, right: int) -> int:\n"
                    "    return left + right\n\n"
                    "def subtract(left: int, right: int) -> int:\n"
                    "    return left - right\n"
                ),
            },
        ],
        "calculator-tests": [
            {
                "path": "tests/test_calculator.py",
                "content": (
                    "from calculator import add, subtract\n\n"
                    "def test_add() -> None:\n"
                    "    assert add(2, 3) == 5\n\n"
                    "def test_subtract() -> None:\n"
                    "    assert subtract(5, 3) == 2\n"
                ),
            }
        ],
        "calculator-cli": [
            {
                "path": "calculator/cli.py",
                "content": (
                    "import argparse\n\n"
                    "from .core import add\n\n"
                    "def main() -> None:\n"
                    "    parser = argparse.ArgumentParser(prog='calculator')\n"
                    "    parser.add_argument('left', type=int)\n"
                    "    parser.add_argument('right', type=int)\n"
                    "    args = parser.parse_args()\n"
                    "    print(add(args.left, args.right))\n\n"
                    "if __name__ == '__main__':\n"
                    "    main()\n"
                ),
            }
        ],
        "validation-report": [
            {
                "path": "stories/demo_subtasks/reports/final_validation.md",
                "content": "# Final Validation\n\nCalculator files are ready for pytest and CLI validation.\n",
            }
        ],
    }
    response = {
        "report": f"Completed {task_id}.\n",
        "files": files_by_task[task_id],
        "handoff_summary": {
            "decisions": [f"Completed {task_id}."],
            "files_changed": [entry["path"] for entry in files_by_task[task_id]],
            "outputs_produced": [entry["path"] for entry in files_by_task[task_id]],
            "tests_run": [],
            "unresolved_risks": [],
            "available_to_dependents": True,
            "call_count": call_index,
        },
    }
    return yaml.safe_dump(response, sort_keys=False)


def extract_prompt_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("Fake demo payload must include messages.")
    first = messages[0]
    if not isinstance(first, dict) or not isinstance(first.get("content"), str):
        raise ValueError("Fake demo payload message must include content.")
    return str(first["content"])


def extract_task_id(prompt: str) -> str:
    match = re.search(r"^task_id:\s*([A-Za-z0-9_.-]+)\s*$", prompt, flags=re.MULTILINE)
    if match is None:
        raise ValueError("Unable to determine demo task_id from local execution prompt.")
    return match.group(1)


def run_demo_validation(sandbox_root: Path) -> DemoValidationResult:
    env = os.environ.copy()
    # Nested validation should not inherit unrelated pytest plugins from the outer test process.
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    pytest_result = subprocess.run(
        ["python", "-m", "pytest", "-q", "--capture=no"],
        cwd=sandbox_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    cli_result = subprocess.run(
        ["python", "-m", "calculator.cli", "2", "3"],
        cwd=sandbox_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    validation_path = sandbox_root / "stories" / DEMO_STORY / "reports" / "demo_validation.yaml"
    return DemoValidationResult(
        pytest_passed=pytest_result.returncode == 0,
        cli_passed=cli_result.returncode == 0 and cli_result.stdout.strip() == "5",
        pytest_output=(pytest_result.stdout + pytest_result.stderr).strip(),
        cli_output=(cli_result.stdout + cli_result.stderr).strip(),
        validation_path=validation_path,
    )


def persist_demo_validation(sandbox_root: Path, validation: DemoValidationResult) -> None:
    validation.validation_path.write_text(
        yaml.safe_dump(
            {
                "pytest_passed": validation.pytest_passed,
                "cli_passed": validation.cli_passed,
                "pytest_output": validation.pytest_output,
                "cli_output": validation.cli_output,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def persist_demo_metadata(
    sandbox_root: Path,
    *,
    mode: str,
    scenario: str,
    local_result: LocalExecutionResult,
    fake_call_count: int,
    first_pass_status: str | None,
) -> None:
    state = {}
    if local_result.state_path.exists():
        loaded = yaml.safe_load(local_result.state_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            state = loaded
    result_path = sandbox_root / "stories" / DEMO_STORY / "reports" / "demo_result.yaml"
    result_path.write_text(
        yaml.safe_dump(
            {
                "mode": mode,
                "scenario": scenario,
                "status": local_result.status,
                "fake_call_count": fake_call_count,
                "first_pass_status": first_pass_status,
                "state_path": str(local_result.state_path),
                "subtasks": [
                    {
                        "task_id": task.task_id,
                        "role": task.role,
                        "status": task.status,
                        "estimated_input_tokens": task.estimated_input_tokens,
                        "usable_input_tokens": task.usable_input_tokens,
                        "model": task.model,
                    }
                    for task in (local_result.subtasks or [])
                ],
                "state": state,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def runtime_unavailable(result: LocalExecutionResult) -> bool:
    if result.state_path.exists():
        loaded = yaml.safe_load(result.state_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            tasks = loaded.get("tasks")
            if isinstance(tasks, dict):
                for task_state in tasks.values():
                    if not isinstance(task_state, dict):
                        continue
                    if task_state.get("failure_type") in {
                        "runtime_disabled",
                        "configuration_error",
                        "runtime_unavailable",
                        "unresolved_model",
                    }:
                        return True
    return False


def cleanup_demo_sandbox(sandbox_root: Path, *, keep_workspace: bool) -> str:
    if keep_workspace:
        return f"preserved at {sandbox_root}"
    try:
        shutil.rmtree(sandbox_root)
    except OSError as error:
        return f"preservation forced after cleanup failure: {error}; path={sandbox_root}"
    return f"deleted {sandbox_root}"


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def add_demo_subtasks_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Source repository used to seed the temporary demo sandbox.",
    )
    parser.add_argument(
        "--mode",
        default=FAKE_MODE,
        choices=sorted(DEMO_MODES),
        help="Execution mode. Defaults to deterministic fake mode.",
    )
    parser.add_argument(
        "--scenario",
        default=SUCCESS_SCENARIO,
        choices=sorted(DEMO_SCENARIOS),
        help="Demo scenario to run.",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Preserve the generated sandbox workspace for inspection.",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help="Optional safe temporary root under the system temp directory or C:/tmp.",
    )
