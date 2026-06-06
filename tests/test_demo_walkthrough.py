from pathlib import Path

import yaml


README_PATH = Path("README.md")
DEMO_DOC_PATH = Path("docs/demo_walkthrough.md")
DEMO_ROOT = Path("examples/minimal_project")
DEMO_README_PATH = DEMO_ROOT / "README.md"
DEMO_BLUEPRINT_PATH = DEMO_ROOT / "blueprints" / "blueprint.yaml"


def test_demo_walkthrough_and_files_exist() -> None:
    assert DEMO_DOC_PATH.exists()
    assert DEMO_README_PATH.exists()
    assert DEMO_BLUEPRINT_PATH.exists()


def test_readme_links_to_demo_walkthrough() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "docs/demo_walkthrough.md" in readme


def test_demo_blueprint_contains_stories_list() -> None:
    blueprint = yaml.safe_load(DEMO_BLUEPRINT_PATH.read_text(encoding="utf-8"))

    assert isinstance(blueprint["stories"], list)
    assert blueprint["stories"]
    assert "Build a simple task tracker CLI using mock data." in str(blueprint)


def test_demo_contains_no_env_files() -> None:
    env_files = [
        path
        for path in DEMO_ROOT.rglob("*")
        if path.is_file() and (path.name == ".env" or path.name.startswith(".env."))
    ]

    assert env_files == []


def test_demo_docs_state_no_cloud_secrets_or_deployment_required() -> None:
    walkthrough = DEMO_DOC_PATH.read_text(encoding="utf-8").lower()

    assert "does not require cloud models" in walkthrough
    assert "secrets" in walkthrough
    assert "deployment" in walkthrough
