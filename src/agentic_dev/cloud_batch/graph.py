from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from agentic_dev.cloud_batch.models import BatchItem
from agentic_dev.cloud_queue.validation import normalize_relative_path
from agentic_dev.cloud_application.validation import validate_path_overlap


@dataclass(frozen=True)
class GraphValidationResult:
    valid: bool
    cycles: tuple[tuple[str, ...], ...] = ()
    missing_dependencies: tuple[str, ...] = ()
    ready_set: tuple[str, ...] = ()
    topological_order: tuple[str, ...] = ()


def validate_batch_dependency_graph(items: list[BatchItem]) -> None:
    ids = [item.item_id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate batch item IDs are not allowed.")
    item_ids = set(ids)
    for item in items:
        for dependency in item.dependencies:
            if dependency not in item_ids:
                raise ValueError(f"Missing dependency: {dependency}")
    if detect_dependency_cycles(items):
        raise ValueError("Dependency graph contains a cycle.")


def detect_dependency_cycles(items: list[BatchItem]) -> tuple[tuple[str, ...], ...]:
    graph = {item.item_id: tuple(item.dependencies) for item in items}
    seen: set[str] = set()
    on_stack: set[str] = set()
    stack: list[str] = []
    cycles: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        if node in on_stack:
            if node in stack:
                index = stack.index(node)
                cycles.append(tuple(stack[index:] + [node]))
            return
        if node in seen:
            return
        seen.add(node)
        on_stack.add(node)
        stack.append(node)
        for dependency in graph.get(node, ()):
            visit(dependency)
        stack.pop()
        on_stack.remove(node)

    for node in sorted(graph):
        visit(node)

    return tuple(cycles)


def batch_dependency_topological_order(items: list[BatchItem]) -> tuple[str, ...]:
    validate_batch_dependency_graph(items)
    graph = {item.item_id: set(item.dependencies) for item in items}
    reverse_graph: dict[str, set[str]] = {item.item_id: set() for item in items}
    for node, dependencies in graph.items():
        for dependency in dependencies:
            reverse_graph[dependency].add(node)
    ready = deque(sorted(node for node, deps in graph.items() if not deps))
    order: list[str] = []
    remaining = {node: set(deps) for node, deps in graph.items()}
    while ready:
        node = ready.popleft()
        order.append(node)
        for dependent in sorted(reverse_graph.get(node, ())):
            remaining[dependent].discard(node)
            if not remaining[dependent]:
                ready.append(dependent)
    if len(order) != len(items):
        raise ValueError("Dependency graph contains a cycle.")
    return tuple(order)


def batch_dependency_ready_set(items: list[BatchItem], completed: Iterable[str] = ()) -> tuple[str, ...]:
    completed_set = set(completed)
    item_ids = {item.item_id for item in items}
    ready: list[str] = []
    for item in sorted(items, key=lambda item: item.item_id):
        if item.item_id in completed_set:
            continue
        if any(dependency not in item_ids for dependency in item.dependencies):
            continue
        if all(dependency in completed_set for dependency in item.dependencies):
            ready.append(item.item_id)
    return tuple(ready)


def dependency_blocking_map(items: list[BatchItem], failed_items: Iterable[str]) -> dict[str, tuple[str, ...]]:
    failed_set = set(failed_items)
    blocking: dict[str, tuple[str, ...]] = {}
    by_id = {item.item_id: item for item in items}
    for item in items:
        blockers = tuple(sorted(dependency for dependency in item.dependencies if dependency in failed_set))
        if blockers:
            blocking[item.item_id] = blockers
        elif any(dependency in by_id and dependency in failed_set for dependency in item.dependencies):
            blocking[item.item_id] = tuple(sorted(dependency for dependency in item.dependencies if dependency in failed_set))
    return blocking


def propagate_terminal_states(
    items: list[BatchItem],
    terminal_states: dict[str, str],
) -> dict[str, str]:
    propagated = dict(terminal_states)
    changed = True
    while changed:
        changed = False
        for item in items:
            if item.item_id in propagated:
                continue
            if any(dependency in propagated and propagated[dependency] in {"failed", "cancelled", "superseded"} for dependency in item.dependencies):
                propagated[item.item_id] = "blocked"
                changed = True
    return propagated


def stable_scheduling_order(items: list[BatchItem]) -> tuple[str, ...]:
    return batch_dependency_topological_order(items)


def validate_path_overlap_for_items(items: list[BatchItem]) -> None:
    snapshot_items = []
    for item in items:
        snapshot_items.append(
            {
                "task_id": item.item_id,
                "writable_paths": list(item.writable_paths),
            },
        )
    validate_path_overlap(
        [
            _to_task_snapshot(item_id=item["task_id"], writable_paths=tuple(item["writable_paths"]))
            for item in snapshot_items
        ],
    )


def _to_task_snapshot(item_id: str, writable_paths: tuple[str, ...]):
    from agentic_dev.cloud_application.models import TaskSnapshot

    return TaskSnapshot(
        task_id=item_id,
        title=item_id,
        role="batch",
        writable_paths=tuple(normalize_relative_path(path) for path in writable_paths),
    )

