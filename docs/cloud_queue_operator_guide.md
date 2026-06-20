# Cloud Queue Operator Guide

This guide explains the manual-first cloud escalation queue introduced by Story 063.
It is intentionally offline-friendly. It does not call paid cloud APIs, it does not
auto-apply imported responses, and it keeps provider-specific concerns out of the
canonical queue records.

## Architecture

The queue lives under `.agentic/cloud_queue/` at runtime. Requests are stored as
YAML, exports are written as ZIP packets plus a human-readable export index, and
audit events are appended to `audit.jsonl`.

The canonical request and response shapes are provider-neutral. OpenAI-shaped and
Gemini-shaped adapters are fixtures only and normalize into the same stored schema.

## Queue Lifecycle

1. Create a request from a local blocker.
2. Export the request or batch of ready requests.
3. Upload the export manually to ChatGPT, Gemini, or another compatible model.
4. Import the returned response file or bundle.
5. Classify the response independently.
6. Approve or reject the response only after the checksum matches.

Approved changes are recorded, but they are not applied automatically.

## Runtime Storage

```text
.agentic/cloud_queue/
|-- requests/
|-- exports/
|-- imports/
|-- approvals/
`-- audit.jsonl
```

Runtime files are ignored by Git and blocked by the artifact policy.

## Request Types

- `local_blocker`: a local execution blocker that needs manual review.
- Future provider-specific request flavors can normalize into the same canonical shape.

## Creating Requests

```powershell
agentic cloud-queue create --story STORY_SLUG --title "Explain the blocker" --details "..."
```

Add `--requirement`, `--writable-path`, and `--dependency` entries when they are known.

## Listing and Inspecting Requests

```powershell
agentic cloud-queue list
agentic cloud-queue show --request CQ-...
agentic cloud-queue status
```

Use `--json` when you want machine-readable output.

## Exporting One Request

```powershell
agentic cloud-queue export --request CQ-...
```

The export creates a ZIP packet plus a Markdown index. The packet contains the exact
response template, the request context, and a manifest with per-member checksums.

## Exporting Batches

```powershell
agentic cloud-queue export --all-ready
```

Only ready requests with resolved dependencies are exported. Each request in the batch
gets its own audit event.

## Uploading Manually

Upload the generated ZIP packet or the per-request Markdown export to ChatGPT, Gemini,
or another compatible model. Paste back the returned response file without executing it.

The exact response bundle should include:

- `response_id`
- `request_id`
- `batch_id`
- `response_schema_version`
- `normalized_response`
- `raw_response`
- `checksum`
- `decision`
- `claims`
- `adapter`

## Importing a Response

```powershell
agentic cloud-queue import --file .\response.yaml
```

The importer validates the file independently. It never executes imported content.
Malformed siblings do not block valid responses in the same bundle.

## Classification

Classification is independent of the cloud claim. The response is compared against:

- requirements
- writable paths
- dependency resolution
- scope changes

Responses that require approval become `approval_required`. Safe responses become
`validated_safe`. Prohibited or malformed responses become `validated_failed`.

## Approvals and Rejection

```powershell
agentic cloud-queue approve --request CQ-...
agentic cloud-queue reject --request CQ-...
```

Approval is checksum-locked to the exact normalized response that was classified.
Rejection and cancellation are recorded in the append-only audit log.

## Audit Records

Audit events are append-only JSONL records. Existing events are never overwritten.
Every state transition gets its own event.

## Redaction

Filenames and content are redacted before export when they look like secrets:

- `.env` files
- AWS credentials
- SSH private keys
- PEM blocks
- bearer tokens
- API keys
- passwords
- cookies
- authorization headers
- wallet seed phrases
- Git credential files

## Packet Limits

Exports and imports enforce archive size, expansion, path, and entry-count limits.
Nested ZIPs, traversal paths, unsupported archive entry types, and non-UTF-8 payloads
are rejected.

## Cleanup

Remove stale runtime requests after they have been approved, rejected, or canceled and
their evidence has been recorded.

## Troubleshooting

- If a request is not ready for export, check dependencies and prior state.
- If approval fails, confirm the checksum matches the normalized response exactly.
- If import fails, inspect the malformed response file and the audit log.

## Future Adapters

Future provider adapters can normalize into the same canonical request and response
schema without changing stored records. OpenAI and Gemini can be added later without
schema changes.

## Boundaries

Consumer subscriptions and API access are separate concerns from Story 063.
Story 063 performs no paid cloud API calls. Manual mode remains the default.
