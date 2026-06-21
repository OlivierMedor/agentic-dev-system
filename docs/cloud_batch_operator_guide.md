# Cloud Batch Operator Guide

Story 065 adds a batch orchestration layer on top of the Story 063 request queue
and the Story 064 application/runtime revision pipeline. Batches do not replace
the per-request controls. They only coordinate multiple requests in a
deterministic dependency-aware order.

## Architecture

Each cloud request still has its own request record, imported response record,
approval boundary, application plan, transaction journal, runtime revision,
lease set, and publication records. The batch layer only stores orchestration
metadata under `.agentic/cloud_batches/`.

Batch records are operator-readable YAML and reference the underlying request
and application files by checksum, not by opaque bundle payload.

## Runtime Storage

```text
.agentic/cloud_batches/
|-- records/
|-- plans/
|-- attempts/
|-- audits/
|-- locks/
`-- recovery/
```

These files are ignored by Git and blocked by artifact policy and public
readiness checks. They are for local/manual operation only.

## Lifecycle

1. Export ready requests into one deterministic batch.
2. Upload the request packet manually.
3. Import one or more responses.
4. Build an orchestration plan.
5. Apply eligible items in deterministic order.
6. Resume successful applications with explicit operator action.
7. Retry, cancel, rollback, or recover only when requested.

## CLI

```powershell
agentic cloud-queue batch list
agentic cloud-queue batch show --batch batch-20260621-0001
agentic cloud-queue batch export --all-ready
agentic cloud-queue batch import --file .\responses.zip
agentic cloud-queue batch plan-apply --batch batch-20260621-0001
agentic cloud-queue batch apply --batch batch-20260621-0001
agentic cloud-queue batch apply --batch batch-20260621-0001 --dry-run
agentic cloud-queue batch resume --batch batch-20260621-0001
agentic cloud-queue batch retry --batch batch-20260621-0001
agentic cloud-queue batch cancel --batch batch-20260621-0001
agentic cloud-queue batch rollback --batch batch-20260621-0001
agentic cloud-queue batch status
```

## Manual-Only Behavior

- No paid provider API calls are added by the batch layer.
- No provider network access is added.
- Manual cloud upload remains the default.
- Automatic batch apply remains disabled.
- Automatic batch resume remains disabled.
- Item approvals and item checksums remain required.
- One active runtime revision remains enforced.

## Troubleshooting

- If a batch is not ready, inspect request dependencies and item states.
- If an import member is malformed, the remaining responses are still processed.
- If apply or resume stops early, inspect the batch audit log and per-item
  application records under `.agentic/cloud_batches/` and `.agentic/cloud_applications/`.
- If rollback stops part-way through, the batch record will show a partial
  rollback state and the later unrelated revision must be reviewed manually.

