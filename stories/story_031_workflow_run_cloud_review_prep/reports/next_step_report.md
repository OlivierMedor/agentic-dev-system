# Next Step Report

## Story

story_031_workflow_run_cloud_review_prep

## Recommendation

Investigate failed workflow-run cloud-review-prep.

## Suggested command

No command. Human review or manual correction is required.

## Why

workflow_run_result.yaml records a failed cloud-review-prep run.

## Details

- Review reports/workflow_run_report.md and the failed local step result.
- Fix the failed local evidence before continuing.

## Evidence inspected

- status.yaml status: ready_for_review
- ready_for_review: true
- agent_plan.yaml: yes
- prompt_pack: yes (7 prompt file(s))
- reports: developer_report.md, finalize_story_report.md, finalize_story_result.yaml, local_review_report.md, next_step_report.md, prepare_story_report.md, quality_gate_report.md, quality_gate_result.yaml, test_layer_report.md, test_layer_result.yaml, test_report.md, workflow_preview_report.md, workflow_preview_result.yaml, workflow_run_report.md, workflow_run_result.yaml
- review_bundle: file_tree.txt, git_diff.patch, git_diff_staged.patch, git_diff_stat.txt, git_log.txt, git_status.txt, handoff.md, pytest_output.txt, ruff_output.txt, skipped_untracked_files.txt, untracked_file_contents.md, untracked_files.txt
- cloud_review_packet/cloud_review_export.md: yes
- remote_dev_validation/remote_dev_packet.md: no
- test_plan.yaml uses test_layers_version: 1: yes
- result files: finalize_story_result.yaml, quality_gate_result.yaml, test_layer_result.yaml, workflow_run_result.yaml

## Warnings

- None.

## Safety reminders

- This command did not execute the recommended command.
- This command did not call cloud models or GitHub APIs.
- This command did not commit, push, merge, deploy, or recommend automatic merge or deployment.
- Human final approval is always required before merge.
