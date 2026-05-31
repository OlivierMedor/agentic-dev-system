from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


TEST_LAYERS_VERSION = 1
TEST_LAYER_PASSED = "PASSED"
TEST_LAYER_FAILED = "FAILED"
TEST_LAYER_LEGACY_FORMAT = "LEGACY_FORMAT"

TEST_LAYER_NAMES = [
    "unit_tests",
    "integration_tests",
    "mock_e2e_tests",
    "live_read_only_checks",
    "remote_dev_smoke_tests",
]

VALID_ACTIONS = {
    "add_or_update",
    "update_existing",
    "confirm_existing",
    "not_applicable_with_reason",
    "scheduled_later_with_reason",
}

OPTIONAL_LAYER_ACTIONS = {
    "not_applicable_with_reason",
    "scheduled_later_with_reason",
}

REQUIRED_LAYER_FIELDS = [
    "required",
    "action",
    "frequency",
    "evidence_or_reason",
]

DEFAULT_TEST_LAYER_PLAN: dict[str, Any] = {
    "test_layers_version": TEST_LAYERS_VERSION,
    "unit_tests": {
        "required": True,
        "action": "add_or_update",
        "frequency": "every_commit",
        "evidence_or_reason": "Explain unit test coverage.",
    },
    "integration_tests": {
        "required": True,
        "action": "confirm_existing",
        "frequency": "every_pull_request",
        "evidence_or_reason": "Explain integration coverage.",
    },
    "mock_e2e_tests": {
        "required": True,
        "action": "confirm_existing",
        "frequency": "before_merge",
        "evidence_or_reason": "Explain mock E2E coverage.",
    },
    "live_read_only_checks": {
        "required": False,
        "action": "not_applicable_with_reason",
        "frequency": "scheduled_or_before_release",
        "evidence_or_reason": (
            "Explain why live checks are not applicable or how they will be scheduled."
        ),
    },
    "remote_dev_smoke_tests": {
        "required": False,
        "action": "not_applicable_with_reason",
        "frequency": "after_remote_dev_deploy",
        "evidence_or_reason": (
            "Explain why remote smoke tests are not applicable or how they will be scheduled."
        ),
    },
}

TEST_LAYER_EXPLANATIONS = {
    "unit_tests": "Small tests for focused functions, classes, and validation rules.",
    "integration_tests": "Tests that exercise connected modules or command paths together.",
    "mock_e2e_tests": "End-to-end style checks that use mocks instead of real external systems.",
    "live_read_only_checks": "Safe live checks that only read from real services or environments.",
    "remote_dev_smoke_tests": "Basic checks after deploying or running in a remote dev environment.",
}


@dataclass(frozen=True)
class TestLayerResult:
    story: str
    status: str
    passed_checks: list[str]
    failed_checks: list[str]
    layers: dict[str, dict[str, Any]]
    next_action: str
    result_path: Path
    report_path: Path


def run_test_layers(project_path: Path, story: str) -> TestLayerResult:
    project_path = project_path.resolve()
    story_path = project_path / "stories" / story

    if not story_path.exists():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    if not story_path.is_dir():
        raise ValueError(f"Story path is not a folder: {story_path}")

    test_plan_path = story_path / "test_plan.yaml"
    if not test_plan_path.exists():
        raise FileNotFoundError(f"Required test plan does not exist: {test_plan_path}")

    test_plan = load_yaml_mapping(test_plan_path, "test_plan.yaml")
    reports_path = story_path / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)

    if test_plan.get("test_layers_version") != TEST_LAYERS_VERSION:
        result = build_legacy_result(story, reports_path)
    else:
        result = validate_test_layer_plan(story, reports_path, test_plan)

    write_test_layer_result(result.result_path, result)
    write_test_layer_report(result.report_path, result)
    return result


def test_plan_uses_test_layer_schema(story_path: Path) -> bool:
    test_plan_path = story_path / "test_plan.yaml"
    if not test_plan_path.exists():
        return False

    test_plan = load_yaml_mapping(test_plan_path, "test_plan.yaml")
    return test_plan.get("test_layers_version") == TEST_LAYERS_VERSION


def load_yaml_mapping(path: Path, label: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as yaml_file:
        loaded = yaml.safe_load(yaml_file)

    if loaded is None:
        return {}

    if not isinstance(loaded, dict):
        raise ValueError(f"{label} must be a YAML mapping: {path}")

    return loaded


def build_legacy_result(story: str, reports_path: Path) -> TestLayerResult:
    passed_checks = ["Detected legacy test plan format."]
    next_action = (
        "Legacy test plan format detected. Add test_layers_version: 1 and address all "
        "standard test layers before relying on test layer validation."
    )

    return TestLayerResult(
        story=story,
        status=TEST_LAYER_LEGACY_FORMAT,
        passed_checks=passed_checks,
        failed_checks=[],
        layers={},
        next_action=next_action,
        result_path=reports_path / "test_layer_result.yaml",
        report_path=reports_path / "test_layer_report.md",
    )


def validate_test_layer_plan(
    story: str,
    reports_path: Path,
    test_plan: dict[str, Any],
) -> TestLayerResult:
    passed_checks: list[str] = []
    failed_checks: list[str] = []
    layer_results: dict[str, dict[str, Any]] = {}

    for layer_name in TEST_LAYER_NAMES:
        layer_result = validate_layer(layer_name, test_plan.get(layer_name))
        layer_results[layer_name] = layer_result

        if layer_result["status"] == TEST_LAYER_PASSED:
            passed_checks.append(f"{layer_name} is addressed.")
        else:
            failed_checks.extend(layer_result["failed_checks"])

    status = TEST_LAYER_PASSED if not failed_checks else TEST_LAYER_FAILED
    next_action = build_next_action(status)

    return TestLayerResult(
        story=story,
        status=status,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        layers=layer_results,
        next_action=next_action,
        result_path=reports_path / "test_layer_result.yaml",
        report_path=reports_path / "test_layer_report.md",
    )


def validate_layer(layer_name: str, layer: Any) -> dict[str, Any]:
    failed_checks: list[str] = []

    if not isinstance(layer, dict):
        return {
            "status": TEST_LAYER_FAILED,
            "required": None,
            "action": None,
            "frequency": None,
            "evidence_or_reason": None,
            "failed_checks": [f"{layer_name} must be a YAML mapping."],
        }

    for field_name in REQUIRED_LAYER_FIELDS:
        if field_name not in layer:
            failed_checks.append(f"{layer_name} is missing required field: {field_name}")

    required = layer.get("required")
    action = layer.get("action")
    frequency = layer.get("frequency")
    evidence_or_reason = layer.get("evidence_or_reason")

    if "required" in layer and not isinstance(required, bool):
        failed_checks.append(f"{layer_name}.required must be true or false.")

    if "action" in layer and action not in VALID_ACTIONS:
        failed_checks.append(f"{layer_name}.action must be one of: {format_valid_actions()}")

    if "frequency" in layer:
        if not isinstance(frequency, str):
            failed_checks.append(f"{layer_name}.frequency must be text.")
        elif not frequency.strip():
            failed_checks.append(f"{layer_name}.frequency must not be empty.")

    if "evidence_or_reason" in layer and not has_text(evidence_or_reason):
        failed_checks.append(f"{layer_name}.evidence_or_reason must not be empty.")

    if isinstance(required, bool) and action in VALID_ACTIONS:
        if required and action == "not_applicable_with_reason":
            failed_checks.append(
                f"{layer_name}.action cannot be not_applicable_with_reason when required is true."
            )
        if not required and action not in OPTIONAL_LAYER_ACTIONS:
            failed_checks.append(
                f"{layer_name}.action must be not_applicable_with_reason or "
                "scheduled_later_with_reason when required is false."
            )

    status = TEST_LAYER_FAILED if failed_checks else TEST_LAYER_PASSED

    return {
        "status": status,
        "required": required,
        "action": action,
        "frequency": frequency,
        "evidence_or_reason": evidence_or_reason,
        "failed_checks": failed_checks,
    }


def has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def format_valid_actions() -> str:
    return ", ".join(sorted(VALID_ACTIONS))


def build_next_action(status: str) -> str:
    if status == TEST_LAYER_PASSED:
        return "Continue to the quality gate or finalize-story workflow."

    return "Fix the failed test layer checks, then run test-layers again."


def write_test_layer_result(path: Path, result: TestLayerResult) -> None:
    data = {
        "story": result.story,
        "status": result.status,
        "passed_checks": result.passed_checks,
        "failed_checks": result.failed_checks,
        "layers": result.layers,
        "next_action": result.next_action,
    }

    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def write_test_layer_report(path: Path, result: TestLayerResult) -> None:
    content = f"""# Test Layer Report

## Story

{result.story}

## Final status

{result.status}

## Beginner-friendly explanation

Story test plans describe the testing layers that must be considered before review. A story does
not need a brand-new test in every layer, but it must say whether each layer is required, what
action was taken or planned, how often it should run, and what evidence or reason supports that
choice.

## Test layers

{format_layer_sections(result.layers)}
## Passed checks

{format_check_list(result.passed_checks)}
## Failed checks

{format_check_list(result.failed_checks)}
## Next recommended action

{result.next_action}
"""

    path.write_text(content, encoding="utf-8")


def format_layer_sections(layers: dict[str, dict[str, Any]]) -> str:
    if not layers:
        return "- Legacy test plan format detected. No test layer details were validated.\n\n"

    sections: list[str] = []
    for layer_name in TEST_LAYER_NAMES:
        layer = layers.get(layer_name, {})
        sections.extend(
            [
                f"### {layer_name}",
                "",
                TEST_LAYER_EXPLANATIONS[layer_name],
                "",
                f"- Validation status: {layer.get('status', TEST_LAYER_FAILED)}",
                f"- Required: {layer.get('required')}",
                f"- Action: {layer.get('action')}",
                f"- Frequency: {layer.get('frequency')}",
                f"- Evidence or reason: {layer.get('evidence_or_reason')}",
                "",
            ]
        )
    return "\n".join(sections)


def format_check_list(checks: list[str]) -> str:
    if not checks:
        return "- None\n"

    return "\n".join(f"- {check}" for check in checks) + "\n"
