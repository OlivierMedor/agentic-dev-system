from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_dev.local_repair_loop import run_local_repair_loop
from agentic_dev.repair_loop_smoke import normalize_symbol
from agentic_dev.review_bundle import CommandResult


STORY = "story_071_repair_loop_smoke_test_fixes"


def test_normalize_symbol_smoke_helper_formats_uppercase_dash_separated() -> None:
    assert normalize_symbol("eth/usd") == "ETH-USD"
    assert normalize_symbol("btc-usd") == "BTC-USD"


def test_local_repair_loop_smoke_repairs_broken_helper_from_blueprint_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story_path = create_story_workspace(tmp_path)
    target = write_broken_helper(tmp_path)
    test_path = write_smoke_test(tmp_path)
    failure_output_path = write_pytest_failure_output(tmp_path)

    dry_run_result = run_local_repair_loop(
        tmp_path,
        STORY,
        target,
        tests=(test_path,),
        failure_output=failure_output_path,
        required_api=("normalize_symbol",),
        execute=False,
    )

    dry_run_prompt = dry_run_result.prompt_path.read_text(encoding="utf-8")
    assert dry_run_result.classification.kind.value == "pytest_failure"
    assert dry_run_result.classification.owner.value == "developer"
    assert dry_run_result.manual_support_report_path is None
    assert "Repair Loop Smoke Test Fixes" in dry_run_prompt
    assert "trading symbol" in dry_run_prompt
    assert "No story contract file or matching blueprint story was found" not in dry_run_prompt

    repaired_file = (
        "from __future__ import annotations\n\n\n"
        "def normalize_symbol(symbol: str) -> str:\n"
        "    \"\"\"Normalize a trading symbol into uppercase dash-separated form.\"\"\"\n"
        "    return symbol.replace(\"/\", \"-\").replace(\"_\", \"-\").upper()"
    )
    monkeypatch.setattr(
        "agentic_dev.local_repair_loop.invoke_local_repair_model",
        lambda project_path, prompt_text, http_client=None: repaired_file,
    )

    def fake_command_runner(command: list[str], cwd: Path) -> CommandResult:
        return CommandResult(command=" ".join(command), returncode=0, stdout="ok\n", stderr="")

    execute_result = run_local_repair_loop(
        tmp_path,
        STORY,
        target,
        tests=(test_path,),
        failure_output=failure_output_path,
        required_api=("normalize_symbol",),
        execute=True,
        max_local_attempts=1,
        command_runner=fake_command_runner,
    )

    assert execute_result.status == "completed"
    assert execute_result.applied is True
    assert execute_result.attempts[0].cloud_attempt_count == 0
    assert execute_result.attempts[0].codex_used is False
    assert target.read_text(encoding="utf-8") == repaired_file
    assert execute_result.attempts[0].command_results is not None
    assert execute_result.attempts[0].command_results["ruff"].passed is True
    assert execute_result.attempts[0].command_results["pytest"].passed is True

    attempt_report = yaml.safe_load(
        (story_path / "reports" / "local_repair_loop" / "repair_attempt_01.yaml").read_text(
            encoding="utf-8",
        ),
    )
    assert attempt_report["cloud_attempt_count"] == 0
    assert attempt_report["codex_used"] is False
    assert attempt_report["failure_kind"] == "repair_accepted"


def create_story_workspace(tmp_path: Path) -> Path:
    story_path = tmp_path / "stories" / STORY
    story_path.mkdir(parents=True)
    (tmp_path / "blueprints" / "stories").mkdir(parents=True, exist_ok=True)
    (tmp_path / "blueprints" / "stories" / f"{STORY}.yaml").write_text(
        "\n".join(
            [
                "name: Repair Loop Smoke Test Fixes",
                "stories:",
                f"  - story_id: {STORY}",
                f"    slug: {STORY}",
                "    title: Repair Loop Smoke Test Fixes",
                "    goal: Verify local repair loop fixes for smoke tests.",
                "    acceptance_criteria:",
                "      - Load story contract text from a matching blueprint when story.md is missing.",
                "      - Classify clear pytest assertion failures as developer repair work.",
                "      - Allow harmless symbol-normalization wording.",
                "      - Keep cloud escalation manual-only.",
            ],
        ),
        encoding="utf-8",
    )
    return story_path


def write_broken_helper(tmp_path: Path) -> Path:
    target = tmp_path / "src" / "agentic_dev" / "repair_loop_smoke.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '\n'.join(
            [
                '"""Tiny helper used to smoke-test the local repair loop."""',
                "",
                "",
                "def normalize_symbol(symbol: str) -> str:",
                '    """Normalize a trading symbol into uppercase dash-separated form."""',
                '    return symbol.lower().replace("/", "_")',
                "",
            ],
        ),
        encoding="utf-8",
    )
    return target


def write_smoke_test(tmp_path: Path) -> Path:
    test_path = tmp_path / "tests" / "test_repair_loop_smoke.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(
        "\n".join(
            [
                "from agentic_dev.repair_loop_smoke import normalize_symbol",
                "",
                "",
                "def test_normalize_symbol_uppercase_dash_separated() -> None:",
                '    assert normalize_symbol("eth/usd") == "ETH-USD"',
                "",
                "",
                "def test_normalize_symbol_preserves_existing_dash() -> None:",
                '    assert normalize_symbol("btc-usd") == "BTC-USD"',
            ],
        ),
        encoding="utf-8",
    )
    return test_path


def write_pytest_failure_output(tmp_path: Path) -> Path:
    failure_output = tmp_path / "reports" / "pytest_failure_1.txt"
    failure_output.parent.mkdir(parents=True, exist_ok=True)
    failure_output.write_text(
        "\n".join(
            [
                "=================================== FAILURES ===================================",
                "___________ test_normalize_symbol_uppercase_dash_separated _____________",
                "    assert normalize_symbol(\"eth/usd\") == \"ETH-USD\"",
                "E   AssertionError: assert 'eth_usd' == 'ETH-USD'",
                "___________ test_normalize_symbol_preserves_existing_dash _____________",
                "    assert normalize_symbol(\"btc-usd\") == \"BTC-USD\"",
                "E   AssertionError: assert 'btc-usd' == 'BTC-USD'",
            ],
        ),
        encoding="utf-8",
    )
    return failure_output
