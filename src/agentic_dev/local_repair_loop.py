from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

import yaml

from agentic_dev.local_model_runtime import (
    LocalModelHttpClient,
    call_local_model,
    extract_response_text,
    load_local_model_runtime_config,
)
from agentic_dev.review_bundle import CommandResult, format_command_output, run_command


LOCAL_REPAIR_LOOP_FOLDER = Path("reports") / "local_repair_loop"
DEFAULT_MAX_LOCAL_ATTEMPTS = 3
DEFAULT_MAX_CLOUD_ATTEMPTS = 0
DEFAULT_MAX_CODEX_ATTEMPTS = 0
REPAIR_PLAN_FILENAME = "repair_plan.yaml"
REPAIR_RESULT_FILENAME = "repair_result.yaml"
MANUAL_SUPPORT_REPORT_FILENAME = "manual_support_report.yaml"
REPAIR_POLICY_LINES = [
    "Return the complete corrected file only.",
    "No markdown.",
    "No explanation.",
    "No code fences.",
    "Preserve the public API unless the failure explicitly requires changing it.",
    "Do not change unrelated behavior.",
    "Do not add network calls.",
    "Do not add live APIs.",
    "Do not add trading, wallet, private key, signing, or deployment logic.",
    "Keep the repair local-only.",
]
BANNED_DOMAIN_TERMS = (
    "wallet",
    "private key",
    "private-key",
    "signing",
    "deployment",
    "deploy",
    "live defi",
    "live-defi",
    "trading",
    "exchange api",
    "cloud model",
)


class RepairFailureKind(str, Enum):
    REPAIR_ACCEPTED = "repair_accepted"
    EMPTY_LOCAL_OUTPUT = "empty_local_output"
    MALFORMED_OUTPUT = "malformed_output"
    MARKDOWN_FENCE_IN_STRICT_PYTHON = "markdown_fence_in_strict_python"
    MISSING_REQUIRED_API = "missing_required_api"
    WRONG_TARGET_PATH = "wrong_target_path"
    WRONG_DOMAIN = "wrong_domain"
    RUFF_FAILURE = "ruff_failure"
    PYTEST_FAILURE = "pytest_failure"
    CONTRACT_VIOLATION = "contract_violation"
    UNCLEAR_ACCEPTANCE_CRITERIA = "unclear_acceptance_criteria"
    RETRY_BUDGET_EXCEEDED = "retry_budget_exceeded"


class RepairOwner(str, Enum):
    DEVELOPER = "developer"
    TEST = "test"
    MANUAL_SUPPORT = "manual_support"


@dataclass(frozen=True)
class OutputValidationResult:
    passed: bool
    failure_kind: RepairFailureKind | None
    owner: RepairOwner | None
    reason: str
    normalized_output: str
    stripped_code_fence: bool = False


@dataclass(frozen=True)
class RepairPromptInputs:
    story: str
    story_contract: str
    current_file_path: Path
    current_file_content: str
    failure_output: str
    required_api_strings: tuple[str, ...]
    repair_policy: str
    owner: RepairOwner
    failure_kind: RepairFailureKind
    strict_python: bool


@dataclass(frozen=True)
class RepairAttempt:
    attempt_number: int
    local_attempt_count: int
    cloud_attempt_count: int
    codex_used: bool
    failure_kind: RepairFailureKind
    owner: RepairOwner
    prompt_path: Path
    output_path: Path | None
    validation_result: OutputValidationResult
    applied: bool
    reason: str
    retry_budget_status: str
    command_results: dict[str, CommandResult] | None = None


@dataclass(frozen=True)
class RepairLoopConfig:
    project_path: Path
    story: str
    target_path: Path
    tests: tuple[Path, ...] = ()
    failure_output_path: Path | None = None
    required_api_strings: tuple[str, ...] = ()
    execute: bool = False
    max_local_attempts: int = DEFAULT_MAX_LOCAL_ATTEMPTS
    max_cloud_attempts: int = DEFAULT_MAX_CLOUD_ATTEMPTS
    max_codex_attempts: int = DEFAULT_MAX_CODEX_ATTEMPTS
    strict_python: bool | None = None


@dataclass(frozen=True)
class RepairLoopResult:
    story: str
    target_path: Path
    story_path: Path
    prompt_path: Path
    plan_path: Path
    result_path: Path
    attempts: list[RepairAttempt]
    classification: "FailureClassification"
    status: str
    applied: bool
    applied_path: Path | None
    manual_support_report_path: Path | None

    @property
    def terminal_summary(self) -> str:
        lines = [
            f"Local repair loop for {self.story}:",
            f"Status: {self.status}",
            f"Target: {self.target_path}",
            f"Prompt: {self.prompt_path}",
            f"Plan: {self.plan_path}",
            f"Result: {self.result_path}",
            f"Attempts: {len(self.attempts)}",
            f"Classification: {self.classification.kind.value} ({self.classification.owner.value})",
        ]
        if self.applied_path is not None:
            lines.append(f"Applied path: {self.applied_path}")
        if self.manual_support_report_path is not None:
            lines.append(f"Manual support report: {self.manual_support_report_path}")
        return "\n".join(lines)


@dataclass(frozen=True)
class FailureClassification:
    kind: RepairFailureKind
    owner: RepairOwner
    reason: str
    manual_support_required: bool = False


def run_local_repair_loop(
    project_path: Path,
    story: str,
    target: Path,
    *,
    tests: Sequence[Path] = (),
    failure_output: Path | None = None,
    required_api: Sequence[str] = (),
    execute: bool = False,
    max_local_attempts: int = DEFAULT_MAX_LOCAL_ATTEMPTS,
    max_cloud_attempts: int = DEFAULT_MAX_CLOUD_ATTEMPTS,
    max_codex_attempts: int = DEFAULT_MAX_CODEX_ATTEMPTS,
    strict_python: bool | None = None,
    http_client: LocalModelHttpClient | None = None,
    command_runner=run_command,
) -> RepairLoopResult:
    resolved_project_path = project_path.resolve()
    story_path = resolved_project_path / "stories" / story
    if not story_path.exists() or not story_path.is_dir():
        raise FileNotFoundError(f"Story folder does not exist: {story_path}")

    resolved_target = validate_target_path(resolved_project_path, target)
    resolved_tests = tuple(validate_target_path(resolved_project_path, test_path) for test_path in tests)
    if failure_output is not None and not failure_output.resolve().exists():
        raise FileNotFoundError(f"Failure output file does not exist: {failure_output.resolve()}")

    strict_mode = is_python_file(resolved_target) if strict_python is None else strict_python
    story_contract = load_story_contract(story_path)
    failure_output_text = read_optional_text(failure_output)
    initial_classification = classify_available_failure(
        failure_output_text,
        target_path=resolved_target,
        required_api_strings=tuple(required_api),
        strict_python=strict_mode,
        story_contract=story_contract,
    )
    repair_dir = ensure_repair_loop_directory(story_path)
    prompt_path = repair_dir / REPAIR_PLAN_FILENAME.replace("plan", "prompt").replace(".yaml", ".md")
    plan_path = repair_dir / REPAIR_PLAN_FILENAME
    result_path = repair_dir / REPAIR_RESULT_FILENAME
    prompt_inputs = build_repair_prompt_inputs(
        story=story,
        story_contract=story_contract,
        target_path=resolved_target,
        current_file_content=read_optional_text(resolved_target),
        failure_output=failure_output_text,
        required_api_strings=tuple(required_api),
        owner=initial_classification.owner,
        failure_kind=initial_classification.kind,
        strict_python=strict_mode,
    )
    prompt_text = build_repair_prompt(prompt_inputs)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    write_plan_report(
        plan_path,
        story=story,
        target_path=resolved_target,
        tests=resolved_tests,
        failure_output_path=failure_output,
        required_api_strings=tuple(required_api),
        execute=execute,
        classification=initial_classification,
        prompt_path=prompt_path,
        strict_python=strict_mode,
        max_local_attempts=max_local_attempts,
        max_cloud_attempts=max_cloud_attempts,
        max_codex_attempts=max_codex_attempts,
    )

    if not execute:
        result = RepairLoopResult(
            story=story,
            target_path=resolved_target,
            story_path=story_path,
            prompt_path=prompt_path,
            plan_path=plan_path,
            result_path=result_path,
            attempts=[],
            classification=initial_classification,
            status="dry_run",
            applied=False,
            applied_path=None,
            manual_support_report_path=None,
        )
        write_result_report(result)
        return result

    attempts: list[RepairAttempt] = []
    current_prompt_text = prompt_text
    current_prompt_inputs = prompt_inputs
    applied_path: Path | None = None
    manual_support_report_path: Path | None = None

    for attempt_number in range(1, max_local_attempts + 1):
        current_prompt_path = repair_dir / f"repair_prompt_{attempt_number:02d}.md"
        current_prompt_path.write_text(current_prompt_text, encoding="utf-8")
        current_output_path = repair_dir / f"repair_output_{attempt_number:02d}.txt"

        response_text = invoke_local_repair_model(
            resolved_project_path,
            current_prompt_text,
            http_client=http_client,
        )
        current_output_path.write_text(response_text, encoding="utf-8")
        validation_result = validate_repair_output(
            response_text,
            target_path=resolved_target,
            required_api_strings=tuple(required_api),
            strict_python=strict_mode,
        )

        if not validation_result.passed:
            classification = FailureClassification(
                kind=validation_result.failure_kind or RepairFailureKind.MALFORMED_OUTPUT,
                owner=validation_result.owner or RepairOwner.DEVELOPER,
                reason=validation_result.reason,
            )
            attempt = build_attempt(
                attempt_number=attempt_number,
                failure_kind=classification.kind,
                owner=classification.owner,
                prompt_path=current_prompt_path,
                output_path=current_output_path,
                validation_result=validation_result,
                applied=False,
                reason=validation_result.reason,
                retry_budget_status="within_budget"
                if attempt_number < max_local_attempts
                else "exhausted",
            )
            attempts.append(attempt)
            write_attempt_report(repair_dir, attempt)

            if attempt_number >= max_local_attempts:
                manual_support_report_path = write_manual_support_report(
                    repair_dir,
                    story=story,
                    target_path=resolved_target,
                    classification=FailureClassification(
                        kind=RepairFailureKind.RETRY_BUDGET_EXCEEDED,
                        owner=RepairOwner.MANUAL_SUPPORT,
                        reason=validation_result.reason,
                        manual_support_required=True,
                    ),
                    attempts=attempts,
                    prompt_path=current_prompt_path,
                    output_path=current_output_path,
                    retry_budget_status="exhausted",
                    requested_clarification=manual_support_clarification(
                        validation_result.reason,
                        current_prompt_inputs,
                    ),
                )
                result = RepairLoopResult(
                    story=story,
                    target_path=resolved_target,
                    story_path=story_path,
                    prompt_path=current_prompt_path,
                    plan_path=plan_path,
                    result_path=result_path,
                    attempts=attempts,
                    classification=FailureClassification(
                        kind=RepairFailureKind.RETRY_BUDGET_EXCEEDED,
                        owner=RepairOwner.MANUAL_SUPPORT,
                        reason=validation_result.reason,
                        manual_support_required=True,
                    ),
                    status="budget_exceeded",
                    applied=False,
                    applied_path=None,
                    manual_support_report_path=manual_support_report_path,
                )
                write_result_report(result)
                return result

            current_prompt_inputs = build_repair_prompt_inputs(
                story=story,
                story_contract=story_contract,
                target_path=resolved_target,
                current_file_content=read_optional_text(resolved_target),
                failure_output=response_text,
                required_api_strings=tuple(required_api),
                owner=classification.owner,
                failure_kind=classification.kind,
                strict_python=strict_mode,
            )
            current_prompt_text = build_repair_prompt(current_prompt_inputs)
            continue

        if should_apply_output(validation_result.normalized_output, resolved_target):
            write_text(resolved_target, validation_result.normalized_output)
            applied_path = resolved_target

        command_results: dict[str, CommandResult] = {}
        latest_failure_text = ""
        if should_run_ruff(resolved_target):
            ruff_result = command_runner(["ruff", "check", resolved_target.name], resolved_target.parent)
            command_results["ruff"] = ruff_result
            if not ruff_result.passed:
                latest_failure_text = format_command_output(ruff_result)

        if not latest_failure_text and resolved_tests:
            pytest_command = ["python", "-m", "pytest", "-q", *[str(path) for path in resolved_tests]]
            pytest_result = command_runner(pytest_command, resolved_project_path)
            command_results["pytest"] = pytest_result
            if not pytest_result.passed:
                latest_failure_text = format_command_output(pytest_result)

        attempt_classification = classification_for_command_results(
            command_results,
            target_path=resolved_target,
            story_contract=story_contract,
        )
        attempt = build_attempt(
            attempt_number=attempt_number,
            failure_kind=attempt_classification.kind,
            owner=attempt_classification.owner,
            prompt_path=current_prompt_path,
            output_path=current_output_path,
            validation_result=validation_result,
            applied=True,
            reason=attempt_classification.reason,
            retry_budget_status="within_budget",
            command_results=command_results or None,
        )
        attempts.append(attempt)
        write_attempt_report(repair_dir, attempt)

        if not latest_failure_text:
            result = RepairLoopResult(
                story=story,
                target_path=resolved_target,
                story_path=story_path,
                prompt_path=current_prompt_path,
                plan_path=plan_path,
                result_path=result_path,
                attempts=attempts,
                classification=attempt_classification,
                status="completed",
                applied=True,
                applied_path=applied_path,
                manual_support_report_path=None,
            )
            write_result_report(result)
            return result

        if attempt_number >= max_local_attempts:
            manual_support_report_path = write_manual_support_report(
                repair_dir,
                story=story,
                target_path=resolved_target,
                classification=FailureClassification(
                    kind=RepairFailureKind.RETRY_BUDGET_EXCEEDED,
                    owner=RepairOwner.MANUAL_SUPPORT,
                    reason=latest_failure_text,
                    manual_support_required=True,
                ),
                attempts=attempts,
                prompt_path=current_prompt_path,
                output_path=current_output_path,
                retry_budget_status="exhausted",
                requested_clarification=manual_support_clarification(latest_failure_text, current_prompt_inputs),
            )
            result = RepairLoopResult(
                story=story,
                target_path=resolved_target,
                story_path=story_path,
                prompt_path=current_prompt_path,
                plan_path=plan_path,
                result_path=result_path,
                attempts=attempts,
                classification=FailureClassification(
                    kind=RepairFailureKind.RETRY_BUDGET_EXCEEDED,
                    owner=RepairOwner.MANUAL_SUPPORT,
                    reason=latest_failure_text,
                    manual_support_required=True,
                ),
                status="budget_exceeded",
                applied=True,
                applied_path=applied_path,
                manual_support_report_path=manual_support_report_path,
            )
            write_result_report(result)
            return result

        current_prompt_inputs = build_repair_prompt_inputs(
            story=story,
            story_contract=story_contract,
            target_path=resolved_target,
            current_file_content=read_optional_text(resolved_target),
            failure_output=latest_failure_text,
            required_api_strings=tuple(required_api),
            owner=attempt_classification.owner,
            failure_kind=attempt_classification.kind,
            strict_python=strict_mode,
        )
        current_prompt_text = build_repair_prompt(current_prompt_inputs)

    result = RepairLoopResult(
        story=story,
        target_path=resolved_target,
        story_path=story_path,
        prompt_path=repair_dir / f"repair_prompt_{max_local_attempts:02d}.md",
        plan_path=plan_path,
        result_path=result_path,
        attempts=attempts,
        classification=FailureClassification(
            kind=RepairFailureKind.RETRY_BUDGET_EXCEEDED,
            owner=RepairOwner.MANUAL_SUPPORT,
            reason="Retry budget exhausted without a successful repair.",
            manual_support_required=True,
        ),
        status="budget_exceeded",
        applied=bool(applied_path),
        applied_path=applied_path,
        manual_support_report_path=manual_support_report_path,
    )
    write_result_report(result)
    return result


def build_repair_prompt_inputs(
    *,
    story: str,
    story_contract: str,
    target_path: Path,
    current_file_content: str,
    failure_output: str,
    required_api_strings: tuple[str, ...],
    owner: RepairOwner,
    failure_kind: RepairFailureKind,
    strict_python: bool,
) -> RepairPromptInputs:
    return RepairPromptInputs(
        story=story,
        story_contract=story_contract,
        current_file_path=target_path,
        current_file_content=current_file_content,
        failure_output=failure_output,
        required_api_strings=required_api_strings,
        repair_policy="\n".join(f"- {line}" for line in REPAIR_POLICY_LINES),
        owner=owner,
        failure_kind=failure_kind,
        strict_python=strict_python,
    )


def build_repair_prompt(inputs: RepairPromptInputs) -> str:
    required_api_lines = (
        "\n".join(f"- {value}" for value in inputs.required_api_strings)
        if inputs.required_api_strings
        else "- None supplied"
    )
    current_file_display = inputs.current_file_content if inputs.current_file_content else "<empty file>"
    failure_display = inputs.failure_output if inputs.failure_output else "<no failure output supplied>"
    strict_python_note = "true" if inputs.strict_python else "false"

    return "\n".join(
        [
            "# Local Repair Loop Prompt",
            "",
            f"Story: {inputs.story}",
            f"Owner: {inputs.owner.value}",
            f"Failure kind: {inputs.failure_kind.value}",
            f"Target file: {inputs.current_file_path.as_posix()}",
            f"Strict Python output expected: {strict_python_note}",
            "",
            "## Repair Policy",
            "",
            inputs.repair_policy,
            "",
            "## Required Public API Strings",
            "",
            required_api_lines,
            "",
            "## Story Contract",
            "",
            fenced_text(inputs.story_contract or "<no story contract available>", "yaml"),
            "",
            "## Current File Content",
            "",
            fenced_text(current_file_display, "python" if inputs.strict_python else "text"),
            "",
            "## Exact Failure Output",
            "",
            fenced_text(failure_display, "text"),
            "",
            "## Output Rules",
            "",
            "- Return the complete corrected file only.",
            "- Do not use markdown.",
            "- Do not explain the changes.",
            "- Do not use code fences.",
            "- Preserve the public API unless the failure explicitly requires changing it.",
            "- Do not change unrelated behavior.",
            "- Do not add network calls, live APIs, trading logic, wallet logic, private key logic, signing logic, or deployment logic.",
            "- Keep the answer local-only and file-complete.",
            "",
        ],
    )


def validate_repair_output(
    output_text: str,
    *,
    target_path: Path,
    required_api_strings: tuple[str, ...],
    strict_python: bool,
) -> OutputValidationResult:
    stripped = output_text.strip()
    if not stripped:
        return OutputValidationResult(
            passed=False,
            failure_kind=RepairFailureKind.EMPTY_LOCAL_OUTPUT,
            owner=RepairOwner.DEVELOPER,
            reason="Local model returned an empty output.",
            normalized_output="",
        )

    if strict_python and looks_like_markdown_fence(stripped):
        return OutputValidationResult(
            passed=False,
            failure_kind=RepairFailureKind.MARKDOWN_FENCE_IN_STRICT_PYTHON,
            owner=RepairOwner.DEVELOPER,
            reason="Strict Python output was fenced in markdown.",
            normalized_output="",
        )

    normalized_output, stripped_code_fence, fence_error = normalize_repair_output(
        stripped,
        allow_code_fence=not strict_python,
    )
    if fence_error is not None:
        return OutputValidationResult(
            passed=False,
            failure_kind=RepairFailureKind.MALFORMED_OUTPUT,
            owner=RepairOwner.DEVELOPER,
            reason=fence_error,
            normalized_output="",
        )

    if not normalized_output.strip():
        return OutputValidationResult(
            passed=False,
            failure_kind=RepairFailureKind.EMPTY_LOCAL_OUTPUT,
            owner=RepairOwner.DEVELOPER,
            reason="Local model returned an empty output after normalization.",
            normalized_output="",
        )

    missing_required = [value for value in required_api_strings if value not in normalized_output]
    if missing_required:
        return OutputValidationResult(
            passed=False,
            failure_kind=RepairFailureKind.MISSING_REQUIRED_API,
            owner=RepairOwner.DEVELOPER,
            reason="Missing required public API string(s): " + ", ".join(missing_required),
            normalized_output=normalized_output,
            stripped_code_fence=stripped_code_fence,
        )

    banned_domain = detect_banned_domain_terms(normalized_output)
    if banned_domain is not None:
        return OutputValidationResult(
            passed=False,
            failure_kind=RepairFailureKind.WRONG_DOMAIN,
            owner=RepairOwner.DEVELOPER,
            reason=f"Output appears to target a disallowed domain: {banned_domain}.",
            normalized_output=normalized_output,
            stripped_code_fence=stripped_code_fence,
        )

    return OutputValidationResult(
        passed=True,
        failure_kind=None,
        owner=None,
        reason="Output accepted.",
        normalized_output=normalized_output,
        stripped_code_fence=stripped_code_fence,
    )


def normalize_repair_output(output_text: str, *, allow_code_fence: bool) -> tuple[str, bool, str | None]:
    if not allow_code_fence:
        return output_text, False, None

    if not looks_like_markdown_fence(output_text):
        return output_text, False, None

    lines = output_text.splitlines()
    if len(lines) < 2:
        return "", False, "Markdown fence was incomplete."

    opening = lines[0].strip()
    closing = lines[-1].strip()
    if not opening.startswith("```") or closing != "```":
        return "", False, "Markdown fence must be a single outer fence with no prose outside it."

    body = "\n".join(lines[1:-1]).strip()
    return body, True, None


def classify_available_failure(
    failure_output_text: str,
    *,
    target_path: Path,
    required_api_strings: tuple[str, ...],
    strict_python: bool,
    story_contract: str,
) -> FailureClassification:
    if not story_contract.strip():
        return FailureClassification(
            kind=RepairFailureKind.UNCLEAR_ACCEPTANCE_CRITERIA,
            owner=RepairOwner.MANUAL_SUPPORT,
            reason="Story contract is missing or empty.",
            manual_support_required=True,
        )

    validation = validate_repair_output(
        failure_output_text,
        target_path=target_path,
        required_api_strings=required_api_strings,
        strict_python=strict_python,
    )
    if validation.passed:
        return FailureClassification(
            kind=RepairFailureKind.CONTRACT_VIOLATION,
            owner=RepairOwner.DEVELOPER,
            reason="Failure output does not indicate a local-model contract problem.",
        )

    if validation.failure_kind in {
        RepairFailureKind.EMPTY_LOCAL_OUTPUT,
        RepairFailureKind.MALFORMED_OUTPUT,
        RepairFailureKind.MARKDOWN_FENCE_IN_STRICT_PYTHON,
        RepairFailureKind.MISSING_REQUIRED_API,
        RepairFailureKind.WRONG_DOMAIN,
    }:
        return FailureClassification(
            kind=validation.failure_kind,
            owner=validation.owner or RepairOwner.DEVELOPER,
            reason=validation.reason,
        )

    return FailureClassification(
        kind=RepairFailureKind.CONTRACT_VIOLATION,
        owner=RepairOwner.DEVELOPER,
        reason=validation.reason,
    )


def classify_ruff_failure(failure_output: str, *, target_path: Path) -> FailureClassification:
    lowered = failure_output.lower()
    if "fixture" in lowered or "importerror" in lowered or "cannot import name" in lowered:
        return FailureClassification(
            kind=RepairFailureKind.CONTRACT_VIOLATION,
            owner=RepairOwner.TEST,
            reason="Ruff output suggests a test import or fixture problem.",
        )
    if target_path.parts and "tests" in target_path.parts:
        return FailureClassification(
            kind=RepairFailureKind.RUFF_FAILURE,
            owner=RepairOwner.TEST,
            reason="Ruff failure is affecting test code.",
        )
    return FailureClassification(
        kind=RepairFailureKind.RUFF_FAILURE,
        owner=RepairOwner.DEVELOPER,
        reason="Ruff failure affected source code.",
    )


def classify_pytest_failure(failure_output: str, *, target_path: Path) -> FailureClassification:
    lowered = failure_output.lower()
    if any(
        phrase in lowered
        for phrase in (
            "fixture '",
            "fixture \"",
            "importerror while importing test module",
            "module not found",
            "cannot import name",
            "attributeerror: module",
        )
    ):
        return FailureClassification(
            kind=RepairFailureKind.PYTEST_FAILURE,
            owner=RepairOwner.TEST,
            reason="Pytest failure points to test fixture or import wiring.",
        )
    if "assert" in lowered or "failed" in lowered:
        return FailureClassification(
            kind=RepairFailureKind.PYTEST_FAILURE,
            owner=RepairOwner.DEVELOPER,
            reason="Pytest failure points to implementation behavior.",
        )
    return FailureClassification(
        kind=RepairFailureKind.PYTEST_FAILURE,
        owner=RepairOwner.DEVELOPER,
        reason=f"Pytest failed while checking {target_path.as_posix()}.",
    )


def classification_for_command_results(
    command_results: dict[str, CommandResult],
    *,
    target_path: Path,
    story_contract: str,
) -> FailureClassification:
    if "ruff" in command_results and not command_results["ruff"].passed:
        return classify_ruff_failure(
            format_command_output(command_results["ruff"]),
            target_path=target_path,
        )
    if "pytest" in command_results and not command_results["pytest"].passed:
        return classify_pytest_failure(
            format_command_output(command_results["pytest"]),
            target_path=target_path,
        )
    if not story_contract.strip():
        return FailureClassification(
            kind=RepairFailureKind.UNCLEAR_ACCEPTANCE_CRITERIA,
            owner=RepairOwner.MANUAL_SUPPORT,
            reason="Story contract is missing or empty.",
            manual_support_required=True,
        )
    return FailureClassification(
        kind=RepairFailureKind.REPAIR_ACCEPTED,
        owner=RepairOwner.DEVELOPER,
        reason="Validated output was accepted and no requested checks failed.",
    )


def validate_target_path(project_path: Path, target_path: Path) -> Path:
    resolved_project = project_path.resolve()
    resolved_target = target_path if target_path.is_absolute() else resolved_project / target_path
    resolved_target = resolved_target.resolve(strict=False)
    if not is_relative_to(resolved_target, resolved_project):
        raise ValueError(f"Target path must stay inside the project: {target_path}")
    return resolved_target


def should_apply_output(normalized_output: str, target_path: Path) -> bool:
    return bool(normalized_output.strip()) and target_path is not None


def should_run_ruff(target_path: Path) -> bool:
    return target_path.suffix == ".py"


def invoke_local_repair_model(
    project_path: Path,
    prompt_text: str,
    *,
    http_client: LocalModelHttpClient | None = None,
) -> str:
    _, config = load_local_model_runtime_config(project_path)
    response = call_local_model(config, prompt_text, http_client)
    response_text = extract_response_text(response)
    if not response_text.strip():
        raise ValueError("Local model returned an empty output.")
    return response_text


def ensure_repair_loop_directory(story_path: Path) -> Path:
    repair_dir = story_path / LOCAL_REPAIR_LOOP_FOLDER
    repair_dir.mkdir(parents=True, exist_ok=True)
    (repair_dir / ".gitkeep").touch()
    return repair_dir


def load_story_contract(story_path: Path) -> str:
    sections: list[str] = []
    for relative_path in ("story.md", "status.yaml", "test_plan.yaml", "monitoring_plan.yaml"):
        source_path = story_path / relative_path
        if not source_path.exists():
            continue
        content = source_path.read_text(encoding="utf-8")
        sections.extend(
            [
                f"## {relative_path}",
                "",
                fenced_text(content.rstrip(), "yaml" if source_path.suffix in {".yaml", ".yml"} else "text"),
                "",
            ],
        )
    return "\n".join(sections).strip()


def manual_support_clarification(reason: str, prompt_inputs: RepairPromptInputs) -> str:
    required_api = ", ".join(prompt_inputs.required_api_strings) or "none"
    return (
        "Human review is needed to clarify the accepted file shape and retry boundary. "
        f"Reason: {reason}. "
        f"Target: {prompt_inputs.current_file_path.as_posix()}. "
        f"Required API strings: {required_api}."
    )


def write_plan_report(
    plan_path: Path,
    *,
    story: str,
    target_path: Path,
    tests: Sequence[Path],
    failure_output_path: Path | None,
    required_api_strings: tuple[str, ...],
    execute: bool,
    classification: FailureClassification,
    prompt_path: Path,
    strict_python: bool,
    max_local_attempts: int,
    max_cloud_attempts: int,
    max_codex_attempts: int,
) -> None:
    plan = {
        "story": story,
        "target_path": target_path.as_posix(),
        "tests": [path.as_posix() for path in tests],
        "failure_output_path": failure_output_path.resolve().as_posix() if failure_output_path else None,
        "required_api_strings": list(required_api_strings),
        "execute": execute,
        "prompt_path": prompt_path.as_posix(),
        "strict_python": strict_python,
        "classification": classification_payload(classification),
        "retry_budget": {
            "max_local_attempts": max_local_attempts,
            "max_cloud_attempts": max_cloud_attempts,
            "max_codex_attempts": max_codex_attempts,
        },
        "cloud_policy": "manual-only",
        "codex_policy": "disabled-by-default",
        "safety": [
            "No automatic cloud model calls.",
            "No automatic Codex calls.",
            "No live trading, wallet, signing, or deployment logic.",
        ],
        "actions": [
            "Classify available failure evidence.",
            "Write a repair prompt.",
            "Run the local model only when execute mode is enabled.",
            "Apply only a fully validated output.",
            "Write a manual support report instead of escalating automatically when budgets are exceeded.",
        ],
    }
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")


def write_attempt_report(repair_dir: Path, attempt: RepairAttempt) -> Path:
    attempt_path = repair_dir / f"repair_attempt_{attempt.attempt_number:02d}.yaml"
    payload = {
        "attempt_number": attempt.attempt_number,
        "local_attempt_count": attempt.local_attempt_count,
        "cloud_attempt_count": attempt.cloud_attempt_count,
        "codex_used": attempt.codex_used,
        "failure_kind": attempt.failure_kind.value,
        "owner": attempt.owner.value,
        "prompt_path": attempt.prompt_path.as_posix(),
        "output_path": attempt.output_path.as_posix() if attempt.output_path else None,
        "validation_result": {
            "passed": attempt.validation_result.passed,
            "failure_kind": (
                attempt.validation_result.failure_kind.value
                if attempt.validation_result.failure_kind is not None
                else None
            ),
            "owner": (
                attempt.validation_result.owner.value
                if attempt.validation_result.owner is not None
                else None
            ),
            "reason": attempt.validation_result.reason,
            "normalized_output": attempt.validation_result.normalized_output,
            "stripped_code_fence": attempt.validation_result.stripped_code_fence,
        },
        "applied": attempt.applied,
        "reason": attempt.reason,
        "retry_budget_status": attempt.retry_budget_status,
    }
    if attempt.command_results:
        payload["command_results"] = {
            name: {
                "command": result.command,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            for name, result in attempt.command_results.items()
        }
    attempt_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return attempt_path


def write_result_report(result: RepairLoopResult) -> None:
    payload = {
        "story": result.story,
        "target_path": result.target_path.as_posix(),
        "story_path": result.story_path.as_posix(),
        "prompt_path": result.prompt_path.as_posix(),
        "plan_path": result.plan_path.as_posix(),
        "result_path": result.result_path.as_posix(),
        "status": result.status,
        "applied": result.applied,
        "applied_path": result.applied_path.as_posix() if result.applied_path else None,
        "manual_support_report_path": (
            result.manual_support_report_path.as_posix()
            if result.manual_support_report_path
            else None
        ),
        "classification": classification_payload(result.classification),
        "attempts": [attempt.attempt_number for attempt in result.attempts],
    }
    result.result_path.parent.mkdir(parents=True, exist_ok=True)
    result.result_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def write_manual_support_report(
    repair_dir: Path,
    *,
    story: str,
    target_path: Path,
    classification: FailureClassification,
    attempts: list[RepairAttempt],
    prompt_path: Path,
    output_path: Path,
    retry_budget_status: str,
    requested_clarification: str,
) -> Path:
    report_path = repair_dir / MANUAL_SUPPORT_REPORT_FILENAME
    payload = {
        "story": story,
        "target_path": target_path.as_posix(),
        "failure_kind": classification.kind.value,
        "owner": classification.owner.value,
        "reason": classification.reason,
        "retry_budget_status": retry_budget_status,
        "local_attempt_count": len(attempts),
        "cloud_attempt_count": 0,
        "codex_used": False,
        "prompt_path": prompt_path.as_posix(),
        "output_path": output_path.as_posix(),
        "requested_clarification": requested_clarification,
        "attempts": [
            {
                "attempt_number": attempt.attempt_number,
                "failure_kind": attempt.failure_kind.value,
                "owner": attempt.owner.value,
                "reason": attempt.reason,
                "prompt_path": attempt.prompt_path.as_posix(),
                "output_path": attempt.output_path.as_posix() if attempt.output_path else None,
                "applied": attempt.applied,
                "retry_budget_status": attempt.retry_budget_status,
            }
            for attempt in attempts
        ],
        "cloud_escalation": "manual-only",
        "codex_escalation": "disabled-by-default",
    }
    report_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return report_path


def build_attempt(
    *,
    attempt_number: int,
    failure_kind: RepairFailureKind,
    owner: RepairOwner,
    prompt_path: Path,
    output_path: Path | None,
    validation_result: OutputValidationResult,
    applied: bool,
    reason: str,
    retry_budget_status: str,
    command_results: dict[str, CommandResult] | None = None,
) -> RepairAttempt:
    return RepairAttempt(
        attempt_number=attempt_number,
        local_attempt_count=attempt_number,
        cloud_attempt_count=0,
        codex_used=False,
        failure_kind=failure_kind,
        owner=owner,
        prompt_path=prompt_path,
        output_path=output_path,
        validation_result=validation_result,
        applied=applied,
        reason=reason,
        retry_budget_status=retry_budget_status,
        command_results=command_results,
    )


def classification_payload(classification: FailureClassification) -> dict[str, Any]:
    return {
        "kind": classification.kind.value,
        "owner": classification.owner.value,
        "reason": classification.reason,
        "manual_support_required": classification.manual_support_required,
    }


def read_optional_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def fenced_text(content: str, language: str) -> str:
    return "\n".join([f"~~~{language}", content, "~~~"])


def looks_like_markdown_fence(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def detect_banned_domain_terms(text: str) -> str | None:
    lowered = text.lower()
    for term in BANNED_DOMAIN_TERMS:
        if term in lowered:
            return term
    return None


def is_python_file(path: Path) -> bool:
    return path.suffix in {".py", ".pyi"}


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def format_repair_attempt_summary(attempt: RepairAttempt) -> str:
    lines = [
        f"Attempt {attempt.attempt_number}:",
        f"  failure_kind: {attempt.failure_kind.value}",
        f"  owner: {attempt.owner.value}",
        f"  applied: {attempt.applied}",
        f"  retry_budget_status: {attempt.retry_budget_status}",
        f"  reason: {attempt.reason}",
        f"  prompt_path: {attempt.prompt_path}",
    ]
    if attempt.output_path is not None:
        lines.append(f"  output_path: {attempt.output_path}")
    if attempt.command_results:
        for name, result in attempt.command_results.items():
            lines.append(f"  {name}: {'passed' if result.passed else 'failed'}")
    return "\n".join(lines)


def execute_or_plan_summary(result: RepairLoopResult) -> str:
    lines = [result.terminal_summary]
    if result.attempts:
        lines.append("")
        lines.extend(format_repair_attempt_summary(attempt) for attempt in result.attempts)
    return "\n".join(lines)
