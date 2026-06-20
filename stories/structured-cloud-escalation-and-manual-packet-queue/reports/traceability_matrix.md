# Story 063 Acceptance Traceability Matrix

| Acceptance criterion | Implementation symbol | Test / evidence | Evidence artifact |
| --- | --- | --- | --- |
| A local execution blocker can create a queue item | `create_cloud_queue_request` | `tests/test_cloud_queue_service.py::test_create_list_show_status_and_audit_events` | `stories/.../reports/test_report.md` |
| Queue items have stable unique IDs | `normalize_request_id`, `generate_request_id` | `tests/test_cloud_queue_service.py` | `stories/.../reports/test_report.md` |
| Request schema is versioned | `REQUEST_SCHEMA_VERSION`, `CloudQueueRequest.from_dict` | `tests/test_cloud_queue_contract.py` | `stories/.../reports/test_report.md` |
| Queue state transitions are validated | `validate_transition` | `tests/test_cloud_queue_state_machine.py` | `stories/.../reports/test_report.md` |
| Unsupported transitions are rejected | `state_machine.validate_transition` | `tests/test_cloud_queue_state_machine.py` | `stories/.../reports/test_report.md` |
| Request packets are self-contained | `export_requests`, `build_context` | `tests/test_cloud_queue_service.py::test_export_writes_per_request_audit_events_and_manifest` | `stories/.../reports/round_trip_report.md` |
| Request packets include relevant requirements | `build_context` | `tests/test_cloud_queue_service.py` | `stories/.../reports/round_trip_report.md` |
| Request packets include blocker evidence | `build_context` | `tests/test_cloud_queue_service.py`, `docs/cloud_queue_operator_guide.md` | `stories/.../reports/local_review_report.md` |
| Request packets include exact response schema | `request_template` | `tests/test_cloud_queue_contract.py` | `stories/.../reports/test_report.md` |
| Secrets are redacted | `redact_text`, `redact_path_fragment` | `tests/test_cloud_queue_security.py::test_secret_redaction_masks_filenames_and_content` | `stories/.../reports/security_quality_report.md` |
| `.env` contents are excluded | `is_sensitive_filename`, `redact_text` | `tests/test_cloud_queue_security.py` | `stories/.../reports/security_quality_report.md` |
| Export packet size is bounded | `validate_archive`, `MAX_ARCHIVE_BYTES`, `MAX_RESPONSE_BYTES` | `tests/test_cloud_queue_security.py` | `stories/.../reports/security_quality_report.md` |
| Single-request export works | `export_cloud_queue_request` | `tests/test_cloud_queue_service.py` | `stories/.../reports/test_report.md` |
| Batch export works | `export_cloud_queue_request(all_ready=True)` | `tests/test_cloud_queue_service.py::test_export_writes_per_request_audit_events_and_manifest` | `stories/.../reports/test_report.md` |
| Only ready independent requests are batched | `dependencies_resolved` | `tests/test_cloud_queue_service.py::test_dependency_resolution_blocks_export_until_prerequisite_resolves` | `stories/.../reports/test_report.md` |
| Dependent requests are not exported prematurely | `dependencies_resolved` | `tests/test_cloud_queue_service.py::test_dependency_resolution_blocks_export_until_prerequisite_resolves` | `stories/.../reports/test_report.md` |
| Batch ordering is deterministic | `export_requests` sort order | `tests/test_cloud_queue_service.py` | `stories/.../reports/test_report.md` |
| Export checksums are persisted | `checksum_text`, `append_audit_event` | `tests/test_cloud_queue_service.py` | `stories/.../reports/monitoring_report.md` |
| YAML response import works | `import_single_response` | `tests/test_cloud_queue_service.py` | `stories/.../reports/round_trip_report.md` |
| ZIP response-bundle import works | `import_response_bundle` | `tests/test_cloud_queue_service.py` | `stories/.../reports/round_trip_report.md` |
| ZIP-slip attacks are rejected | `validate_archive`, `normalize_relative_path` | `tests/test_cloud_queue_security.py` | `stories/.../reports/security_quality_report.md` |
| Unknown request IDs are rejected | `import_single_response` | `tests/test_cloud_queue_security.py`, `tests/test_cloud_queue_service.py` | `stories/.../reports/test_report.md` |
| Duplicate response IDs are rejected | `import_response_bundle` | `tests/test_cloud_queue_security.py::test_duplicate_response_ids_rejected_within_bundle` | `stories/.../reports/security_quality_report.md` |
| Invalid schema versions are rejected | `response_schema_is_valid` | `tests/test_cloud_queue_security.py` | `stories/.../reports/security_quality_report.md` |
| Malformed YAML is rejected safely | `load_mapping_text` | `tests/test_cloud_queue_security.py` | `stories/.../reports/security_quality_report.md` |
| Raw imported responses are preserved safely | `CloudQueueResponse.raw_response` | `tests/test_cloud_queue_service.py` | `stories/.../reports/round_trip_report.md` |
| Normalized responses are persisted | `approval_checksum`, `normalized_response_checksum` | `tests/test_cloud_queue_service.py::test_approval_checksum_lock_blocks_stale_checksum_and_reclassification_changes_binding` | `stories/.../reports/security_quality_report.md` |
| Requirements are independently compared | `compare_requirements` | `tests/test_cloud_queue_service.py`, `tests/test_cloud_queue_contract.py` | `stories/.../reports/test_report.md` |
| Writable paths are independently compared | `compare_writable_paths` | `tests/test_cloud_queue_service.py`, `tests/test_cloud_queue_security.py` | `stories/.../reports/test_report.md` |
| External-service additions are detected | `compare_scope` | `tests/test_cloud_queue_contract.py` | `stories/.../reports/test_report.md` |
| Safe decompositions are classified as safe candidates | `classify_response` | `tests/test_cloud_queue_service.py` | `stories/.../reports/round_trip_report.md` |
| Scope-changing responses require approval | `classify_response` | `tests/test_cloud_queue_service.py` | `stories/.../reports/round_trip_report.md` |
| Invalid responses do not corrupt valid responses in the same batch | `import_response_bundle` | `tests/test_cloud_queue_service.py` | `stories/.../reports/round_trip_report.md` |
| No imported response executes code | `load_mapping_text`, `ensure_json_or_yaml_text` | `tests/test_cloud_queue_security.py` | `stories/.../reports/security_quality_report.md` |
| Audit logs contain state transitions and checksums | `append_audit_event` | `tests/test_cloud_queue_service.py` | `stories/.../reports/monitoring_report.md` |
| Logs do not expose secrets | `redact_text`, `append_audit_event` | `tests/test_cloud_queue_security.py`, `tests/test_text_encoding_hygiene.py` | `stories/.../reports/security_quality_report.md` |
| Manual packet mode works without network access | `ManualPacketAdapter` | `tests/test_cloud_queue_contract.py` | `stories/.../reports/test_report.md` |
| CI uses deterministic fixtures | `FakeOpenAIAdapter`, `FakeGeminiAdapter` | `tests/test_cloud_queue_contract.py` | `stories/.../reports/test_report.md` |
| Future provider adapters can use the same canonical schemas | `CloudQueueRequest`, `CloudQueueResponse` | `tests/test_cloud_queue_contract.py` | `stories/.../reports/test_report.md` |
| OpenAI and Gemini can be added later without changing queue records | `FakeOpenAIAdapter`, `FakeGeminiAdapter` | `tests/test_cloud_queue_contract.py` | `stories/.../reports/test_report.md` |
| Story 061 context-safe task rules remain enforced | `workflow_run`, `workflow_preview` | `tests/test_workflow_run.py`, `tests/test_workflow_preview.py` | `stories/.../reports/test_report.md` |
| Story 062 demo and post-merge verification remain backward compatible | `workflow_run`, `workflow_preview` | `tests/test_workflow_run.py`, `tests/test_workflow_preview.py` | `stories/.../reports/test_report.md` |
| No cloud or Codex fallback is introduced | `ManualPacketAdapter`, CLI wiring | `tests/test_cloud_queue_contract.py`, `tests/test_cloud_queue_cli.py` | `stories/.../reports/test_report.md` |
| No automatic API charges can occur in Story 063 | `docs/cloud_queue_operator_guide.md` | `tests/test_cloud_queue_docs.py` | `stories/.../reports/local_review_report.md` |
| Operator documentation explains export/upload/download/import | `docs/cloud_queue_operator_guide.md` | `tests/test_cloud_queue_docs.py` | `stories/.../reports/local_review_report.md` |
| Error messages are actionable | CLI formatting helpers | `tests/test_cloud_queue_cli.py` | `stories/.../reports/test_report.md` |
| Queue artifacts follow artifact policy | `artifact_policy.py`, `.gitignore` | `tests/test_cloud_queue_cli.py`, `tests/test_cloud_queue_docs.py` | `stories/.../reports/monitoring_report.md` |
| Generation remains idempotent | `generate_stories` | `tests/test_feature_scan.py`, CLI run twice | `stories/.../reports/test_report.md` |

