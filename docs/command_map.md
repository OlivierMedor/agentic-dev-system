# Command Map

This map connects user-facing commands to their CLI entry point, core module,
tests, and best-known story workspace. Every listed command enters through
`src/agentic_dev/cli.py`.

When a story mapping is not a direct one-to-one implementation story, the table
uses "best-known mapping" so the link is useful without pretending to be exact.

| Command | Purpose | CLI entry | Core module | Tests | Related story |
| --- | --- | --- | --- | --- | --- |
| `agentic init` | Create the starter project structure. | `src/agentic_dev/cli.py` | `src/agentic_dev/scaffolding.py` | `tests/test_scaffolding.py`, `tests/test_runtime_config.py` | `story_001_project_setup` best-known mapping |
| `agentic generate-stories` | Create story workspaces from `blueprints/blueprint.yaml`. | `src/agentic_dev/cli.py` | `src/agentic_dev/story_generator.py` | `tests/test_story_generator.py` | Project setup / ongoing blueprint stories best-known mapping |
| `agentic assign-agents` | Write the core agent plan for a story. | `src/agentic_dev/cli.py` | `src/agentic_dev/agent_assignment.py` | `tests/test_agent_assignment.py` | `story_004_agent_assignment` |
| `agentic generate-prompts` | Generate prompt pack files for assigned agents. | `src/agentic_dev/cli.py` | `src/agentic_dev/prompt_pack.py` | `tests/test_prompt_pack.py` | `story_006_agent_prompt_packs` |
| `agentic build-context` | Build role-specific context packets for assigned story agents. | `src/agentic_dev/cli.py` | `src/agentic_dev/role_context.py` | `tests/test_role_context.py` | `story_051_role_specific_context_builder` |
| `agentic local-execute` | Execute assigned story roles with local models only, using blueprint-selected agents and bounded writable paths. | `src/agentic_dev/cli.py` | `src/agentic_dev/local_execution.py` | `tests/test_local_execution.py` | `story_060_blueprint_local_model_execution` best-known mapping |
| `agentic codex-task create` | Create Codex-ready task files from role context packets without invoking Codex. | `src/agentic_dev/cli.py` | `src/agentic_dev/codex_runtime.py` | `tests/test_codex_runtime.py` | `story_052_codex_runtime_connector` |
| `agentic prepare-story` | Prepare a story by assigning agents, writing prompts, runbook, report, and status. | `src/agentic_dev/cli.py` | `src/agentic_dev/prepare_story.py` | `tests/test_prepare_story.py` | `story_007_prepare_story_command` |
| `agentic review-bundle` | Collect local review evidence for a story. | `src/agentic_dev/cli.py` | `src/agentic_dev/review_bundle.py` | `tests/test_review_bundle.py` | `story_002_review_bundle_command` best-known mapping |
| `agentic quality-gate` | Decide whether local evidence is ready for review or needs changes. | `src/agentic_dev/cli.py` | `src/agentic_dev/quality_gate.py` | `tests/test_quality_gate.py` | `story_005_quality_gate` |
| `agentic finalize-story` | Generate review evidence, run quality gate, write finalize reports, and update status. | `src/agentic_dev/cli.py` | `src/agentic_dev/finalize_story.py` | `tests/test_finalize_story.py` | `story_008_finalize_story_command` |
| `agentic artifact-policy` | Block tracked generated artifacts, secrets-like files, and local runtime files. | `src/agentic_dev/cli.py` | `src/agentic_dev/artifact_policy.py` | `tests/test_artifact_policy.py`, `tests/test_public_launch_docs.py` | `story_011_artifact_policy_guard` |
| `agentic public-readiness` | Check tracked files for public-release hygiene problems. | `src/agentic_dev/cli.py` | `src/agentic_dev/public_readiness.py` | `tests/test_public_readiness.py`, `tests/test_public_launch_docs.py` | `story_033_public_readiness_private_instructions` |
| `agentic runtime-config validate` | Validate `.agentic/agent_runtime.yaml`. | `src/agentic_dev/cli.py` | `src/agentic_dev/runtime_config.py` | `tests/test_runtime_config.py` | `story_013_dynamic_agent_runtime_config` |
| `agentic runtime-config show` | Print `.agentic/agent_runtime.yaml`. | `src/agentic_dev/cli.py` | `src/agentic_dev/runtime_config.py` | `tests/test_runtime_config.py` | `story_013_dynamic_agent_runtime_config` |
| `agentic project-status` | Summarize status across stories and queues. | `src/agentic_dev/cli.py` | `src/agentic_dev/project_status.py` | `tests/test_project_status.py` | `story_018_project_status_dashboard` best-known mapping |
| `agentic next-step` | Recommend the next safe action for one story. | `src/agentic_dev/cli.py` | `src/agentic_dev/next_step.py` | `tests/test_next_step.py` | `story_026_story_next_step_advisor` |
| `agentic cloud-review-packet` | Create a manual cloud review handoff packet without calling a cloud model. | `src/agentic_dev/cli.py` | `src/agentic_dev/cloud_review_packet.py` | `tests/test_cloud_review_packet.py` | `story_010_cloud_review_packet` |
| `agentic record-cloud-review` | Record a manual cloud review decision and update story status. | `src/agentic_dev/cli.py` | `src/agentic_dev/cloud_review_result.py` | `tests/test_cloud_review_result.py` | `story_016_cloud_review_result_recording` |
| `agentic merge-readiness` | Check whether evidence is ready for the human merge decision. | `src/agentic_dev/cli.py` | `src/agentic_dev/merge_readiness.py` | `tests/test_merge_readiness.py` | `story_017_merge_readiness_gate` |
| `agentic remote-dev-packet` | Create a manual remote-dev validation packet. | `src/agentic_dev/cli.py` | `src/agentic_dev/remote_dev_validation.py` | `tests/test_remote_dev_validation.py` | `story_024_remote_dev_validation_bundle` |
| `agentic record-remote-dev` | Record manual remote-dev validation evidence. | `src/agentic_dev/cli.py` | `src/agentic_dev/remote_dev_validation.py` | `tests/test_remote_dev_validation.py` | `story_024_remote_dev_validation_bundle` |
| `agentic queue create` | Create a generic improvement, maintenance, or feature queue item. | `src/agentic_dev/cli.py` | `src/agentic_dev/queue_management.py` | `tests/test_queue_management.py` | `story_019_queue_management` best-known mapping |
| `agentic queue list` | List queue items by type and status. | `src/agentic_dev/cli.py` | `src/agentic_dev/queue_management.py` | `tests/test_queue_management.py` | `story_019_queue_management` best-known mapping |
| `agentic queue show` | Show one queue item. | `src/agentic_dev/cli.py` | `src/agentic_dev/queue_management.py` | `tests/test_queue_management.py` | `story_019_queue_management` best-known mapping |
| `agentic queue set-status` | Move a queue item to a new status folder. | `src/agentic_dev/cli.py` | `src/agentic_dev/queue_management.py` | `tests/test_queue_management.py` | `story_019_queue_management` best-known mapping |
| `agentic queue promote-to-story` | Promote an approved queue item into the blueprint and story workspace. | `src/agentic_dev/cli.py` | `src/agentic_dev/queue_management.py` | `tests/test_queue_management.py` | `story_019_queue_management` best-known mapping |
| `agentic improvement-scan create` | Create a post-story improvement scan packet. | `src/agentic_dev/cli.py` | `src/agentic_dev/improvement_scan.py` | `tests/test_improvement_scan.py` | `story_021_post_story_improvement_scan` |
| `agentic improvement-scan record` | Record improvement suggestions into the improvement queue. | `src/agentic_dev/cli.py` | `src/agentic_dev/improvement_scan.py` | `tests/test_improvement_scan.py` | `story_021_post_story_improvement_scan` |
| `agentic maintenance-scan create` | Create a reactive maintenance scan packet. | `src/agentic_dev/cli.py` | `src/agentic_dev/maintenance_scan.py` | `tests/test_maintenance_scan.py` | `story_022_reactive_maintenance_scan` |
| `agentic maintenance-scan record` | Record maintenance findings into the maintenance queue. | `src/agentic_dev/cli.py` | `src/agentic_dev/maintenance_scan.py` | `tests/test_maintenance_scan.py` | `story_022_reactive_maintenance_scan` |
| `agentic feature-scan create` | Create a project-level feature discovery packet. | `src/agentic_dev/cli.py` | `src/agentic_dev/feature_scan.py` | `tests/test_feature_scan.py` | `story_023_project_feature_discovery_scan` |
| `agentic feature-scan record` | Record feature suggestions into the feature queue. | `src/agentic_dev/cli.py` | `src/agentic_dev/feature_scan.py` | `tests/test_feature_scan.py` | `story_023_project_feature_discovery_scan` |
| `agentic support-ticket create` | Create a support ticket for blocked story work. | `src/agentic_dev/cli.py` | `src/agentic_dev/support_queue.py` | `tests/test_support_queue.py` | `story_012_agent_support_queue` |
| `agentic support-ticket list` | List support tickets. | `src/agentic_dev/cli.py` | `src/agentic_dev/support_queue.py` | `tests/test_support_queue.py` | `story_012_agent_support_queue` |
| `agentic support-ticket cloud-packet` | Create a manual cloud review packet for a support ticket. | `src/agentic_dev/cli.py` | `src/agentic_dev/support_queue.py` | `tests/test_support_queue.py` | `story_012_agent_support_queue` |
| `agentic support-ticket answer` | Record an answer and move the ticket to answered. | `src/agentic_dev/cli.py` | `src/agentic_dev/support_queue.py` | `tests/test_support_queue.py` | `story_012_agent_support_queue` |
| `agentic support-ticket close` | Move a support ticket to closed. | `src/agentic_dev/cli.py` | `src/agentic_dev/support_queue.py` | `tests/test_support_queue.py` | `story_012_agent_support_queue` |
| `agentic workflow-preview` | Preview the next workflow route with LangGraph-safe local logic. | `src/agentic_dev/cli.py` | `src/agentic_dev/workflow_preview.py` | `tests/test_workflow_preview.py` | `story_027_langgraph_workflow_preview` |
| `agentic workflow-run` | Plan or execute hardcoded safe local workflow phases. | `src/agentic_dev/cli.py` | `src/agentic_dev/workflow_run.py` | `tests/test_workflow_run.py`, `tests/e2e/test_agentic_workflow.py` | `story_028_langgraph_safe_workflow_runner`, `story_030_workflow_run_prepare_phase`, `story_031_workflow_run_cloud_review_prep` best-known mapping |

## Reading The Map

Use the table from left to right:

1. Start with the command a user runs.
2. Open `src/agentic_dev/cli.py` to see arguments and dispatch.
3. Open the core module to understand behavior.
4. Open the test file to see expected behavior.
5. Open the related story folder when you need the original acceptance criteria
   or review reports.
