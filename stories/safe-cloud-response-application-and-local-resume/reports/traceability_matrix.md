# Traceability Matrix

| Acceptance criterion | Implementation symbol | Focused test or evidence |
| --- | --- | --- |
| Only eligible responses can produce application plans | `cloud_application/validation.py::validate_eligibility`, `cloud_application/planning.py::build_planned_application` | `tests/test_cloud_application_validation.py`, `stories/safe-cloud-response-application-and-local-resume/reports/test_report.md` |
| `validated_safe` responses may be planned without approval | `cloud_application/service.py::plan_apply` | `tests/test_cloud_application_service.py` |
| `approval_required` responses need valid approval | `cloud_application/validation.py::validate_eligibility`, `cloud_queue/approvals.py::load_approval_record` | `tests/test_cloud_application_validation.py`, `tests/test_cloud_application_service.py` |
| Approval checksum must match | `cloud_application/validation.py::validate_eligibility`, `cloud_application/validation.py::validate_approval_scope` | `tests/test_cloud_application_validation.py` |
| Request checksum must match | `cloud_application/validation.py::validate_eligibility` | `tests/test_cloud_application_validation.py` |
| Stale responses cannot be applied | `cloud_application/service.py::plan_apply`, `cloud_application/service.py::_transition_application` | `tests/test_cloud_application_service.py` |
| Already-applied responses cannot be applied twice | `cloud_application/service.py::_apply_plan`, `cloud_application/transactions.py::create_transaction_record` | `tests/test_cloud_application_service.py` |
| Application plans are versioned | `cloud_application/models.py::ApplicationPlan`, `cloud_application/planning.py::build_planned_application` | `tests/test_cloud_application_models.py` |
| Application plans are immutable | `cloud_application/models.py::ApplicationPlan`, `cloud_application/planning.py::PlannedApplication` | `tests/test_cloud_application_models.py` |
| Dry run performs complete validation | `cloud_application/service.py::plan_apply`, `cloud_application/planning.py::build_planned_application` | `tests/test_cloud_application_service.py` |
| Dry run makes no runtime-plan changes | `cloud_application/service.py::plan_apply` | `tests/test_cloud_application_service.py` |
| Canonical blueprint is never modified | `cloud_application/validation.py::validate_no_canonical_mutation`, `artifact_policy.py` | `tests/test_artifact_policy.py`, `tests/test_public_readiness.py`, `tests/test_cloud_application_service.py` |
| Source tasks are superseded, not deleted | `cloud_application/graph.py::build_runtime_graph_revision`, `cloud_application/service.py::_apply_plan` | `tests/test_cloud_application_service.py`, `tests/test_cloud_application_models.py` |
| Source-task history is preserved | `cloud_application/models.py::TaskSnapshot`, `cloud_application/graph.py::build_runtime_graph_revision` | `tests/test_cloud_application_models.py` |
| Child tasks preserve requirement coverage | `cloud_application/planning.py::_build_subtask_children`, `cloud_application/validation.py::validate_requirement_coverage` | `tests/test_cloud_application_service.py` |
| Child tasks fit local context limits | `cloud_application/validation.py::validate_context_budget` | `tests/test_cloud_application_validation.py` |
| Child tasks have valid dependencies | `cloud_application/validation.py::validate_dependency_graph` | `tests/test_cloud_application_validation.py` |
| Dependency cycles are rejected | `cloud_application/validation.py::validate_dependency_graph` | `tests/test_cloud_application_validation.py` |
| Missing dependencies are rejected | `cloud_application/planning.py::_build_subtask_children` | `tests/test_cloud_application_service.py` |
| Unsafe writable-path changes are rejected | `cloud_application/validation.py::validate_writable_paths_exact` | `tests/test_cloud_application_validation.py` |
| Approved writable-path changes must match approval | `cloud_application/validation.py::validate_approval_scope` | `tests/test_cloud_application_validation.py` |
| Declared unsupported operation types are rejected explicitly | `cloud_application/models.py::SUPPORTED_REJECTED_APPLICATION_OPERATIONS`, `cloud_application/planning.py::supported_operation_type` | `tests/test_cloud_application_service.py` |
| Task metadata updates are applied through an explicit schema | `cloud_application/planning.py::_build_metadata_update_task` | `tests/test_cloud_application_service.py` |
| Runtime revisions are immutable | `cloud_application/models.py::RuntimePlanRevision`, `cloud_application/graph.py::build_runtime_graph_revision` | `tests/test_cloud_application_models.py` |
| Every revision has a parent | `cloud_application/models.py::RuntimePlanRevision` | `tests/test_cloud_application_models.py` |
| Revision checksums are verified | `cloud_application/persistence.py::load_active_pointer`, `cloud_application/validation.py::validate_active_pointer` | `tests/test_cloud_application_models.py`, `tests/test_cloud_application_service.py` |
| Active revision changes atomically | `cloud_application/persistence.py::save_active_pointer` | `tests/test_cloud_application_service.py` |
| Failed application leaves prior revision active | `cloud_application/transactions.py`, `cloud_application/service.py::_apply_plan` | `tests/test_cloud_application_service.py` |
| Partial revisions are not activated | `cloud_application/transactions.py`, `cloud_application/publication.py::validate_publication_gate` | `tests/test_cloud_application_service.py` |
| Application is idempotent | `cloud_application/service.py::_transition_application`, `cloud_application/transactions.py::save_transaction_phase` | `tests/test_cloud_application_service.py` |
| Concurrent stale applications are rejected | `cloud_application/service.py::_apply_plan`, `cloud_application/persistence.py::load_active_pointer` | `tests/test_cloud_application_service.py` |
| Resume eligibility is calculated after application | `cloud_application/service.py::_build_resume_eligibility` | `tests/test_cloud_application_service.py` |
| Resume preserves unaffected completed tasks | `cloud_application/resume.py::run_runtime_revision_execution` | `tests/test_cloud_application_service.py` |
| Resume skips superseded tasks | `cloud_application/resume.py::run_runtime_revision_execution` | `tests/test_cloud_application_service.py` |
| Resume uses only the active revision | `cloud_application/service.py::resume`, `cloud_application/publication.py::validate_publication_gate` | `tests/test_cloud_application_service.py`, `tests/test_cloud_application_cli.py` |
| Resume uses the existing local execution pipeline | `cloud_application/resume.py::run_runtime_revision_execution` | `tests/test_cloud_application_service.py`, `tests/test_cloud_application_cli.py` |
| Resume performs no cloud call | `cloud_application/service.py::resume`, `cloud_application/resume.py` | `tests/test_cloud_application_service.py` |
| Old-revision task results are rejected | `cloud_application/publication.py::validate_publication_gate` | `tests/test_cloud_application_service.py` |
| Execution leases are revision-bound | `cloud_application/models.py::ExecutionLease`, `cloud_application/service.py::_create_lease` | `tests/test_cloud_application_service.py`, `tests/test_cloud_application_models.py` |
| Automatic resume is disabled by default | `cloud_application/models.py::RuntimeConfig` / runtime config defaults | `tests/test_runtime_config.py` |
| Automatic apply is disabled by default | `cloud_application/models.py::RuntimeConfig` / runtime config defaults | `tests/test_runtime_config.py` |
| Explicit apply works | `cloud_application/service.py::apply`, `cli.py` command wiring | `tests/test_cloud_application_cli.py` |
| Explicit resume works | `cloud_application/service.py::resume`, `cli.py` command wiring | `tests/test_cloud_application_cli.py` |
| Rollback restores the prior active revision | `cloud_application/service.py::rollback` | `tests/test_cloud_application_service.py` |
| Rollback preserves history | `cloud_application/service.py::rollback`, `cloud_application/models.py::RuntimePlanRevision` | `tests/test_cloud_application_service.py`, `tests/test_cloud_application_models.py` |
| Rollback does not silently revert Git changes | `cloud_application/service.py::rollback` | `tests/test_cloud_application_service.py`, `stories/safe-cloud-response-application-and-local-resume/reports/round_trip_report.md` |
| Incomplete transactions are detected | `cloud_application/transactions.py::load_transaction`, `cloud_application/service.py::recover` | `tests/test_cloud_application_service.py` |
| Corrupt active pointers are reported safely | `cloud_application/persistence.py::load_active_pointer`, `cloud_application/service.py::recover` | `tests/test_cloud_application_service.py` |
| Every application action is audited | `cloud_application/audit.py::record_application_audit_event` | `tests/test_cloud_application_service.py` |
| Audit logs contain checksums and state transitions | `cloud_application/audit.py::record_application_audit_event` | `tests/test_cloud_application_service.py`, `tests/test_cloud_application_models.py` |
| Audit logs contain no secrets | `cloud_queue/redaction.py`, `cloud_application/audit.py` | `tests/test_cloud_queue_security.py`, `tests/test_public_readiness.py` |
| Runtime application artifacts are not committed | `.gitignore`, `artifact_policy.py` | `tests/test_artifact_policy.py` |
| Artifact policy detects tracked runtime artifacts | `artifact_policy.py` | `tests/test_artifact_policy.py` |
| Public readiness excludes runtime artifacts | `public_readiness.py` | `tests/test_public_readiness.py` |
| Windows and Linux behavior are equivalent | `cloud_queue/validation.py`, `cloud_application/persistence.py` | `tests/test_cloud_application_service.py`, `tests/test_cloud_queue_security.py` |
| Story 061 behavior remains intact | `cloud_application/validation.py`, `cloud_application/state_machine.py` | `tests/test_cloud_queue_contract.py`, `tests/test_runtime_config.py` |
| Story 062 behavior remains intact | `cloud_application/resume.py`, `cli.py` | `tests/test_demo_subtasks.py`, `tests/test_cloud_queue_cli.py` |
| Story 063 behavior remains intact | `cloud_queue/importers.py`, `cloud_queue/service.py` | `tests/test_cloud_queue_service.py`, `tests/test_cloud_queue_security.py` |
| Generation remains idempotent | `agentic generate-stories` | `stories/safe-cloud-response-application-and-local-resume/reports/test_report.md` |
| CI is deterministic and offline | Docker workflow commands and offline runtime layers | `stories/safe-cloud-response-application-and-local-resume/reports/quality_gate_report.md` |
| No paid provider integration is introduced | `cloud_queue/classification.py`, `cloud_application/service.py` | `tests/test_cloud_queue_security.py`, `tests/test_cloud_application_service.py` |
