from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_blueprint_story(project_path: Path, story_path: Path) -> dict[str, Any] | None:
    blueprint_path = project_path.resolve() / "blueprints" / "blueprint.yaml"
    if not blueprint_path.exists():
        return None

    try:
        loaded = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None

    if not isinstance(loaded, dict):
        return None

    stories = loaded.get("stories")
    if not isinstance(stories, list):
        return None

    refs = story_refs(story_path)
    for story in stories:
        if not isinstance(story, dict):
            continue
        if refs & story_blueprint_refs(story):
            return story

    return None


def story_refs(story_path: Path) -> set[str]:
    refs = {story_path.name}
    status_path = story_path / "status.yaml"
    if not status_path.exists():
        return refs

    try:
        loaded = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return refs

    if not isinstance(loaded, dict):
        return refs

    for key in ("slug", "story_id", "id"):
        value = loaded.get(key)
        if isinstance(value, str) and value.strip():
            refs.add(value.strip())

    return refs


def story_blueprint_refs(story: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key in ("slug", "story_id", "id"):
        value = story.get(key)
        if isinstance(value, str) and value.strip():
            refs.add(value.strip())
    return refs
