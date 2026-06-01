# Maintenance Scan Packet

This packet is for a reactive maintenance scan. Use only the context in this file.
Do not call cloud models automatically. Do not call internet search.

## Reviewer instructions

- identify broken behavior, regressions, failing checks, missing evidence, or external dependency failures.
- do not implement fixes.
- do not expand scope.
- create findings for maintenance queue review.
- use the findings template format.

## Story name

story_022_reactive_maintenance_scan

## Story content

Source: `story.md`

```markdown
# STORY-022: Add reactive maintenance scan

## Goal

Create commands that generate a maintenance scan packet from story/test/log evidence and record structured maintenance findings into the maintenance queue.

## Why This Matters

When tests, logs, CI, remote dev, or external integrations fail, agents should not guess or silently change code. The system should create a structured maintenance ticket that can be reviewed by the cloud model and human owner before becoming repair work.

## Acceptance Criteria

- Add maintenance-scan create command.
- Add maintenance-scan record command.
- maintenance-scan create requires --story.
- maintenance-scan create defaults --project to the current working directory.
- maintenance-scan create creates stories/<story>/maintenance/maintenance_scan_packet.md.
- maintenance-scan create creates stories/<story>/maintenance/maintenance_findings_template.yaml.
- maintenance-scan packet includes story content, monitoring plan, test plan, review bundle handoff, pytest output, ruff output, quality gate result, finalize result, and optional log files when present.
- maintenance-scan packet instructs the reviewer to identify broken behavior, regressions, or external dependency failures.
- maintenance-scan packet instructs the reviewer not to implement fixes automatically.
- maintenance-scan record requires --story and --findings-file.
- maintenance-scan record validates findings YAML.
- maintenance-scan record creates maintenance queue items under .agentic/maintenance_queue/pending.
- Each maintenance item includes source_story, severity, source_type, problem, evidence, suspected_cause, recommended_action, suggested_acceptance_criteria, and next_action.
- Tests verify packet creation, findings validation, and maintenance queue item creation.
- README documents the reactive maintenance workflow.

## Not In Scope

- No automatic repair.
- No automatic cloud model call.
- No internet lookup yet.
- No scheduled log monitor yet.
- No remote dev validation environment yet.
- No production incident workflow yet.
- No LangGraph yet.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- maintenance-scan create works.
- maintenance-scan record works with a sample findings file.
- finalize-story marks this story ready for review.
```

## Monitoring plan

Source: `monitoring_plan.yaml`

```yaml
logs_required: true
watch_for:
- missing_maintenance_scan_packet
- invalid_maintenance_findings_yaml
- failed_maintenance_queue_recording
- accidental_auto_fix_attempt
- external_dependency_failure
```

## Test plan

Source: `test_plan.yaml`

```yaml
test_layers_version: 1
unit_tests:
  required: true
  action: add_or_update
  frequency: every_commit
  evidence_or_reason: Add unit tests for maintenance scan packet creation and findings
    recording.
integration_tests:
  required: true
  action: confirm_existing
  frequency: every_pull_request
  evidence_or_reason: Existing command tests cover CLI integration patterns.
mock_e2e_tests:
  required: true
  action: confirm_existing
  frequency: before_merge
  evidence_or_reason: Existing mock E2E workflow test covers the local story workflow.
live_read_only_checks:
  required: false
  action: not_applicable_with_reason
  frequency: scheduled_or_before_release
  evidence_or_reason: This story does not call live APIs or external services.
remote_dev_smoke_tests:
  required: false
  action: not_applicable_with_reason
  frequency: after_remote_dev_deploy
  evidence_or_reason: No remote dev deployment environment exists yet.
```

## Story status

Source: `status.yaml`

```yaml
story_id: STORY-022
status: ready_for_review
ready_for_review: true
```

## Test layer result

Source: `reports/test_layer_result.yaml`

```yaml
story: story_022_reactive_maintenance_scan
status: PASSED
passed_checks:
- unit_tests is addressed.
- integration_tests is addressed.
- mock_e2e_tests is addressed.
- live_read_only_checks is addressed.
- remote_dev_smoke_tests is addressed.
failed_checks: []
layers:
  unit_tests:
    status: PASSED
    required: true
    action: add_or_update
    frequency: every_commit
    evidence_or_reason: Add unit tests for maintenance scan packet creation and findings
      recording.
    failed_checks: []
  integration_tests:
    status: PASSED
    required: true
    action: confirm_existing
    frequency: every_pull_request
    evidence_or_reason: Existing command tests cover CLI integration patterns.
    failed_checks: []
  mock_e2e_tests:
    status: PASSED
    required: true
    action: confirm_existing
    frequency: before_merge
    evidence_or_reason: Existing mock E2E workflow test covers the local story workflow.
    failed_checks: []
  live_read_only_checks:
    status: PASSED
    required: false
    action: not_applicable_with_reason
    frequency: scheduled_or_before_release
    evidence_or_reason: This story does not call live APIs or external services.
    failed_checks: []
  remote_dev_smoke_tests:
    status: PASSED
    required: false
    action: not_applicable_with_reason
    frequency: after_remote_dev_deploy
    evidence_or_reason: No remote dev deployment environment exists yet.
    failed_checks: []
next_action: Continue to the quality gate or finalize-story workflow.
```

## Quality gate result

Source: `reports/quality_gate_result.yaml`

```yaml
story: story_022_reactive_maintenance_scan
status: READY_FOR_REVIEW
passed_checks:
- 'Found required file: story.md'
- 'Found required file: status.yaml'
- 'Found required file: test_plan.yaml'
- 'Found required file: monitoring_plan.yaml'
- 'Found required file: agent_plan.yaml'
- 'Found required file: reports/developer_report.md'
- 'Found required file: reports/test_report.md'
- 'Found required file: reports/local_review_report.md'
- 'Found required file: review_bundle/handoff.md'
- 'Found required file: review_bundle/pytest_output.txt'
- 'Found required file: review_bundle/ruff_output.txt'
- pytest output shows a passing result.
- Ruff output shows a passing result.
- Local reviewer marked the story READY_FOR_REVIEW.
- Test layer result status is PASSED.
failed_checks: []
ready_for_review: true
next_action: Send the story to a human or cloud reviewer.
```

## Finalize story result

Source: `reports/finalize_story_result.yaml`

```yaml
story: story_022_reactive_maintenance_scan
status: ready_for_review
ready_for_review: true
review_bundle_path: /app/stories/story_022_reactive_maintenance_scan/review_bundle
quality_gate_result_path: /app/stories/story_022_reactive_maintenance_scan/reports/quality_gate_result.yaml
test_layer_result_path: /app/stories/story_022_reactive_maintenance_scan/reports/test_layer_result.yaml
finalize_report_path: /app/stories/story_022_reactive_maintenance_scan/reports/finalize_story_report.md
next_action: Send the story to a human or cloud reviewer.
```

## Local review report

Source: `reports/local_review_report.md`

```markdown
# Local Review Report: STORY-022 Reactive Maintenance Scan

Status: READY_FOR_REVIEW

## Files changed

- `README.md`
- `blueprints/blueprint.yaml`
- `src/agentic_dev/cli.py`
- `src/agentic_dev/maintenance_scan.py`
- `tests/test_maintenance_scan.py`
- `stories/story_022_reactive_maintenance_scan/`

## What I did

- Reviewed `src/agentic_dev/maintenance_scan.py`, `src/agentic_dev/cli.py`, `tests/test_maintenance_scan.py`, `README.md`, Story 022 maintenance artifacts, and story reports.
- Verified `maintenance-scan create` writes `maintenance_scan_packet.md` and `maintenance_findings_template.yaml`.
- Verified the packet is focused on broken behavior, regressions, failing checks, missing evidence, and external dependency failures.
- Verified the packet says not to implement fixes, not to expand scope, not to call cloud models automatically, and not to call internet search.
- Created a disposable sample findings YAML and verified `maintenance-scan record` validates it and writes a pending maintenance queue item.
- Verified the sample queue item included `source_story`, `severity`, `source_type`, `problem`, `evidence`, `suspected_cause`, `recommended_action`, `suggested_acceptance_criteria`, and `next_action`.
- Verified the record command did not promote maintenance items to stories, did not implement fixes, and did not call cloud or internet services.
- Removed the disposable sample findings file and sample maintenance queue item after validation.
- Ran `finalize-story --force` after writing the local review report and confirmed the story reached `ready_for_review`.
- Refreshed the maintenance scan packet after finalization and confirmed it includes quality-gate, finalize, local-review, review-bundle, pytest, and Ruff evidence when those files are present.

## Validation performed

- `docker compose run --rm dev pytest`
  - Passed: 197 tests.
- `docker compose run --rm dev ruff check .`
  - Passed.
- `docker compose run --rm dev agentic artifact-policy`
  - Passed.
- `docker compose run --rm dev agentic runtime-config validate`
  - Passed.
- `docker compose run --rm dev agentic test-layers --story story_022_reactive_maintenance_scan`
  - Passed with `status: PASSED`.
- `docker compose run --rm dev agentic maintenance-scan create --story story_022_reactive_maintenance_scan --force`
  - Passed and generated the packet and template.
- `docker compose run --rm dev agentic maintenance-scan record --story story_022_reactive_maintenance_scan --findings-file .tmp/story022_sample_maintenance_findings.yaml`
  - Passed and created pending queue item `MAINT-20260601-194228`.
- `docker compose run --rm dev agentic finalize-story --story story_022_reactive_maintenance_scan --force`
  - Passed with `status: ready_for_review` and `ready_for_review: true`.
- Refreshed `maintenance-scan create --force` after finalization.
  - Confirmed the packet includes `Review bundle handoff`, `pytest output`, `ruff output`, `Quality gate result`, `Finalize story result`, and `Local review report`.

## Assumptions

- Missing packet evidence is acceptable when the evidence file does not exist yet; the packet lists those paths as missing optional evidence.
- The sample findings file and generated sample queue item were validation artifacts, not intentional fixtures.
- The socket/network guard in the test suite plus the local filesystem-only implementation are sufficient for the no-cloud/no-internet scope of this story.

## Warnings or uncertainty

- The first forced packet creation happened before local review, finalization, quality-gate output, and review-bundle files existed, so the packet initially listed those files as missing optional evidence. It was refreshed after finalization and no longer reports missing optional evidence.
- The disposable sample findings file and sample queue item were removed after validation and should not be committed.
- `maintenance/maintenance_record_report.md` remains as sample command-output evidence from the validation run and references the removed disposable queue item; it should not be treated as live maintenance work.
- No commit was made.
```

## Review bundle handoff

Source: `review_bundle/handoff.md`

```markdown
# Review Bundle Handoff

## Story

story_022_reactive_maintenance_scan

## Project path

`/app`

## Generated files

- `handoff.md`
- `git_status.txt`
- `git_log.txt`
- `git_diff_stat.txt`
- `git_diff_staged.patch`
- `git_diff.patch`
- `untracked_files.txt`
- `pytest_output.txt`
- `ruff_output.txt`
- `untracked_file_contents.md`
- `skipped_untracked_files.txt`
- `file_tree.txt`

## Validation

- pytest: passed
- ruff: passed
- untracked files: 35
- skipped untracked files: 0
- staged changes: no
- unstaged changes: yes

## Git status summary

584 changed or untracked path(s).

## Next recommended action

Review the bundle, then ask a human reviewer to approve or request changes.
```

## pytest output

Source: `review_bundle/pytest_output.txt`

```text
Command: pytest
Exit code: 0
Status: PASSED

STDOUT:
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.0.3, pluggy-1.6.0
rootdir: /app
configfile: pyproject.toml
testpaths: tests
collected 197 items

tests/e2e/test_agentic_workflow.py .                                     [  0%]
tests/test_agent_assignment.py .....                                     [  3%]
tests/test_artifact_policy.py ........                                   [  7%]
tests/test_ci_workflow.py ....                                           [  9%]
tests/test_cloud_review_packet.py ...........                            [ 14%]
tests/test_cloud_review_result.py ...........                            [ 20%]
tests/test_finalize_story.py ........                                    [ 24%]
tests/test_improvement_scan.py ...............                           [ 31%]
tests/test_maintenance_scan.py ...............                           [ 39%]
tests/test_merge_readiness.py ...........                                [ 45%]
tests/test_prepare_story.py .......                                      [ 48%]
tests/test_project_status.py ...........                                 [ 54%]
tests/test_prompt_pack.py .......                                        [ 57%]
tests/test_quality_gate.py ............                                  [ 63%]
tests/test_queue_management.py .....................                     [ 74%]
tests/test_review_bundle.py .......                                      [ 78%]
tests/test_runtime_config.py ............                                [ 84%]
tests/test_scaffolding.py ..                                             [ 85%]
tests/test_story_generator.py ........                                   [ 89%]
tests/test_support_queue.py .........                                    [ 93%]
tests/test_test_layers.py ............                                   [100%]

============================= 197 passed in 1.43s ==============================

STDERR:
```

## ruff output

Source: `review_bundle/ruff_output.txt`

```text
Command: ruff check .
Exit code: 0
Status: PASSED

STDOUT:
All checks passed!

STDERR:
```

## Optional log files

No optional log files were provided.

## Missing optional evidence

No optional evidence files are missing.
