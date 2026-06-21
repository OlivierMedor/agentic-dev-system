from __future__ import annotations


import pytest

from agentic_dev.cloud_batch.models import (
    BATCH_SCHEMA_VERSION,
    BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION,
    AttemptRecord,
    BatchDependencyGraph,
    BatchItem,
    BatchRecord,
    BatchResult,
    ExecutionPolicy,
    ItemResult,
    LockRecord,
    OrchestrationPlan,
    ProgressSummary,
    RecoveryRecord,
    ExecutionWave,
    validate_batch_record,
    validate_checksum,
    validate_execution_policy,
    validate_status,
    validate_supported_batch_type,
)


def sample_batch_item(item_id: str = "item-a", request_id: str = "CQ-1") -> BatchItem:
    return BatchItem(
        item_id=item_id,
        request_id=request_id,
        response_id=f"{request_id}-response",
        status="ready",
        dependencies=("root",) if item_id != "root" else (),
        writable_paths=("src/app.py",),
        request_checksum="",
        response_checksum="",
        approval_checksum="",
        plan_checksum="",
        application_id="",
        revision_id="",
        lease_id="",
        attempt_ids=("attempt-1",),
        notes=("note",),
        result={"status": "ready"},
    )


def test_batch_models_round_trip() -> None:
    item = sample_batch_item()
    graph = BatchDependencyGraph(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id="batch-1",
        node_ids=("item-a",),
        dependency_map={"item-a": ("root",)},
        topological_order=("item-a",),
        ready_set=("item-a",),
        checksum="a" * 64,
    )
    progress = ProgressSummary(total=1, pending=1, running=0, succeeded=0, failed=0, blocked=0, skipped=0, cancelled=0)
    result = BatchResult(batch_id="batch-1", status="draft", progress=progress, item_results=(ItemResult(item_id="item-a", outcome="pending", message="waiting"),))
    record = BatchRecord(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id="batch-1",
        batch_type=BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION,
        created_at="2026-06-21T12:00:00-04:00",
        status="draft",
        item_ids=("item-a",),
        items=(item,),
        dependency_graph=graph,
        execution_policy=ExecutionPolicy(),
        progress=progress,
        results=result,
        checksums={"batch_record": "a" * 64},
        attempts=(AttemptRecord(schema_version=1, attempt_id="attempt-1", batch_id="batch-1", phase="draft", created_at="2026-06-21T12:00:00-04:00", item_ids=("item-a",)),),
        audits=("audit-1",),
        latest_plan_id="plan-1",
        latest_attempt_id="attempt-1",
        notes=("note",),
    )
    plan = OrchestrationPlan(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id="batch-1",
        plan_id="plan-1",
        batch_type=BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION,
        created_at="2026-06-21T12:00:00-04:00",
        item_ids=("item-a",),
        items=(item,),
        dependency_graph=graph,
        execution_policy=ExecutionPolicy(),
        execution_waves=(ExecutionWave(wave_id="wave-1", phase="validation", item_ids=("item-a",)),),
        conflict_graph=(),
        expected_revision_chain=("rev-1",),
        checksums={"plan": "a" * 64, "dependency_graph": "a" * 64},
        progress=progress,
        status="planned",
        dry_run=False,
        details={"key": "value"},
    )
    lock = LockRecord(
        schema_version=1,
        lock_id="lock-1",
        batch_id="batch-1",
        operation="apply",
        holder="operator",
        created_at="2026-06-21T12:00:00-04:00",
        expires_at=None,
        checksum="a" * 64,
    )
    recovery = RecoveryRecord(
        schema_version=1,
        batch_id="batch-1",
        created_at="2026-06-21T12:00:00-04:00",
        findings=("missing checksum",),
        recommended_actions=("recompute",),
        reconciled=False,
        checksum="a" * 64,
    )

    assert BatchItem.from_dict(item.to_dict()) == item
    assert BatchDependencyGraph.from_dict(graph.to_dict()) == graph
    assert BatchResult.from_dict(result.to_dict()) == result
    assert BatchRecord.from_dict(record.to_dict()) == record
    assert OrchestrationPlan.from_dict(plan.to_dict()) == plan
    assert LockRecord.from_dict(lock.to_dict()) == lock
    assert RecoveryRecord.from_dict(recovery.to_dict()) == recovery


def test_batch_validation_rejects_bad_checksums_and_statuses() -> None:
    with pytest.raises(ValueError, match="Malformed checksum"):
        validate_checksum("not-a-checksum")
    with pytest.raises(ValueError, match="Invalid batch status"):
        validate_status("unknown")
    with pytest.raises(ValueError, match="Unsupported batch type"):
        validate_supported_batch_type("bad-type")


def test_batch_validation_rejects_duplicate_ids_and_invalid_policy() -> None:
    item_a = sample_batch_item("item-a", "CQ-1")
    item_b = sample_batch_item("item-a", "CQ-2")
    graph = BatchDependencyGraph(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id="batch-1",
        node_ids=("item-a", "item-a"),
        dependency_map={"item-a": ()},
        topological_order=("item-a",),
        ready_set=("item-a",),
        checksum="a" * 64,
    )
    record = BatchRecord(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id="batch-1",
        batch_type=BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION,
        created_at="2026-06-21T12:00:00-04:00",
        status="draft",
        item_ids=("item-a", "item-a"),
        items=(item_a, item_b),
        dependency_graph=graph,
        execution_policy=ExecutionPolicy(),
        progress=ProgressSummary(total=2, pending=2, running=0, succeeded=0, failed=0, blocked=0, skipped=0, cancelled=0),
        results=BatchResult(batch_id="batch-1", status="draft", progress=ProgressSummary(total=2, pending=2, running=0, succeeded=0, failed=0, blocked=0, skipped=0, cancelled=0), item_results=()),
        checksums={"batch_record": "a" * 64},
    )

    with pytest.raises(ValueError, match="Duplicate batch item IDs"):
        validate_batch_record(record)

    with pytest.raises(ValueError, match="Automatic batch apply must remain disabled"):
        validate_execution_policy(ExecutionPolicy(automatic_apply_enabled=True))
