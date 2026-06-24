# Quality Gate Report

## Story

evidence-derived-local-execution-recording

## Final status

REQUEST_CHANGES

## Passed checks

- Found required file: story.md
- Found required file: status.yaml
- Found required file: test_plan.yaml
- Found required file: monitoring_plan.yaml
- Found required file: reports/developer_report.md
- Found required file: reports/test_report.md
- Found required file: reports/local_review_report.md
- Found required file: review_bundle/handoff.md
- Found required file: review_bundle/pytest_output.txt
- Found required file: review_bundle/ruff_output.txt
- pytest output shows a passing result.
- Ruff output shows a passing result.
- Test layer result status is PASSED.

## Failed checks

- Missing required file: agent_plan.yaml
- Local execution record is invalid: execution record manifest_checksum does not match canonical manifest; execution record cleanliness mismatch; developer role claimed but missing patch checksum in role_evidence; test role claimed but missing pytest evidence checksum in role_evidence; review decision manifest_checksum mismatch
- A structured local review decision of 'ready_for_review' is required. execution record manifest_checksum does not match canonical manifest; execution record cleanliness mismatch; developer role claimed but missing patch checksum in role_evidence; test role claimed but missing pytest evidence checksum in role_evidence; review decision manifest_checksum mismatch

## Next recommended action

Fix the failed checks, regenerate any missing reports, then run the quality gate again.

## Beginner-friendly explanation

The quality gate checks that the story has the required planning files, workflow reports, review bundle files, passing pytest output, passing Ruff output, and local reviewer approval. If any required item is missing or failed, the story should stay in REQUEST_CHANGES until the evidence is fixed.
