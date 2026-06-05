# Workflow Preview Report

## Story

story_032_golden_path_operator_guide

## Why LangGraph is being used here

This is the first LangGraph integration for the workflow. It is a preview graph only: it reads
story state, routes through explicit nodes, and explains the next safe action without executing
agents or calling models. LangGraph is being introduced here so future orchestration can reuse the
same route shape after the workflow rules are clear.

## Graph nodes visited

- collect_story_state
- determine_next_action
- write_preview

## Evidence inspected

- story.md
- status.yaml
- test_plan.yaml
- agent_plan.yaml
- prompt_pack/
- prompt_pack/01_research_agent_prompt.md
- prompt_pack/02_planner_agent_prompt.md
- prompt_pack/03_developer_agent_prompt.md
- prompt_pack/04_test_agent_prompt.md
- prompt_pack/05_docs_agent_prompt.md
- prompt_pack/06_security_quality_agent_prompt.md
- prompt_pack/07_local_reviewer_agent_prompt.md
- reports/developer_report.md
- reports/docs_report.md
- reports/finalize_story_report.md
- reports/finalize_story_result.yaml
- reports/local_review_report.md
- reports/planner_report.md
- reports/prepare_story_report.md
- reports/quality_gate_report.md
- reports/quality_gate_result.yaml
- reports/research_report.md
- reports/security_quality_report.md
- reports/test_layer_report.md
- reports/test_layer_result.yaml
- reports/test_report.md
- reports/workflow_preview_report.md
- reports/workflow_preview_result.yaml
- reports/workflow_run_report.md
- reports/workflow_run_result.yaml
- review_bundle/.gitkeep
- review_bundle/file_tree.txt
- review_bundle/git_diff.patch
- review_bundle/git_diff_staged.patch
- review_bundle/git_diff_stat.txt
- review_bundle/git_log.txt
- review_bundle/git_status.txt
- review_bundle/handoff.md
- review_bundle/pytest_output.txt
- review_bundle/ruff_output.txt
- review_bundle/skipped_untracked_files.txt
- review_bundle/untracked_file_contents.md
- review_bundle/untracked_files.txt

## Current state

- status.yaml status: ready_for_review
- ready_for_review: true
- agent_plan.yaml: yes
- prompt_pack: yes (7 prompt file(s))
- reports: developer_report.md, docs_report.md, finalize_story_report.md, finalize_story_result.yaml, local_review_report.md, planner_report.md, prepare_story_report.md, quality_gate_report.md, quality_gate_result.yaml, research_report.md, security_quality_report.md, test_layer_report.md, test_layer_result.yaml, test_report.md, workflow_preview_report.md, workflow_preview_result.yaml, workflow_run_report.md, workflow_run_result.yaml
- review_bundle: .gitkeep, file_tree.txt, git_diff.patch, git_diff_staged.patch, git_diff_stat.txt, git_log.txt, git_status.txt, handoff.md, pytest_output.txt, ruff_output.txt, skipped_untracked_files.txt, untracked_file_contents.md, untracked_files.txt
- cloud_review_packet/cloud_review_export.md: no
- remote_dev_validation/remote_dev_packet.md: no
- test_plan.yaml uses test_layers_version: 1: yes
- result files: finalize_story_result.yaml, quality_gate_result.yaml, test_layer_result.yaml, workflow_run_result.yaml

## Recommended next action

Run workflow-run cloud-review-prep.

## Suggested command

agentic workflow-run --story story_032_golden_path_operator_guide --phase cloud-review-prep --execute

## Why

finalize-story is ready, but the cloud review export packet does not exist.

## Details

- Expected cloud_review_packet/cloud_review_export.md.
- workflow-run cloud-review-prep wraps cloud-review-packet and workflow-preview safely.
- It creates local cloud review evidence only; it does not call cloud models, call GitHub APIs, commit, push, merge, or deploy.

## Warnings

- None.

## Safety reminders

- This is a preview graph only.
- It did not execute agents through the configured agent runtime.
- It did not call cloud models or GitHub APIs.
- It did not run shell commands, commit, push, merge, or deploy.
- It does not recommend automatic merge or automatic deployment.
- Human final approval is always required before merge.

## Future orchestration notes

Later LangGraph workflows may orchestrate prepare-story, configured agent runtime execution,
finalize-story, cloud review packet creation, merge readiness, remote-dev evidence routing, and
support queue pauses. This preview does not use LangGraph persistence, checkpointing, or
human-in-the-loop pause/resume yet.
