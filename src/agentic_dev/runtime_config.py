from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REQUIRED_AGENT_IDS = (
    "research_agent",
    "planner_agent",
    "developer_agent",
    "test_agent",
    "docs_agent",
    "security_quality_agent",
    "local_reviewer_agent",
    "cloud_reviewer",
)

KNOWN_PROVIDER_TYPES = {
    "codex",
    "local_model_optional",
    "manual_cloud_model",
    "future_api_cloud_model",
}

KNOWN_APPROVAL_MODES = {
    "read_only",
    "workspace_write_with_approval",
    "workspace_write_no_prompt",
    "manual_only",
}

KNOWN_FALLBACK_PROVIDERS = KNOWN_PROVIDER_TYPES | {"human_owner"}

RISKY_COMMAND_REQUIREMENTS = {
    "git push": "git push",
    "git merge": "git merge",
    "git reset --hard": "git reset --hard",
    "deploy": "deploy",
    "secret changes": "secret changes",
}

CODEX_RUNTIME_ALLOWED_COMMANDS = {"codex", "codex.cmd"}
CODEX_RUNTIME_REQUIRED_ARGS = ["exec", "--file", "{task_file}"]
MAX_CODEX_RUNTIME_TIMEOUT_SECONDS = 7200

DEFAULT_RUNTIME_CONFIG = """agents:
  research_agent:
    provider: codex
    model: gpt-5.4-mini
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  planner_agent:
    provider: codex
    model: gpt-5.4
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  developer_agent:
    provider: codex
    model: gpt-5.4
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  test_agent:
    provider: codex
    model: gpt-5.4
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  docs_agent:
    provider: codex
    model: gpt-5.4-mini
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  security_quality_agent:
    provider: codex
    model: gpt-5.5
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  local_reviewer_agent:
    provider: codex
    model: gpt-5.5
    approval_mode: workspace_write_no_prompt
    fallback_provider: manual_cloud_model

  cloud_reviewer:
    provider: manual_cloud_model
    model: main_cloud_model
    approval_mode: manual_only
    fallback_provider: human_owner

  local_model_helper:
    provider: local_model_optional
    model: gemma-4-26b
    prompt_mode: micro
    approval_mode: workspace_write_no_prompt
    fallback_provider: codex

command_policy:
  allowed_without_approval:
    - docker compose build
    - docker compose run --rm dev pytest
    - docker compose run --rm dev ruff check .
    - docker compose run --rm dev agentic generate-stories
    - docker compose run --rm dev agentic prepare-story
    - docker compose run --rm dev agentic build-context
    - docker compose run --rm dev agentic codex-task create
    - docker compose run --rm dev agentic workflow-run
    - docker compose run --rm dev agentic review-bundle
    - docker compose run --rm dev agentic quality-gate
    - docker compose run --rm dev agentic test-layers
    - docker compose run --rm dev agentic finalize-story
    - docker compose run --rm dev agentic artifact-policy
    - docker compose run --rm dev agentic public-readiness
    - docker compose run --rm dev agentic runtime-config validate
    - docker compose run --rm dev agentic project-status

  requires_human_approval:
    - git push
    - git merge
    - git reset --hard
    - git rebase
    - deployment commands
    - secret changes
    - credential changes
    - wallet/private-key actions
    - destructive file deletion

support_policy:
  if_agent_blocked: create_support_ticket
  preferred_responder: cloud_model
  escalate_to_human_when:
    - cloud_model_uncertain
    - business_decision_required
    - security_sensitive_decision
    - real_money_or_deployment_risk

local_model_runtime:
  enabled: false
  provider: local_openai_compatible
  base_url: http://host.docker.internal:1234/v1
  model: qwen3-coder-30b-a3b-instruct
  api_key_env: LOCAL_MODEL_API_KEY
  timeout_seconds: 120
  max_output_tokens: 4096
  temperature: 0.2

codex_runtime:
  enabled: false
  command: codex
  args:
    - exec
    - --file
    - "{task_file}"
  timeout_seconds: 1800

local_model_profiles:
  lm_studio:
    base_url: http://host.docker.internal:1234/v1
    api_key_hint: lm-studio
  ollama:
    base_url: http://host.docker.internal:11434/v1
    api_key_hint: ollama
"""


class IndentedYamlDumper(yaml.SafeDumper):
    """Keep YAML lists indented under their keys for easier reading."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


@dataclass(frozen=True)
class RuntimeConfigValidationResult:
    config_path: Path
    config: dict[str, Any]


@dataclass(frozen=True)
class CodexRuntimeConfig:
    enabled: bool
    command: str
    args: list[str]
    timeout_seconds: int


def runtime_config_path(project_path: Path) -> Path:
    return project_path.resolve() / ".agentic" / "agent_runtime.yaml"


def default_runtime_config_text() -> str:
    return DEFAULT_RUNTIME_CONFIG


def load_runtime_config(project_path: Path) -> tuple[Path, dict[str, Any]]:
    config_path = runtime_config_path(project_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Runtime config does not exist: {config_path}")

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"Runtime config is not valid YAML: {config_path}: {error}") from error

    if not isinstance(loaded, dict):
        raise ValueError(f"Runtime config must be a YAML mapping: {config_path}")

    return config_path, loaded


def show_runtime_config(project_path: Path) -> str:
    _, config = load_runtime_config(project_path)
    return yaml.dump(config, Dumper=IndentedYamlDumper, sort_keys=False, width=1000)


def validate_runtime_config(project_path: Path) -> RuntimeConfigValidationResult:
    config_path, config = load_runtime_config(project_path)
    errors: list[str] = []

    agents = mapping_value(config, "agents", "runtime config", errors)

    for agent_id in REQUIRED_AGENT_IDS:
        agent_config = agents.get(agent_id)
        if not isinstance(agent_config, dict):
            errors.append(f"agents.{agent_id} must exist and be a mapping.")
            continue

        provider = required_string(agent_config, "provider", f"agents.{agent_id}", errors)
        required_string(agent_config, "model", f"agents.{agent_id}", errors)
        approval_mode = required_string(
            agent_config,
            "approval_mode",
            f"agents.{agent_id}",
            errors,
        )
        fallback_provider = required_string(
            agent_config,
            "fallback_provider",
            f"agents.{agent_id}",
            errors,
        )

        if provider and provider not in KNOWN_PROVIDER_TYPES:
            errors.append(
                f"agents.{agent_id}.provider must be one of: "
                f"{', '.join(sorted(KNOWN_PROVIDER_TYPES))}."
            )

        if approval_mode and approval_mode not in KNOWN_APPROVAL_MODES:
            errors.append(
                f"agents.{agent_id}.approval_mode must be one of: "
                f"{', '.join(sorted(KNOWN_APPROVAL_MODES))}."
            )

        if fallback_provider and fallback_provider not in KNOWN_FALLBACK_PROVIDERS:
            errors.append(
                f"agents.{agent_id}.fallback_provider must be one of: "
                f"{', '.join(sorted(KNOWN_FALLBACK_PROVIDERS))}."
            )

        if agent_id == "cloud_reviewer" and provider != "manual_cloud_model":
            errors.append("agents.cloud_reviewer.provider must be manual_cloud_model.")

    command_policy = mapping_value(config, "command_policy", "runtime config", errors)
    allowed_without_approval = string_list_value(
        command_policy,
        "allowed_without_approval",
        "command_policy",
        errors,
    )
    requires_human_approval = string_list_value(
        command_policy,
        "requires_human_approval",
        "command_policy",
        errors,
    )

    for label, required_pattern in RISKY_COMMAND_REQUIREMENTS.items():
        if not contains_command_pattern(requires_human_approval, required_pattern):
            errors.append(
                f"command_policy.requires_human_approval must include an entry covering "
                f"'{label}'."
            )

        if contains_command_pattern(allowed_without_approval, required_pattern):
            errors.append(
                f"command_policy.allowed_without_approval must not include risky command "
                f"'{label}'."
            )

    parse_codex_runtime_config(config.get("codex_runtime"), errors)

    if errors:
        raise ValueError("Runtime config validation failed:\n- " + "\n- ".join(errors))

    return RuntimeConfigValidationResult(config_path=config_path, config=config)


def load_codex_runtime_config(project_path: Path) -> tuple[Path, CodexRuntimeConfig]:
    config_path, config = load_runtime_config(project_path)
    section = config.get("codex_runtime")
    errors: list[str] = []
    parsed = parse_codex_runtime_config(section, errors)

    if section is None:
        raise ValueError("codex_runtime must be configured before invoking Codex.")

    if errors or parsed is None:
        raise ValueError("Codex runtime validation failed:\n- " + "\n- ".join(errors))

    if not parsed.enabled:
        raise ValueError("codex_runtime.enabled must be true before invoking Codex.")

    return config_path, parsed


def parse_codex_runtime_config(
    section: Any,
    errors: list[str],
) -> CodexRuntimeConfig | None:
    if section is None:
        return None

    if not isinstance(section, dict):
        errors.append("codex_runtime must be a mapping.")
        return None

    enabled = section.get("enabled")
    command = section.get("command")
    args = section.get("args")
    timeout_seconds = section.get("timeout_seconds")

    if not isinstance(enabled, bool):
        errors.append("codex_runtime.enabled must be a boolean.")

    if not isinstance(command, str) or not command.strip():
        errors.append("codex_runtime.command must be a non-empty string.")
        command = ""
    else:
        command = command.strip()
        if command not in CODEX_RUNTIME_ALLOWED_COMMANDS:
            allowed = ", ".join(sorted(CODEX_RUNTIME_ALLOWED_COMMANDS))
            errors.append(f"codex_runtime.command must be one of: {allowed}.")

    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        errors.append("codex_runtime.args must be a list of strings.")
        args = []
    elif args != CODEX_RUNTIME_REQUIRED_ARGS:
        errors.append(
            "codex_runtime.args must be exactly: "
            + " ".join(CODEX_RUNTIME_REQUIRED_ARGS)
            + "."
        )

    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        errors.append("codex_runtime.timeout_seconds must be an integer.")
        timeout_seconds = 0
    elif timeout_seconds <= 0:
        errors.append("codex_runtime.timeout_seconds must be greater than 0.")
    elif timeout_seconds > MAX_CODEX_RUNTIME_TIMEOUT_SECONDS:
        errors.append(
            "codex_runtime.timeout_seconds must be less than or equal to "
            f"{MAX_CODEX_RUNTIME_TIMEOUT_SECONDS}."
        )

    if errors:
        return None

    return CodexRuntimeConfig(
        enabled=enabled,
        command=command,
        args=list(args),
        timeout_seconds=timeout_seconds,
    )


def mapping_value(
    mapping: dict[str, Any],
    key: str,
    location: str,
    errors: list[str],
) -> dict[str, Any]:
    value = mapping.get(key)
    if isinstance(value, dict):
        return value

    errors.append(f"{location}.{key} must be a mapping.")
    return {}


def string_list_value(
    mapping: dict[str, Any],
    key: str,
    location: str,
    errors: list[str],
) -> list[str]:
    value = mapping.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{location}.{key} must be a list of strings.")
        return []

    return value


def required_string(
    mapping: dict[str, Any],
    key: str,
    location: str,
    errors: list[str],
) -> str:
    value = mapping.get(key)

    if isinstance(value, str) and value.strip():
        return value.strip()

    errors.append(f"{location}.{key} must be a non-empty string.")
    return ""


def contains_command_pattern(commands: list[str], required_pattern: str) -> bool:
    normalized_pattern = normalize_text(required_pattern)
    return any(normalized_pattern in normalize_text(command) for command in commands)


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())
