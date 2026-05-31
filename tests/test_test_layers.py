from pathlib import Path

import pytest
import yaml

from agentic_dev.cli import main
from agentic_dev.test_layers import TEST_LAYER_FAILED, TEST_LAYER_PASSED, run_test_layers


STORY = "story_014_test_layer_support"


def valid_test_plan() -> dict:
    return {
        "test_layers_version": 1,
        "unit_tests": {
            "required": True,
            "action": "add_or_update",
            "frequency": "every_commit",
            "evidence_or_reason": "Added unit coverage for layer validation.",
        },
        "integration_tests": {
            "required": True,
            "action": "confirm_existing",
            "frequency": "every_pull_request",
            "evidence_or_reason": "Existing CLI tests cover command integration.",
        },
        "mock_e2e_tests": {
            "required": True,
            "action": "confirm_existing",
            "frequency": "before_merge",
            "evidence_or_reason": "Mock workflow coverage exercises the path end to end.",
        },
        "live_read_only_checks": {
            "required": False,
            "action": "not_applicable_with_reason",
            "frequency": "scheduled_or_before_release",
            "evidence_or_reason": "No live read-only service is touched by this story.",
        },
        "remote_dev_smoke_tests": {
            "required": False,
            "action": "scheduled_later_with_reason",
            "frequency": "after_remote_dev_deploy",
            "evidence_or_reason": "Remote dev smoke coverage will run when that environment exists.",
        },
    }


def create_story_with_test_plan(project_path: Path, test_plan: dict) -> Path:
    story_path = project_path / "stories" / STORY
    story_path.mkdir(parents=True)
    (story_path / "test_plan.yaml").write_text(
        yaml.safe_dump(test_plan, sort_keys=False),
        encoding="utf-8",
    )
    return story_path


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def run_invalid_plan(tmp_path: Path, test_plan: dict) -> tuple[Path, list[str]]:
    story_path = create_story_with_test_plan(tmp_path, test_plan)

    result = run_test_layers(tmp_path, STORY)

    assert result.status == TEST_LAYER_FAILED
    assert (story_path / "reports" / "test_layer_result.yaml").exists()
    assert (story_path / "reports" / "test_layer_report.md").exists()
    return story_path, result.failed_checks


def test_test_layers_passes_for_complete_valid_plan_and_writes_reports(
    tmp_path: Path,
) -> None:
    story_path = create_story_with_test_plan(tmp_path, valid_test_plan())

    result = run_test_layers(tmp_path, STORY)

    assert result.status == TEST_LAYER_PASSED
    assert result.failed_checks == []
    assert result.result_path == story_path / "reports" / "test_layer_result.yaml"
    assert result.report_path == story_path / "reports" / "test_layer_report.md"
    assert result.result_path.exists()
    assert result.report_path.exists()

    yaml_result = read_yaml(result.result_path)
    markdown_report = result.report_path.read_text(encoding="utf-8")
    assert yaml_result["status"] == TEST_LAYER_PASSED
    assert yaml_result["layers"]["unit_tests"]["status"] == TEST_LAYER_PASSED
    assert "## Final status" in markdown_report
    assert TEST_LAYER_PASSED in markdown_report


def test_cli_test_layers_defaults_project_to_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    story_path = create_story_with_test_plan(tmp_path, valid_test_plan())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["agentic", "test-layers", "--story", STORY])

    main()

    output = capsys.readouterr().out
    assert "Test layer status: PASSED" in output
    assert (story_path / "reports" / "test_layer_result.yaml").exists()
    assert (story_path / "reports" / "test_layer_report.md").exists()


def test_test_layers_fails_when_required_layer_is_missing(tmp_path: Path) -> None:
    test_plan = valid_test_plan()
    del test_plan["mock_e2e_tests"]

    _, failed_checks = run_invalid_plan(tmp_path, test_plan)

    assert "mock_e2e_tests must be a YAML mapping." in failed_checks


def test_test_layers_fails_when_required_is_not_boolean(tmp_path: Path) -> None:
    test_plan = valid_test_plan()
    test_plan["unit_tests"]["required"] = "yes"

    _, failed_checks = run_invalid_plan(tmp_path, test_plan)

    assert "unit_tests.required must be true or false." in failed_checks


def test_test_layers_fails_when_action_is_invalid(tmp_path: Path) -> None:
    test_plan = valid_test_plan()
    test_plan["integration_tests"]["action"] = "write_some_tests"

    _, failed_checks = run_invalid_plan(tmp_path, test_plan)

    assert any("integration_tests.action must be one of:" in check for check in failed_checks)


def test_test_layers_fails_when_frequency_is_missing(tmp_path: Path) -> None:
    test_plan = valid_test_plan()
    del test_plan["unit_tests"]["frequency"]

    _, failed_checks = run_invalid_plan(tmp_path, test_plan)

    assert "unit_tests is missing required field: frequency" in failed_checks


def test_test_layers_fails_when_frequency_is_empty(tmp_path: Path) -> None:
    test_plan = valid_test_plan()
    test_plan["integration_tests"]["frequency"] = ""

    _, failed_checks = run_invalid_plan(tmp_path, test_plan)

    assert "integration_tests.frequency must not be empty." in failed_checks


def test_test_layers_fails_when_frequency_is_whitespace_only(tmp_path: Path) -> None:
    test_plan = valid_test_plan()
    test_plan["mock_e2e_tests"]["frequency"] = "   "

    _, failed_checks = run_invalid_plan(tmp_path, test_plan)

    assert "mock_e2e_tests.frequency must not be empty." in failed_checks


def test_test_layers_fails_when_frequency_is_not_text(tmp_path: Path) -> None:
    test_plan = valid_test_plan()
    test_plan["live_read_only_checks"]["frequency"] = 7

    _, failed_checks = run_invalid_plan(tmp_path, test_plan)

    assert "live_read_only_checks.frequency must be text." in failed_checks


def test_test_layers_passes_with_valid_non_empty_frequency(tmp_path: Path) -> None:
    test_plan = valid_test_plan()
    test_plan["remote_dev_smoke_tests"]["frequency"] = "nightly"
    story_path = create_story_with_test_plan(tmp_path, test_plan)

    result = run_test_layers(tmp_path, STORY)

    assert result.status == TEST_LAYER_PASSED
    assert result.failed_checks == []
    yaml_result = read_yaml(story_path / "reports" / "test_layer_result.yaml")
    assert yaml_result["layers"]["remote_dev_smoke_tests"]["frequency"] == "nightly"


def test_test_layers_fails_when_evidence_or_reason_is_empty(tmp_path: Path) -> None:
    test_plan = valid_test_plan()
    test_plan["live_read_only_checks"]["evidence_or_reason"] = "   "

    _, failed_checks = run_invalid_plan(tmp_path, test_plan)

    assert "live_read_only_checks.evidence_or_reason must not be empty." in failed_checks


def test_test_layers_fails_when_required_layer_is_marked_not_applicable(
    tmp_path: Path,
) -> None:
    test_plan = valid_test_plan()
    test_plan["mock_e2e_tests"]["action"] = "not_applicable_with_reason"

    _, failed_checks = run_invalid_plan(tmp_path, test_plan)

    assert (
        "mock_e2e_tests.action cannot be not_applicable_with_reason when required is true."
        in failed_checks
    )
