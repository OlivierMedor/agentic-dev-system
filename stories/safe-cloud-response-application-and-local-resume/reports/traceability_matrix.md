# Traceability Matrix

| Story 064 requirement | Implementation area | Evidence |
| --- | --- | --- |
| Eligible responses only | `cloud_application/eligibility.py` | `tests/test_cloud_application_validation.py` |
| Immutable plans | `cloud_application/planning.py` | `tests/test_cloud_application_models.py` |
| Dry run validation | `cloud_application/service.py` | `tests/test_cloud_application_service.py` |
| Immutable revisions | `cloud_application/graph.py` | `tests/test_cloud_application_models.py` |
| Atomic apply | `cloud_application/transactions.py` | `tests/test_cloud_application_service.py` |
| Atomic active pointer | `cloud_application/persistence.py` | `tests/test_cloud_application_service.py` |
| Resume requires explicit command | `cloud_application/resume.py` | `tests/test_cloud_application_cli.py` |
| Revision-bound leases | `cloud_application/leases.py` | `tests/test_cloud_application_service.py` |
| Stale worker rejection | `cloud_application/leases.py` | `tests/test_cloud_application_service.py` |
| Rollback support | `cloud_application/rollback.py` | `tests/test_cloud_application_service.py` |
| Recovery support | `cloud_application/recovery.py` | `tests/test_cloud_application_service.py` |
| Canonical blueprint protection | `artifact_policy.py`, `public_readiness.py` | `tests/test_artifact_policy.py`, `tests/test_public_readiness.py` |
| CLI coverage | `cli.py` | `tests/test_cloud_application_cli.py` |

