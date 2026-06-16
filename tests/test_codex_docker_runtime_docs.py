from pathlib import Path

import yaml


DOCKERFILE_PATH = Path("Dockerfile")
COMPOSE_PATH = Path("compose.yml")
README_PATH = Path("README.md")
CODEX_DOCKER_DOC_PATH = Path("docs/codex_docker_runtime.md")
CODEX_RUNTIME_DOC_PATH = Path("docs/codex_runtime.md")
RUNTIME_CONFIG_DOC_PATH = Path("docs/runtime_config.md")


def test_dockerfile_installs_codex_cli_with_safe_noninteractive_installer() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "https://chatgpt.com/codex/install.sh" in dockerfile
    assert "CODEX_NON_INTERACTIVE=1" in dockerfile
    assert "CODEX_INSTALL_DIR=/usr/local/bin" in dockerfile
    assert "codex --version" in dockerfile
    assert "OPENAI_API_KEY" not in dockerfile
    assert "CODEX_API_KEY" not in dockerfile
    assert "CODEX_ACCESS_TOKEN" not in dockerfile


def test_compose_mounts_codex_home_as_docker_volume_not_repo_path() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    dev = compose["services"]["dev"]

    assert dev["environment"]["CODEX_HOME"] == "/codex-home"
    assert "codex-home:/codex-home" in dev["volumes"]
    assert "codex-home" in compose["volumes"]
    assert "./.codex:/codex-home" not in dev["volumes"]
    assert "./codex-home:/codex-home" not in dev["volumes"]


def test_codex_docker_docs_explain_smoke_checks_and_no_committed_credentials() -> None:
    guide = CODEX_DOCKER_DOC_PATH.read_text(encoding="utf-8")
    normalized_guide = " ".join(guide.split())
    readme = README_PATH.read_text(encoding="utf-8")
    runtime_doc = CODEX_RUNTIME_DOC_PATH.read_text(encoding="utf-8")
    runtime_config_doc = RUNTIME_CONFIG_DOC_PATH.read_text(encoding="utf-8")

    for text in [guide, readme, runtime_doc, runtime_config_doc]:
        assert "docker compose run --rm dev which codex" in text
        assert "docker compose run --rm dev codex --version" in text
        assert "docker compose run --rm dev codex exec --help" in text
        assert "codex exec --sandbox workspace-write -" in text

    assert "docs/codex_docker_runtime.md" in readme
    assert "CODEX_HOME=/codex-home" in guide
    assert "Docker-managed named volume" in normalized_guide
    assert "does not bake API keys, access tokens" in normalized_guide
    assert "read-only by default" in guide
    assert "danger-full-access" in guide
    assert "bwrap" in guide
    assert "No permissions to create a new namespace" in guide
    assert "docker_isolation_acknowledged: true" in guide
    assert "trusted repos" in normalized_guide
    assert "mounted workspace" in normalized_guide
    assert "Do not put `CODEX_API_KEY`, `CODEX_ACCESS_TOKEN`, `auth.json`" in normalized_guide
    assert "BLOCKED_CODEX_COMMAND_NOT_FOUND" in guide


def test_gitignore_excludes_codex_auth_state_paths() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert ".codex/" in gitignore
    assert "codex-home/" in gitignore
    assert "codex-auth/" in gitignore
