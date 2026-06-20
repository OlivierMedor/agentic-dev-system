# STORY-063: Story 063 - Structured Cloud Escalation and Manual Packet Queue

## Goal

Define a provider-neutral, manual-first cloud escalation queue that packages local blockers into self-contained request packets, accepts untrusted cloud responses, validates them independently, classifies safe decompositions, and records approval decisions without invoking paid cloud APIs.

## Why This Matters

Story 061 made context-safe local execution explicit, and Story 062 proved the end-to-end local demo path plus post-merge verification. Story 063 adds the missing cloud escalation boundary so a blocked local task can be packaged, exported, manually reviewed in any compatible cloud model, re-imported safely, and classified for either approval or later automatic application while remaining provider-neutral and offline-friendly.

## Acceptance Criteria

- A local execution blocker can create a queue item.
- Queue items have stable unique IDs.
- Request schema is versioned.
- Queue state transitions are validated.
- Unsupported transitions are rejected.
- Request packets are self-contained.
- Request packets include relevant requirements.
- Request packets include blocker evidence.
- Request packets include exact response schema.
- Secrets are redacted.
- .env contents are excluded.
- Export packet size is bounded.
- Single-request export works.
- Batch export works.
- Only ready independent requests are batched.
- Dependent requests are not exported prematurely.
- Batch ordering is deterministic.
- Export checksums are persisted.
- YAML response import works.
- ZIP response-bundle import works.
- ZIP-slip attacks are rejected.
- Unknown request IDs are rejected.
- Duplicate response IDs are rejected.
- Invalid schema versions are rejected.
- Malformed YAML is rejected safely.
- Raw imported responses are preserved safely.
- Normalized responses are persisted.
- Requirements are independently compared.
- Writable paths are independently compared.
- External-service additions are detected.
- Safe decompositions are classified as safe candidates.
- Scope-changing responses require approval.
- Invalid responses do not corrupt valid responses in the same batch.
- No imported response executes code.
- Audit logs contain state transitions and checksums.
- Logs do not expose secrets.
- Manual packet mode works without network access.
- CI uses deterministic fixtures.
- Future provider adapters can use the same canonical schemas.
- OpenAI and Gemini can be added later without changing queue records.
- Story 061 context-safe task rules remain enforced.
- Story 062 demo and post-merge verification remain backward compatible.
- No cloud or Codex fallback is introduced.
- No automatic API charges can occur in Story 063.
- Operator documentation explains export, upload, response download, and import.
- Error messages are actionable.
- Queue artifacts follow artifact policy.
- Generation remains idempotent.

## Not In Scope

- Paid cloud API integrations.
- Automatic provider selection at runtime.
- Automatic task-graph mutation or local execution resume from imported cloud results.
- Secret-bearing packets, environment dumps, or arbitrary archive extraction.
- Deployment, publishing, release tagging, or direct pushes to main.
- Automatic commits or merges from cloud responses.

## Definition of Done

- The blueprint defines the manual-first escalation queue, batch export, safe import, approval boundary, and provider-neutral schemas.
- Acceptance criteria cover queue lifecycle, packet export/import, redaction, classification, auditability, and future provider compatibility.
- The generated Story 063 workspace is created by agentic generate-stories and generation is idempotent across two runs.
- docker compose run --rm dev pytest passes.
- docker compose run --rm dev ruff check . passes.
- artifact-policy validation passes.
- runtime-config validation passes.
- hidden-Unicode hygiene validation passes.
- Public-readiness validation passes when applicable to the repository state.
- The manual packet mode remains the default.
- No paid cloud API calls are implemented.
- Provider-neutral adapter compatibility is preserved for future OpenAI, Gemini, Anthropic, Bedrock, and OpenAI-compatible support.
- Backward compatibility is preserved for Stories 060, 061, and 062.
