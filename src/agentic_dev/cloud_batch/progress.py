from __future__ import annotations

from collections import Counter

from agentic_dev.cloud_batch.models import BatchItem, BatchResult, ItemResult, ProgressSummary


def derive_batch_progress(items: list[BatchItem]) -> ProgressSummary:
    counts = Counter(item.status for item in items)
    return ProgressSummary(
        total=len(items),
        pending=counts.get("draft", 0) + counts.get("ready", 0) + counts.get("exported", 0) + counts.get("awaiting_responses", 0),
        running=counts.get("planning", 0) + counts.get("applying", 0) + counts.get("resuming", 0) + counts.get("rollback_pending", 0) + counts.get("rolling_back", 0),
        succeeded=counts.get("applied", 0) + counts.get("resumed", 0),
        failed=counts.get("failed", 0) + counts.get("partially_failed", 0),
        blocked=counts.get("validation_partial", 0) + counts.get("planned", 0) + counts.get("partially_applied", 0) + counts.get("partially_resumed", 0) + counts.get("partially_rolled_back", 0),
        skipped=counts.get("superseded", 0),
        cancelled=counts.get("cancelled", 0),
    )


def derive_batch_status(progress: ProgressSummary, item_results: list[ItemResult]) -> str:
    if progress.total == 0:
        return "draft"
    if progress.cancelled == progress.total:
        return "cancelled"
    if progress.succeeded == progress.total:
        return "resumed" if any(result.outcome == "resumed" for result in item_results) else "applied"
    if progress.failed == progress.total:
        return "failed"
    if progress.succeeded and (progress.failed or progress.blocked or progress.pending or progress.running):
        return "partially_resumed" if any(result.outcome == "resumed" for result in item_results) else "partially_applied"
    if progress.pending or progress.running:
        return "planned"
    return "validation_complete"


def derive_batch_result(batch_id: str, items: list[BatchItem], item_results: list[ItemResult]) -> BatchResult:
    progress = derive_batch_progress(items)
    status = derive_batch_status(progress, item_results)
    return BatchResult(
        batch_id=batch_id,
        status=status,
        progress=progress,
        item_results=tuple(item_results),
        attempt_ids=tuple(sorted({result.attempt_id for result in item_results if result.attempt_id})),
        checksum="",
        details={},
    )

