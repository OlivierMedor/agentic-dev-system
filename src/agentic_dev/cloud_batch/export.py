from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agentic_dev.cloud_batch.audit import BatchAuditEvent, append_batch_audit_event
from agentic_dev.cloud_batch.concurrency import acquire_batch_lock
from agentic_dev.cloud_batch.conflicts import detect_batch_conflicts
from agentic_dev.cloud_batch.graph import (
    batch_dependency_ready_set,
    batch_dependency_topological_order,
    validate_batch_dependency_graph,
)
from agentic_dev.cloud_batch.models import (
    BATCH_SCHEMA_VERSION,
    BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION,
    BatchDependencyGraph,
    BatchItem,
    BatchRecord,
    BatchResult,
    ExecutionPolicy,
)
from agentic_dev.cloud_batch.persistence import ensure_batch_dirs, save_batch_record
from agentic_dev.cloud_batch.progress import derive_batch_progress
from agentic_dev.cloud_queue import dependencies_resolved, show_cloud_queue_request
from agentic_dev.cloud_queue.export import export_requests
from agentic_dev.cloud_queue.persistence import load_requests
from agentic_dev.cloud_queue.persistence import checksum_text, now_iso


@dataclass(frozen=True)
class BatchExportResult:
    batch_record: BatchRecord
    export_path: Path
    export_index_path: Path
    request_ids: tuple[str, ...]
    batch_manifest_checksum: str


def export_batch(
    project_path: Path,
    *,
    request_ids: list[str] | None = None,
    all_ready: bool = False,
    batch_id: str | None = None,
    event_id_factory: Callable[[], str] | None = None,
) -> BatchExportResult:
    ensure_batch_dirs(project_path)
    requests = _select_requests(project_path, request_ids=request_ids, all_ready=all_ready)
    if not requests:
        raise ValueError("No ready cloud queue requests were available for batch export.")

    resolved_batch_id = batch_id or f"batch-{now_iso().replace(':', '').replace('+', '-')}"
    items = tuple(
        BatchItem(
            item_id=request.request_id,
            request_id=request.request_id,
            status="exported",
            dependencies=tuple(request.dependencies),
            writable_paths=tuple(request.writable_paths),
            request_checksum=request.packet_checksum,
        )
        for request in requests
    )
    validate_batch_dependency_graph(list(items))
    conflict_result = detect_batch_conflicts(list(items))
    dependency_graph = BatchDependencyGraph(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id=resolved_batch_id,
        node_ids=tuple(item.item_id for item in items),
        dependency_map={item.item_id: item.dependencies for item in items},
        topological_order=batch_dependency_topological_order(list(items)),
        ready_set=batch_dependency_ready_set(list(items)),
        checksum=checksum_text(str([item.to_dict() for item in items])),
    )
    progress = derive_batch_progress(list(items))
    batch_record = BatchRecord(
        schema_version=BATCH_SCHEMA_VERSION,
        batch_id=resolved_batch_id,
        batch_type=BATCH_TYPE_CLOUD_QUEUE_ORCHESTRATION,
        created_at=now_iso(),
        status="exported",
        item_ids=tuple(item.item_id for item in items),
        items=items,
        dependency_graph=dependency_graph,
        execution_policy=ExecutionPolicy(),
        progress=progress,
        results=BatchResult(
            batch_id=resolved_batch_id,
            status="exported",
            progress=progress,
            item_results=(),
            attempt_ids=(),
            checksum=checksum_text(str([item.to_dict() for item in items])),
            details={"conflict_count": len(conflict_result.conflicts)},
        ),
        checksums={},
        attempts=(),
        audits=(),
        latest_plan_id="",
        latest_attempt_id="",
    )
    with acquire_batch_lock(project_path, resolved_batch_id, "export"):
        save_batch_record(project_path, batch_record)
        export_result = export_requests(project_path, list(requests), batch_id=resolved_batch_id, event_id_factory=event_id_factory)
        batch_record_checksum = checksum_text(
            str(
                {
                    "batch_id": resolved_batch_id,
                    "item_ids": [item.item_id for item in items],
                    "export_path": str(export_result.export_path),
                },
            ),
        )
        manifest_checksum = checksum_text(str(
            {
                "batch_id": resolved_batch_id,
                "request_ids": [request.request_id for request in requests],
                "export_path": str(export_result.export_path),
            }
        ))
        updated_batch_record = BatchRecord.from_dict(
            {
                **batch_record.to_dict(),
                "checksums": {
                    "batch_record": batch_record_checksum,
                    "batch_manifest": manifest_checksum,
                },
                "results": {
                    **batch_record.results.to_dict(),
                    "checksum": batch_record_checksum,
                },
            },
        )
        save_batch_record(project_path, updated_batch_record)
        append_batch_audit_event(
            project_path,
            BatchAuditEvent(
                event_id="",
                event_type="batch_export",
                batch_id=resolved_batch_id,
                prior_state="ready",
                new_state="exported",
                timestamp=now_iso(),
                details={"request_ids": [request.request_id for request in requests]},
            ),
        )
    return BatchExportResult(
        batch_record=updated_batch_record,
        export_path=export_result.export_path,
        export_index_path=export_result.export_markdown_path,
        request_ids=tuple(request.request_id for request in requests),
        batch_manifest_checksum=manifest_checksum,
    )


def _select_requests(
    project_path: Path,
    *,
    request_ids: list[str] | None,
    all_ready: bool,
):
    if request_ids:
        selected = []
        for request_id in request_ids:
            selected.append(show_cloud_queue_request(project_path, request_id).request)
        return [request for request in selected if request.state == "ready" and dependencies_resolved(project_path, request)]
    if all_ready:
        return [request for _path, request in load_requests(project_path) if request.state == "ready" and dependencies_resolved(project_path, request)]
    return []
