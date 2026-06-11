from pathlib import Path


GUIDE_PATH = Path("docs/codex_task_execution.md")
README_PATH = Path("README.md")
CODEX_RUNTIME_PATH = Path("docs/codex_runtime.md")
RUNTIME_CONFIG_PATH = Path("docs/runtime_config.md")


def test_codex_task_execution_doc_exists() -> None:
    assert GUIDE_PATH.exists()


def test_readme_links_to_codex_task_execution_doc() -> None:
    assert "docs/codex_task_execution.md" in README_PATH.read_text(encoding="utf-8")


def test_codex_runtime_links_to_codex_task_execution_doc() -> None:
    runtime_doc = CODEX_RUNTIME_PATH.read_text(encoding="utf-8")

    assert "docs/codex_task_execution.md" in runtime_doc
    assert "docs/runtime_config.md" in runtime_doc


def test_codex_task_execution_doc_mentions_required_commands() -> None:
    guide = GUIDE_PATH.read_text(encoding="utf-8")

    assert "build-context" in guide
    assert "codex-task create" in guide
    assert "workflow-run --story STORY_SLUG --phase local-finalize --execute" in guide


def test_codex_task_execution_doc_mentions_required_safety_boundaries() -> None:
    guide = GUIDE_PATH.read_text(encoding="utf-8")

    assert "Codex is not invoked automatically" in guide
    assert "Human approval is required before merge" in guide
    assert "Do not commit generated `codex_tasks`" in guide
    assert "Generated codex_tasks should not be committed" in guide


def test_runtime_config_doc_explains_codex_first_tiers() -> None:
    runtime_doc = RUNTIME_CONFIG_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    codex_runtime = CODEX_RUNTIME_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "Codex is the primary runtime",
        "default worker tier",
        "lighter research and documentation roles",
        "reserved for high-risk security, quality, and final local review",
        "Gemma support available",
        "optional micro-mode",
        "Blueprint files describe what to build and why",
        ".agentic/agent_runtime.yaml",
        "local_model_helper",
        "prompt_mode: micro",
    ]

    for phrase in required_phrases:
        assert phrase in runtime_doc

    assert "docs/runtime_config.md" in readme
    assert "gpt-5.4 (codex)" in codex_runtime
    assert "gpt-5.4-mini (codex)" in codex_runtime
    assert "gpt-5.5 (codex)" in codex_runtime
