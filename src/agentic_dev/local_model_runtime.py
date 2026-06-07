from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from agentic_dev.runtime_config import load_runtime_config


LOCAL_MODEL_PROVIDER = "local_openai_compatible"
DEFAULT_DRY_RUN_PROMPT = "Reply with LOCAL_MODEL_OK only."
DRY_RUN_REPORT_RELATIVE_PATH = Path("reports") / "local_model_dry_run_report.md"


class LocalModelHttpClient(Protocol):
    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        """Send JSON to the configured local model endpoint."""


class UrllibLocalModelHttpClient:
    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.URLError as error:
            raise ValueError(f"Local model request failed: {error}") from error

        try:
            loaded = json.loads(response_body)
        except json.JSONDecodeError as error:
            raise ValueError("Local model response was not valid JSON.") from error

        if not isinstance(loaded, dict):
            raise ValueError("Local model response must be a JSON object.")

        return loaded


@dataclass(frozen=True)
class LocalModelRuntimeConfig:
    enabled: bool
    provider: str
    base_url: str
    model: str
    timeout_seconds: int
    api_key_env: str | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


@dataclass(frozen=True)
class LocalModelValidationResult:
    config_path: Path
    configured: bool
    errors: list[str]

    @property
    def passed(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class LocalModelCallResult:
    config_path: Path
    report_path: Path | None
    response_text: str
    raw_response: dict[str, Any]


def validate_local_model_runtime_config(project_path: Path) -> LocalModelValidationResult:
    config_path, runtime_config = load_runtime_config(project_path)
    errors: list[str] = []
    section = runtime_config.get("local_model_runtime")

    if section is None:
        return LocalModelValidationResult(
            config_path=config_path,
            configured=False,
            errors=[],
        )

    parse_local_model_runtime_config(section, errors)

    return LocalModelValidationResult(
        config_path=config_path,
        configured=True,
        errors=errors,
    )


def load_local_model_runtime_config(project_path: Path) -> tuple[Path, LocalModelRuntimeConfig]:
    config_path, runtime_config = load_runtime_config(project_path)
    section = runtime_config.get("local_model_runtime")

    if section is None:
        raise ValueError("local_model_runtime must be configured before calling a local model.")

    errors: list[str] = []
    parsed = parse_local_model_runtime_config(section, errors)

    if errors or parsed is None:
        raise ValueError("Local model runtime validation failed:\n- " + "\n- ".join(errors))

    if not parsed.enabled:
        raise ValueError("local_model_runtime.enabled must be true before calling a local model.")

    return config_path, parsed


def parse_local_model_runtime_config(
    section: Any,
    errors: list[str],
) -> LocalModelRuntimeConfig | None:
    if not isinstance(section, dict):
        errors.append("local_model_runtime must be a mapping.")
        return None

    enabled = section.get("enabled")
    provider = required_string(section, "provider", errors)
    base_url = required_string(section, "base_url", errors)
    model = required_string(section, "model", errors)
    timeout_seconds = section.get("timeout_seconds")

    if not isinstance(enabled, bool):
        errors.append("local_model_runtime.enabled must be a boolean.")

    if provider and provider != LOCAL_MODEL_PROVIDER:
        errors.append(
            "local_model_runtime.provider must be local_openai_compatible.",
        )

    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        errors.append("local_model_runtime.timeout_seconds must be an integer.")
    elif timeout_seconds <= 0:
        errors.append("local_model_runtime.timeout_seconds must be greater than 0.")

    api_key_env = optional_string(section, "api_key_env", errors)
    max_output_tokens = optional_positive_int(section, "max_output_tokens", errors)
    temperature = optional_number(section, "temperature", errors)

    if errors:
        return None

    return LocalModelRuntimeConfig(
        enabled=enabled,
        provider=provider,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        api_key_env=api_key_env,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )


def run_local_model_dry_run(
    project_path: Path,
    prompt: str = DEFAULT_DRY_RUN_PROMPT,
    http_client: LocalModelHttpClient | None = None,
) -> LocalModelCallResult:
    resolved_project_path = project_path.resolve()
    config_path, config = load_local_model_runtime_config(resolved_project_path)
    response = call_local_model(config, prompt, http_client)
    response_text = extract_response_text(response)
    report_path = resolved_project_path / DRY_RUN_REPORT_RELATIVE_PATH
    write_dry_run_report(report_path, config_path, config, response_text)

    return LocalModelCallResult(
        config_path=config_path,
        report_path=report_path,
        response_text=response_text,
        raw_response=response,
    )


def run_local_agent_prompt(
    project_path: Path,
    prompt_file: Path,
    output_file: Path,
    http_client: LocalModelHttpClient | None = None,
) -> LocalModelCallResult:
    config_path, config = load_local_model_runtime_config(project_path)
    resolved_prompt_file = prompt_file.resolve()

    if not resolved_prompt_file.exists():
        raise FileNotFoundError(f"Prompt file does not exist: {resolved_prompt_file}")

    prompt = resolved_prompt_file.read_text(encoding="utf-8")
    response = call_local_model(config, prompt, http_client)
    response_text = extract_response_text(response)
    resolved_output_file = output_file.resolve()
    resolved_output_file.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_file.write_text(response_text, encoding="utf-8")

    return LocalModelCallResult(
        config_path=config_path,
        report_path=resolved_output_file,
        response_text=response_text,
        raw_response=response,
    )


def call_local_model(
    config: LocalModelRuntimeConfig,
    prompt: str,
    http_client: LocalModelHttpClient | None = None,
) -> dict[str, Any]:
    client = http_client or UrllibLocalModelHttpClient()
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
    }

    if config.max_output_tokens is not None:
        payload["max_tokens"] = config.max_output_tokens

    if config.temperature is not None:
        payload["temperature"] = config.temperature

    return client.post_json(
        config.chat_completions_url,
        payload,
        build_headers(config),
        config.timeout_seconds,
    )


def build_headers(config: LocalModelRuntimeConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}

    if config.api_key_env:
        api_key = os.environ.get(config.api_key_env)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

    return headers


def extract_response_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")

    if not isinstance(choices, list) or not choices:
        raise ValueError("Local model response must include at least one choice.")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("Local model response choice must be a JSON object.")

    message = first_choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content

    text = first_choice.get("text")
    if isinstance(text, str):
        return text

    raise ValueError("Local model response choice must include message.content or text.")


def write_dry_run_report(
    report_path: Path,
    config_path: Path,
    config: LocalModelRuntimeConfig,
    response_text: str,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# Local Model Dry Run Report",
                "",
                "- Status: PASS",
                f"- Runtime config: {config_path}",
                f"- Provider: {config.provider}",
                f"- Base URL: {config.base_url}",
                f"- Model: {config.model}",
                "- Prompt content: not recorded",
                "- Secret values: not recorded",
                "",
                "## Response",
                "",
                response_text,
                "",
                "## Safety",
                "",
                "This dry run saved a report only. It did not edit source files, execute model "
                "output, commit, push, merge, deploy, call GitHub APIs, or call cloud models.",
                "",
            ],
        ),
        encoding="utf-8",
    )


def format_local_model_validation_result(result: LocalModelValidationResult) -> str:
    if result.passed and result.configured:
        return f"Local model runtime validation passed: {result.config_path}"

    if result.passed:
        return (
            "Local model runtime validation passed: no local_model_runtime section is "
            f"configured in {result.config_path}"
        )

    lines = [
        "Local model runtime validation failed.",
        f"Config: {result.config_path}",
        "",
        "Errors:",
    ]
    lines.extend(f"  - {error}" for error in result.errors)
    return "\n".join(lines)


def required_string(mapping: dict[str, Any], key: str, errors: list[str]) -> str:
    value = mapping.get(key)

    if isinstance(value, str) and value.strip():
        return value.strip()

    errors.append(f"local_model_runtime.{key} must be a non-empty string.")
    return ""


def optional_string(mapping: dict[str, Any], key: str, errors: list[str]) -> str | None:
    value = mapping.get(key)

    if value is None:
        return None

    if isinstance(value, str) and value.strip():
        return value.strip()

    errors.append(f"local_model_runtime.{key} must be a non-empty string when provided.")
    return None


def optional_positive_int(mapping: dict[str, Any], key: str, errors: list[str]) -> int | None:
    value = mapping.get(key)

    if value is None:
        return None

    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value

    errors.append(f"local_model_runtime.{key} must be a positive integer when provided.")
    return None


def optional_number(mapping: dict[str, Any], key: str, errors: list[str]) -> float | None:
    value = mapping.get(key)

    if value is None:
        return None

    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)

    errors.append(f"local_model_runtime.{key} must be a number when provided.")
    return None
