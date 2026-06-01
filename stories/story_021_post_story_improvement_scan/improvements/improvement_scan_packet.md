# Improvement Scan Packet

This packet is for a post-story improvement scan. Use only the context in this file.
Do not call cloud models automatically. Do not call internet search.

## Reviewer instructions

- suggest improvements only within this story's scope.
- do not propose unrelated features.
- do not expand the completed story.
- create suggestions for future review only.
- use the suggestions template format.

## Story name

story_021_post_story_improvement_scan

## Story content

Source: `story.md`

```markdown
# STORY-021: Add post-story improvement scan

## Goal

Create commands that let the system generate an improvement scan packet for a completed story and record structured improvement suggestions into the improvement queue.

## Why This Matters

After a story is completed, the Research Agent or cloud model should be able to suggest focused improvements within that story's scope. These suggestions should go into the improvement queue for human/cloud review instead of expanding the current story.

## Acceptance Criteria

- Add improvement-scan create command.
- Add improvement-scan record command.
- improvement-scan create requires --story.
- improvement-scan create defaults --project to the current working directory.
- improvement-scan create validates that the story folder exists.
- improvement-scan create writes stories/<story>/improvements/improvement_scan_packet.md.
- improvement-scan create writes stories/<story>/improvements/improvement_suggestions_template.yaml.
- The packet includes story content, reports, test layer result, finalize result, local review report, and review bundle handoff when present.
- The packet instructs the reviewer to suggest improvements only within the completed story's scope.
- The packet instructs the reviewer not to propose unrelated features.
- improvement-scan record requires --story and --suggestions-file.
- improvement-scan record validates suggestion YAML.
- improvement-scan record creates improvement queue items under .agentic/improvement_queue/pending.
- Each recorded improvement item includes source_story, title, category, priority, details, expected_benefit, suggested_acceptance_criteria, and next_action.
- improvement-scan record writes stories/<story>/improvements/improvement_record_report.md.
- Tests verify packet creation, template creation, suggestion validation, and queue item creation.
- README documents the post-story improvement workflow.

## Not In Scope

- No automatic cloud model call.
- No internet research yet.
- No automatic story creation from suggestions.
- No automatic implementation of improvements.
- No LangGraph yet.
- No web dashboard.

## Definition of Done

- pytest passes.
- ruff passes.
- artifact-policy passes.
- runtime-config validate passes.
- improvement-scan create works.
- improvement-scan record works with a sample suggestions file.
- finalize-story marks this story ready for review.
```

## Story status

Source: `status.yaml`

```yaml
story_id: STORY-021
status: ready_for_review
ready_for_review: true
```

## Developer report

Source: `reports/developer_report.md`

```markdown
# Developer Report

## Files changed

- `src/agentic_dev/improvement_scan.py`
- `src/agentic_dev/cli.py`
- `README.md`
- `stories/story_021_post_story_improvement_scan/reports/developer_report.md`

## What I did

- Added post-story improvement scan packet creation.
- Added improvement suggestions YAML template creation.
- Added validated suggestion recording into `.agentic/improvement_queue/pending/` with `IMP`
  queue item IDs.
- Added an improvement record report under `stories/<story>/improvements/`.
- Wired the new `agentic improvement-scan create` and `agentic improvement-scan record`
  commands into the CLI.
- Documented the post-story improvement workflow in the README.

## Validation performed

- `docker compose run --rm dev ruff check .` passed.
- `docker compose run --rm dev pytest` passed with 167 tests.
- `docker compose run --rm dev agentic artifact-policy` passed.
- `docker compose run --rm dev agentic runtime-config validate` passed.
- Smoke tested `improvement-scan create` and `improvement-scan record` through the CLI against an
  isolated `/tmp` project in the Docker dev container.

## Assumptions

- The Test Agent will add the dedicated tests required by the story.
- Improvement scan packets and suggestion templates are generated local artifacts and are created
  by command execution, not prewritten into this story workspace.
- `next_action` for recorded suggestions should use the existing pending queue next action.

## Warnings or uncertainty

- I did not add or update tests, per the Developer Agent rule.
- I did not run `finalize-story` for this story because local review and the independent Test Agent
  work are still expected later in the workflow.
- `blueprints/blueprint.yaml` was already modified before my work and was left untouched.
```

## Test report

Source: `reports/test_report.md`

```markdown
# Test Report: STORY-021 Post-Story Improvement Scan

## Files changed

- `tests/test_improvement_scan.py`
- `stories/story_021_post_story_improvement_scan/reports/test_layer_result.yaml`
- `stories/story_021_post_story_improvement_scan/reports/test_layer_report.md`
- `stories/story_021_post_story_improvement_scan/reports/test_report.md`

## What I did

- Added independent tests for improvement scan packet creation and suggestion recording.
- Verified `improvement-scan create` validates the story folder, writes the packet and suggestions template, includes available story evidence, keeps reviewer instructions in story scope, and does not overwrite existing files unless `force=True`.
- Verified `improvement-scan record` validates suggestion YAML, rejects missing suggestion lists and required fields, creates pending improvement queue items, preserves `source_story` and `suggested_acceptance_criteria`, and writes `improvement_record_report.md`.
- Added CLI coverage for required arguments, current-directory project defaults, and running without a Git repository, cloud credentials, or network access.
- Confirmed the story test plan addresses unit, integration, mock E2E, live read-only, and remote dev smoke layers.

## Validation performed

- `docker compose run --rm dev pytest`
  - Passed: 182 tests.
- `docker compose run --rm dev ruff check .`
  - Passed.
- `docker compose run --rm dev agentic artifact-policy`
  - Passed.
- `docker compose run --rm dev agentic runtime-config validate`
  - Passed.
- `docker compose run --rm dev agentic test-layers --story story_021_post_story_improvement_scan`
  - Passed.

## Assumptions

- The existing `src/agentic_dev/improvement_scan.py`, CLI wiring, README updates, and blueprint/story setup were produced by other agents and were treated as implementation/docs context.
- No implementation code changes were needed to make the tests runnable.
- Integration and mock E2E layers are covered by existing command-pattern and local workflow tests; this story adds focused unit/CLI tests for the new improvement scan behavior.
- Live read-only checks are not applicable because the feature is local-only and must not call external services.
- Remote dev smoke tests are not applicable because no remote dev environment exists yet.

## Warnings or uncertainty

- The working tree already contained unrelated modified and untracked implementation/docs/story files before this Test Agent work. I did not revert or alter those files.
- The `test-layers` command generated `test_layer_result.yaml` and `test_layer_report.md` under this story's reports directory as part of validation.
```

## Local review report

Source: `reports/local_review_report.md`

```markdown
# Local Review Report: STORY-021 Post-Story Improvement Scan

Status: READY_FOR_REVIEW

## Files changed

- `stories/story_021_post_story_improvement_scan/reports/local_review_report.md`
- `stories/story_021_post_story_improvement_scan/improvements/improvement_scan_packet.md`
- `stories/story_021_post_story_improvement_scan/improvements/improvement_suggestions_template.yaml`
- `stories/story_021_post_story_improvement_scan/improvements/improvement_record_report.md`
- `.tmp/story021_sample_suggestions.yaml`
- `.agentic/improvement_queue/pending/IMP-20260601-162757.yaml`
- Finalize-story also refreshed generated review and report artifacts under `stories/story_021_post_story_improvement_scan/`.

## What I did

- Reviewed `src/agentic_dev/improvement_scan.py`, `src/agentic_dev/cli.py`, `tests/test_improvement_scan.py`, `README.md`, story reports, and generated improvement artifacts.
- Verified `improvement-scan create` produces a useful packet from local story evidence.
- Verified the packet restricts suggestions to this story's scope, rejects unrelated feature expansion, and says not to call cloud models automatically or internet search.
- Created a small sample suggestions YAML for this story and verified `improvement-scan record` accepts valid YAML and writes a pending improvement queue item.
- Verified the recorded sample item was not promoted to the blueprint or a story workspace.
- Updated this local review report with `READY_FOR_REVIEW` only after checks passed.
- Ran `finalize-story --force` after writing the local review report and confirmed the story reached `ready_for_review`.

## Validation performed

- `docker compose run --rm dev pytest`
  - Passed: 182 tests.
- `docker compose run --rm dev ruff check .`
  - Passed.
- `docker compose run --rm dev agentic artifact-policy`
  - Passed.
- `docker compose run --rm dev agentic runtime-config validate`
  - Passed.
- `docker compose run --rm dev agentic test-layers --story story_021_post_story_improvement_scan`
  - Passed with `status: PASSED`.
- `docker compose run --rm dev agentic improvement-scan create --story story_021_post_story_improvement_scan --force`
  - Passed and generated the scan packet and suggestions template.
- `docker compose run --rm dev agentic improvement-scan record --story story_021_post_story_improvement_scan --suggestions-file .tmp/story021_sample_suggestions.yaml`
  - Passed and created pending queue item `IMP-20260601-162757`.
- `docker compose run --rm dev agentic finalize-story --story story_021_post_story_improvement_scan --force`
  - Passed with `status: ready_for_review` and `ready_for_review: true`.

## Assumptions

- The sample suggestion file and generated sample queue item are validation artifacts, not intentional test fixtures.
- The generated improvement scan packet is allowed to list optional evidence as missing when that evidence does not exist at packet creation time.
- Network avoidance is satisfied by the local implementation path and tests that fail socket access for the improvement scan commands.

## Warnings or uncertainty

- `.tmp/story021_sample_suggestions.yaml` and `.agentic/improvement_queue/pending/IMP-20260601-162757.yaml` should not be committed unless intentionally converted into fixtures.
- The first forced packet creation happened before this local review report, finalization result, and review bundle handoff existed, so the packet correctly listed those files as missing optional evidence at that time.
- No commit was made.
```

## Test layer result

Source: `reports/test_layer_result.yaml`

```yaml
story: story_021_post_story_improvement_scan
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
    evidence_or_reason: Add unit tests for improvement scan packet creation and suggestion
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
    evidence_or_reason: No remote dev environment exists yet.
    failed_checks: []
next_action: Continue to the quality gate or finalize-story workflow.
```

## Finalize story result

Source: `reports/finalize_story_result.yaml`

```yaml
story: story_021_post_story_improvement_scan
status: ready_for_review
ready_for_review: true
review_bundle_path: /app/stories/story_021_post_story_improvement_scan/review_bundle
quality_gate_result_path: /app/stories/story_021_post_story_improvement_scan/reports/quality_gate_result.yaml
test_layer_result_path: /app/stories/story_021_post_story_improvement_scan/reports/test_layer_result.yaml
finalize_report_path: /app/stories/story_021_post_story_improvement_scan/reports/finalize_story_report.md
next_action: Send the story to a human or cloud reviewer.
```

## Review bundle handoff

Source: `review_bundle/handoff.md`

```markdown
# Review Bundle Handoff

## Story

story_021_post_story_improvement_scan

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
- untracked files: 37
- skipped untracked files: 0
- staged changes: no
- unstaged changes: yes

## Git status summary

551 changed or untracked path(s).

## Next recommended action

Review the bundle, then ask a human reviewer to approve or request changes.
```

## Missing optional evidence

No optional evidence files are missing.
