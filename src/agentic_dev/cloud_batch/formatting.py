from __future__ import annotations

import json

from agentic_dev.cloud_batch.models import BatchRecord, BatchResult, OrchestrationPlan, RecoveryRecord


def format_batch_record(record: BatchRecord) -> str:
    return "\n".join(
        [
            f"Batch: {record.batch_id}",
            f"Type: {record.batch_type}",
            f"Status: {record.status}",
            f"Created: {record.created_at}",
            f"Items: {len(record.items)}",
            f"Progress: {record.progress.total} total / {record.progress.succeeded} succeeded / {record.progress.failed} failed",
            f"Plan: {record.latest_plan_id or 'none'}",
            f"Attempt: {record.latest_attempt_id or 'none'}",
        ],
    )


def format_batch_status(records: list[BatchRecord]) -> str:
    lines = ["Batch status:"]
    for record in records:
        lines.append(f"- {record.batch_id} | {record.status} | items={len(record.items)}")
    return "\n".join(lines) + "\n"


def format_batch_result(result: BatchResult) -> str:
    lines = [
        f"Batch result: {result.batch_id}",
        f"Status: {result.status}",
        f"Progress: total={result.progress.total} succeeded={result.progress.succeeded} failed={result.progress.failed} blocked={result.progress.blocked} cancelled={result.progress.cancelled}",
    ]
    if result.item_results:
        lines.append("Items:")
        for item in result.item_results:
            lines.append(f"- {item.item_id}: {item.outcome} ({item.message})")
    return "\n".join(lines) + "\n"


def format_orchestration_plan(plan: OrchestrationPlan) -> str:
    return "\n".join(
        [
            f"Batch plan: {plan.batch_id}",
            f"Plan ID: {plan.plan_id}",
            f"Status: {plan.status}",
            f"Items: {len(plan.items)}",
            f"Waves: {len(plan.execution_waves)}",
            f"Checksum: {plan.checksums.get('plan', '')}",
        ],
    )


def format_recovery_record(record: RecoveryRecord) -> str:
    payload = json.dumps(record.to_dict(), sort_keys=True)
    return "\n".join(
        [
            f"Batch recovery: {record.batch_id}",
            f"Reconciled: {record.reconciled}",
            "Findings:",
            *[f"- {finding}" for finding in record.findings],
            "",
            payload,
        ],
    )

