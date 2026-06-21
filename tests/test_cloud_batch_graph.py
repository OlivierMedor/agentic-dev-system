from __future__ import annotations

import pytest

from agentic_dev.cloud_batch.graph import (
    batch_dependency_ready_set,
    batch_dependency_topological_order,
    detect_dependency_cycles,
    validate_batch_dependency_graph,
)
from agentic_dev.cloud_batch.models import BatchItem


def test_dependency_graph_topological_order_and_ready_set() -> None:
    items = [
        BatchItem(item_id="a", request_id="CQ-1", status="ready", writable_paths=("a/**",)),
        BatchItem(item_id="b", request_id="CQ-2", status="ready", dependencies=("a",), writable_paths=("b/**",)),
        BatchItem(item_id="c", request_id="CQ-3", status="ready", writable_paths=("c/**",)),
    ]

    assert batch_dependency_topological_order(items) == ("a", "c", "b")
    assert batch_dependency_ready_set(items) == ("a", "c")
    validate_batch_dependency_graph(items)


def test_dependency_cycle_is_rejected() -> None:
    items = [
        BatchItem(item_id="a", request_id="CQ-1", status="ready", dependencies=("b",), writable_paths=("a/**",)),
        BatchItem(item_id="b", request_id="CQ-2", status="ready", dependencies=("a",), writable_paths=("b/**",)),
    ]

    assert detect_dependency_cycles(items)
    with pytest.raises(ValueError, match="Dependency graph contains a cycle"):
        validate_batch_dependency_graph(items)

