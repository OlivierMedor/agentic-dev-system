from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from agentic_dev.agent_assignment import assign_agents
from agentic_dev.artifact_policy import check_artifact_policy, format_artifact_policy_report
from agentic_dev.cloud_review_packet import create_cloud_review_packet
from agentic_dev.cloud_review_result import record_cloud_review
from agentic_dev.cloud_queue import (
    cloud_queue_status,
    create_cloud_queue_request,
    export_cloud_queue_request,
    format_import_result,
    format_request,
    format_request_list,
    format_status,
    import_cloud_queue_response,
    list_cloud_queue_requests,
    approve_cloud_queue_request,
    reject_cloud_queue_request,
    cancel_cloud_queue_request,
    fail_cloud_queue_request,
    show_cloud_queue_request,
)
from agentic_dev.cloud_batch import (
    build_default_batch_service,
    format_batch_record,
    format_batch_status,
    format_orchestration_plan,
)
from agentic_dev.cloud_application import (
    build_default_application_service,
    format_application_record,
    format_application_status,
    format_recovery_result,
    format_resume_result,
)
from agentic_dev.codex_runtime import create_codex_tasks
from agentic_dev.demo_subtasks import add_demo_subtasks_arguments, run_demo_subtasks
from agentic_dev.finalize_story import finalize_story
from agentic_dev.feature_scan import create_feature_scan_packet, record_feature_suggestions
from agentic_dev.improvement_scan import (
    create_improvement_scan_packet,
    record_improvement_suggestions,
)
from agentic_dev.local_model_runtime import (
    DEFAULT_DRY_RUN_PROMPT,
    format_local_model_validation_result,
    run_local_agent_draft,
    run_local_agent_prompt,
    run_local_model_dry_run,
    validate_local_model_runtime_config,
)
from agentic_dev.local_execution import run_local_execution
from agentic_dev.local_execution_recording import record_local_execution
from agentic_dev.local_review import record_local_review
from agentic_dev.local_model_scorecard import (
    create_local_model_scorecard,
    create_local_model_scorecard_report,
    recommend_local_model_roles,
    run_local_model_scorecard,
    scaffold_local_model_scorecard_scores,
)
from agentic_dev.maintenance_scan import (
    create_maintenance_scan_packet,
    record_maintenance_findings,
)
from agentic_dev.merge_readiness import run_merge_readiness
from agentic_dev.micro_readiness import (
    DEFAULT_TARGET_CHARACTERS,
    run_micro_readiness,
)
from agentic_dev.next_step import run_next_step
from agentic_dev.prepare_story import prepare_story
from agentic_dev.project_status import run_project_status
from agentic_dev.prompt_pack import generate_prompt_pack
from agentic_dev.public_readiness import (
    format_public_readiness_terminal_report,
    run_public_readiness,
)
from agentic_dev.quality_gate import run_quality_gate_mode
from agentic_dev.queue_management import (
    ALL_QUEUE_STATUSES,
    ALL_QUEUE_TYPES,
    QUEUE_STATUSES,
    QUEUE_TYPES,
    create_queue_item,
    format_queue_item,
    format_queue_list,
    format_queue_promotion,
    list_queue_items,
    promote_queue_item_to_story,
    set_queue_item_status,
    show_queue_item,
)
from agentic_dev.review_bundle import create_review_bundle
from agentic_dev.remote_dev_validation import (
    create_remote_dev_packet,
    record_remote_dev_validation,
)
from agentic_dev.role_context import (
    DEFAULT_ROLE_CONTEXT_TARGET_CHARACTERS,
    build_role_context,
)
from agentic_dev.runtime_config import show_runtime_config, validate_runtime_config
from agentic_dev.scaffolding import init_project
from agentic_dev.story_generator import generate_stories
from agentic_dev.story_runner import run_next_story, run_story
from agentic_dev.support_queue import (
    answer_support_ticket,
    close_support_ticket,
    create_support_ticket,
    create_support_ticket_cloud_packet,
    format_support_ticket_list,
    list_support_tickets,
)
from agentic_dev.test_layers import run_test_layers
from agentic_dev.workflow_preview import run_workflow_preview
from agentic_dev.workflow_run import (
    LOCAL_FINALIZE_PHASE,
    WORKFLOW_RUN_PHASES,
    run_workflow_run,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agentic",
        description="Reusable agentic development workflow tool.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a project for agentic development.",
    )
    init_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    review_bundle_parser = subparsers.add_parser(
        "review-bundle",
        help="Create a review bundle for a story.",
    )
    review_bundle_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    review_bundle_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    review_bundle_parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Base ref or base SHA used to capture the committed PR diff. Defaults to origin/main.",
    )
    review_bundle_parser.add_argument(
        "--strict-clean",
        action="store_true",
        help="Fail if the repository is dirty, ambiguous, or has stale review evidence.",
    )
    review_bundle_parser.add_argument(
        "--diagnose-git-state",
        action="store_true",
        help="Run git diagnostics without modifying the filesystem and print the report to stdout.",
    )
    review_bundle_parser.add_argument(
        "--allow-generated-artifacts",
        action="store_true",
        help="Allow ignored generated review artifacts during review bundle classification.",
    )
    review_bundle_parser.add_argument(
        "--host-identity-file",
        type=Path,
        help="Path to the host git identity file. If omitted, checks AGENTIC_HOST_GIT_IDENTITY_FILE env var.",
    )

    quality_gate_parser = subparsers.add_parser(
        "quality-gate",
        help="Check whether a story is ready for human or cloud review.",
    )
    quality_gate_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    quality_gate_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    quality_gate_parser.add_argument(
        "--mode",
        choices=["pre-merge", "post-merge"],
        default="pre-merge",
        help="Use pre-merge review readiness checks or clean-checkout post-merge verification.",
    )

    test_layers_parser = subparsers.add_parser(
        "test-layers",
        help="Validate that a story test plan addresses all standard test layers.",
    )
    test_layers_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    test_layers_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )

    generate_stories_parser = subparsers.add_parser(
        "generate-stories",
        help="Generate story workspaces from a blueprint.",
    )
    generate_stories_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    generate_stories_parser.add_argument(
        "--blueprint",
        type=Path,
        help="Blueprint YAML file. Defaults to blueprints/blueprint.yaml inside the project.",
    )

    assign_agents_parser = subparsers.add_parser(
        "assign-agents",
        help="Assign the core agent team to a story.",
    )
    assign_agents_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    assign_agents_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    assign_agents_parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate agent_plan.yaml if it already exists.",
    )

    generate_prompts_parser = subparsers.add_parser(
        "generate-prompts",
        help="Generate Codex-ready prompt files for a story's assigned agents.",
    )
    generate_prompts_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    generate_prompts_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    generate_prompts_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing prompt files.",
    )

    prepare_story_parser = subparsers.add_parser(
        "prepare-story",
        help="Prepare a story workspace for agent execution.",
    )
    prepare_story_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    prepare_story_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    prepare_story_parser.add_argument(
        "--force",
        action="store_true",
        help="Refresh existing agent plan and prompt files.",
    )

    next_step_parser = subparsers.add_parser(
        "next-step",
        help="Recommend the next safe workflow action for a story.",
    )
    next_step_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    next_step_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )

    workflow_preview_parser = subparsers.add_parser(
        "workflow-preview",
        help="Preview the next story workflow route with LangGraph.",
    )
    workflow_preview_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    workflow_preview_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )

    workflow_run_parser = subparsers.add_parser(
        "workflow-run",
        help="Plan or execute safe local story workflow steps with LangGraph.",
    )
    workflow_run_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    workflow_run_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    workflow_run_parser.add_argument(
        "--phase",
        default=LOCAL_FINALIZE_PHASE,
        choices=WORKFLOW_RUN_PHASES,
        help=(
            "Workflow phase to run: prepare, local-finalize, or cloud-review-prep. "
            "Defaults to local-finalize."
        ),
    )
    workflow_run_parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the hardcoded safe local steps. Without this flag, only a plan is written.",
    )

    run_story_parser = subparsers.add_parser(
        "run-story",
        help="Plan or run the one-command local workflow for one story.",
    )
    run_story_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    run_story_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name, slug, or story_id.",
    )
    run_story_parser.add_argument(
        "--execute",
        action="store_true",
        help="Run safe local workflow steps. Without this flag, only a plan is written.",
    )

    run_next_story_parser = subparsers.add_parser(
        "run-next-story",
        help="Plan or run the next runnable story using blueprint order and story status.",
    )
    run_next_story_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    run_next_story_parser.add_argument(
        "--execute",
        action="store_true",
        help="Run safe local workflow steps. Without this flag, only a plan is written.",
    )

    finalize_story_parser = subparsers.add_parser(
        "finalize-story",
        help="Finalize a story by creating evidence, running the quality gate, and updating status.",
    )
    finalize_story_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    finalize_story_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    finalize_story_parser.add_argument(
        "--force",
        action="store_true",
        help="Refresh generated finalize evidence.",
    )

    cloud_review_packet_parser = subparsers.add_parser(
        "cloud-review-packet",
        help="Create a cloud-model-ready review packet for a story.",
    )
    cloud_review_packet_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    cloud_review_packet_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    cloud_review_packet_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing cloud review packet files.",
    )

    cloud_queue_parser = subparsers.add_parser(
        "cloud-queue",
        help="Manage the structured manual cloud escalation queue.",
    )
    cloud_queue_subparsers = cloud_queue_parser.add_subparsers(
        dest="cloud_queue_command",
        required=True,
    )

    cloud_queue_create_parser = cloud_queue_subparsers.add_parser(
        "create",
        help="Create a cloud queue request from a local blocker.",
    )
    cloud_queue_create_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_create_parser.add_argument("--story", required=True)
    cloud_queue_create_parser.add_argument("--title", default="Cloud escalation request")
    cloud_queue_create_parser.add_argument("--details", default="")
    cloud_queue_create_parser.add_argument("--blocker-type", default="local_blocker")
    cloud_queue_create_parser.add_argument("--requirement", action="append", default=[])
    cloud_queue_create_parser.add_argument("--writable-path", action="append", default=[])
    cloud_queue_create_parser.add_argument("--dependency", action="append", default=[])
    cloud_queue_create_parser.add_argument("--context-file", action="append", default=[])
    cloud_queue_create_parser.add_argument("--note", action="append", default=[])
    cloud_queue_create_parser.add_argument("--json", action="store_true")

    cloud_queue_list_parser = cloud_queue_subparsers.add_parser(
        "list",
        help="List cloud queue requests.",
    )
    cloud_queue_list_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_list_parser.add_argument("--state", default="all")
    cloud_queue_list_parser.add_argument("--json", action="store_true")

    cloud_queue_show_parser = cloud_queue_subparsers.add_parser(
        "show",
        help="Show one cloud queue request.",
    )
    cloud_queue_show_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_show_parser.add_argument("--request", required=True)
    cloud_queue_show_parser.add_argument("--json", action="store_true")

    cloud_queue_export_parser = cloud_queue_subparsers.add_parser(
        "export",
        help="Export one request or all ready requests into a manual packet.",
    )
    cloud_queue_export_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_export_parser.add_argument("--request")
    cloud_queue_export_parser.add_argument("--all-ready", action="store_true")
    cloud_queue_export_parser.add_argument("--json", action="store_true")

    cloud_queue_import_parser = cloud_queue_subparsers.add_parser(
        "import",
        help="Import a manual cloud response file or bundle.",
    )
    cloud_queue_import_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_import_parser.add_argument("--file", required=True)
    cloud_queue_import_parser.add_argument("--json", action="store_true")

    cloud_queue_approve_parser = cloud_queue_subparsers.add_parser(
        "approve",
        help="Approve a validated cloud queue response.",
    )
    cloud_queue_approve_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_approve_parser.add_argument("--request", required=True)
    cloud_queue_approve_parser.add_argument("--checksum")
    cloud_queue_approve_parser.add_argument("--note", default="")
    cloud_queue_approve_parser.add_argument("--json", action="store_true")

    cloud_queue_reject_parser = cloud_queue_subparsers.add_parser(
        "reject",
        help="Reject a cloud queue request.",
    )
    cloud_queue_reject_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_reject_parser.add_argument("--request", required=True)
    cloud_queue_reject_parser.add_argument("--note", default="")
    cloud_queue_reject_parser.add_argument("--json", action="store_true")

    cloud_queue_cancel_parser = cloud_queue_subparsers.add_parser(
        "cancel",
        help="Cancel a cloud queue request.",
    )
    cloud_queue_cancel_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_cancel_parser.add_argument("--request", required=True)
    cloud_queue_cancel_parser.add_argument("--reason", default="")
    cloud_queue_cancel_parser.add_argument("--json", action="store_true")

    cloud_queue_fail_parser = cloud_queue_subparsers.add_parser(
        "fail",
        help="Mark a cloud queue request as failed.",
    )
    cloud_queue_fail_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_fail_parser.add_argument("--request", required=True)
    cloud_queue_fail_parser.add_argument("--reason", required=True)
    cloud_queue_fail_parser.add_argument("--json", action="store_true")

    cloud_queue_status_parser = cloud_queue_subparsers.add_parser(
        "status",
        help="Show cloud queue status summary.",
    )
    cloud_queue_status_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_status_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_parser = cloud_queue_subparsers.add_parser(
        "batch",
        help="Orchestrate cloud queue requests as a dependency-aware batch.",
    )
    cloud_queue_batch_subparsers = cloud_queue_batch_parser.add_subparsers(
        dest="cloud_queue_batch_command",
        required=True,
    )

    cloud_queue_batch_list_parser = cloud_queue_batch_subparsers.add_parser(
        "list",
        help="List batch records.",
    )
    cloud_queue_batch_list_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_list_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_show_parser = cloud_queue_batch_subparsers.add_parser(
        "show",
        help="Show one batch record.",
    )
    cloud_queue_batch_show_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_show_parser.add_argument("--batch", required=True)
    cloud_queue_batch_show_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_export_parser = cloud_queue_batch_subparsers.add_parser(
        "export",
        help="Export a batch of ready requests.",
    )
    cloud_queue_batch_export_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_export_parser.add_argument("--batch")
    cloud_queue_batch_export_parser.add_argument("--all-ready", action="store_true")
    cloud_queue_batch_export_parser.add_argument("--request", action="append", default=[])
    cloud_queue_batch_export_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_import_parser = cloud_queue_batch_subparsers.add_parser(
        "import",
        help="Import a batch response bundle.",
    )
    cloud_queue_batch_import_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_import_parser.add_argument("--file", required=True)
    cloud_queue_batch_import_parser.add_argument("--batch")
    cloud_queue_batch_import_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_plan_apply_parser = cloud_queue_batch_subparsers.add_parser(
        "plan-apply",
        help="Build the batch orchestration plan.",
    )
    cloud_queue_batch_plan_apply_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_plan_apply_parser.add_argument("--batch", required=True)
    cloud_queue_batch_plan_apply_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_apply_parser = cloud_queue_batch_subparsers.add_parser(
        "apply",
        help="Apply a planned batch.",
    )
    cloud_queue_batch_apply_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_apply_parser.add_argument("--batch", required=True)
    cloud_queue_batch_apply_parser.add_argument("--dry-run", action="store_true")
    cloud_queue_batch_apply_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_resume_parser = cloud_queue_batch_subparsers.add_parser(
        "resume",
        help="Resume a planned batch.",
    )
    cloud_queue_batch_resume_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_resume_parser.add_argument("--batch", required=True)
    cloud_queue_batch_resume_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_retry_parser = cloud_queue_batch_subparsers.add_parser(
        "retry",
        help="Retry a batch attempt.",
    )
    cloud_queue_batch_retry_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_retry_parser.add_argument("--batch", required=True)
    cloud_queue_batch_retry_parser.add_argument("--reason", default="")
    cloud_queue_batch_retry_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_cancel_parser = cloud_queue_batch_subparsers.add_parser(
        "cancel",
        help="Cancel a batch.",
    )
    cloud_queue_batch_cancel_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_cancel_parser.add_argument("--batch", required=True)
    cloud_queue_batch_cancel_parser.add_argument("--reason", default="")
    cloud_queue_batch_cancel_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_rollback_parser = cloud_queue_batch_subparsers.add_parser(
        "rollback",
        help="Rollback a batch.",
    )
    cloud_queue_batch_rollback_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_rollback_parser.add_argument("--batch", required=True)
    cloud_queue_batch_rollback_parser.add_argument("--reason", default="")
    cloud_queue_batch_rollback_parser.add_argument("--json", action="store_true")

    cloud_queue_batch_status_parser = cloud_queue_batch_subparsers.add_parser(
        "status",
        help="Show batch status.",
    )
    cloud_queue_batch_status_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_batch_status_parser.add_argument("--json", action="store_true")

    cloud_queue_plan_apply_parser = cloud_queue_subparsers.add_parser(
        "plan-apply",
        help="Plan a safe cloud response application without mutating runtime state.",
    )
    cloud_queue_plan_apply_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_plan_apply_parser.add_argument("--request", required=True)
    cloud_queue_plan_apply_parser.add_argument("--dry-run", action="store_true")
    cloud_queue_plan_apply_parser.add_argument("--json", action="store_true")

    cloud_queue_apply_parser = cloud_queue_subparsers.add_parser(
        "apply",
        help="Apply an eligible cloud response to the runtime revision.",
    )
    cloud_queue_apply_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_apply_parser.add_argument("--request", required=True)
    cloud_queue_apply_parser.add_argument("--dry-run", action="store_true")
    cloud_queue_apply_parser.add_argument("--json", action="store_true")

    cloud_queue_resume_parser = cloud_queue_subparsers.add_parser(
        "resume",
        help="Resume local execution from an applied runtime revision.",
    )
    cloud_queue_resume_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_resume_parser.add_argument("--request", required=True)
    cloud_queue_resume_parser.add_argument("--json", action="store_true")

    cloud_queue_rollback_apply_parser = cloud_queue_subparsers.add_parser(
        "rollback",
        help="Roll back an applied application to its prior runtime revision.",
    )
    cloud_queue_rollback_apply_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_rollback_apply_parser.add_argument("--application", required=True)
    cloud_queue_rollback_apply_parser.add_argument("--json", action="store_true")

    cloud_queue_application_status_parser = cloud_queue_subparsers.add_parser(
        "application-status",
        help="Show runtime application status.",
    )
    cloud_queue_application_status_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_application_status_parser.add_argument("--json", action="store_true")

    cloud_queue_application_show_parser = cloud_queue_subparsers.add_parser(
        "application-show",
        help="Show one runtime application record.",
    )
    cloud_queue_application_show_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_application_show_parser.add_argument("--application", required=True)
    cloud_queue_application_show_parser.add_argument("--json", action="store_true")

    cloud_queue_recover_parser = cloud_queue_subparsers.add_parser(
        "recover",
        help="Inspect runtime application state and recommend recovery actions.",
    )
    cloud_queue_recover_parser.add_argument("--project", type=Path, default=Path.cwd())
    cloud_queue_recover_parser.add_argument("--json", action="store_true")

    record_cloud_review_parser = subparsers.add_parser(
        "record-cloud-review",
        help="Record a manual cloud review decision for a story.",
    )
    record_cloud_review_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    record_cloud_review_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    record_cloud_review_parser.add_argument(
        "--result-file",
        type=Path,
        required=True,
        help="Path to the saved cloud model review result file.",
    )

    record_local_execution_parser = subparsers.add_parser(
        "record-local-execution",
        help="Record evidence-derived local execution for a story.",
    )
    record_local_execution_parser.add_argument("--project", type=Path, default=Path.cwd())
    record_local_execution_parser.add_argument("--story", required=True)
    record_local_execution_parser.add_argument("--execution-type", default="manual")
    record_local_execution_parser.add_argument("--executor-name")
    record_local_execution_parser.add_argument("--role", dest="roles", action="append")
    record_local_execution_parser.add_argument("--attestation-file", type=Path)
    record_local_execution_parser.add_argument("--manifest-path", type=Path)
    record_local_execution_parser.add_argument("--dry-run", action="store_true")
    record_local_execution_parser.add_argument("--force", action="store_true")

    record_local_review_parser = subparsers.add_parser(
        "record-local-review",
        help="Record a structured local review decision for a story.",
    )
    record_local_review_parser.add_argument("--project", type=Path, default=Path.cwd())
    record_local_review_parser.add_argument("--story", required=True)
    record_local_review_parser.add_argument("--reviewer")
    record_local_review_parser.add_argument("--decision", default="pending")
    record_local_review_parser.add_argument("--notes")
    record_local_review_parser.add_argument("--force", action="store_true")

    remote_dev_packet_parser = subparsers.add_parser(
        "remote-dev-packet",
        help="Create a remote-dev validation packet for a story.",
    )
    remote_dev_packet_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    remote_dev_packet_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    remote_dev_packet_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing remote dev validation packet files.",
    )

    record_remote_dev_parser = subparsers.add_parser(
        "record-remote-dev",
        help="Record manual remote-dev validation evidence for a story.",
    )
    record_remote_dev_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    record_remote_dev_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    record_remote_dev_parser.add_argument(
        "--result-file",
        type=Path,
        required=True,
        help="Path to the completed remote dev validation result YAML file.",
    )

    improvement_scan_parser = subparsers.add_parser(
        "improvement-scan",
        help="Create and record post-story improvement scan suggestions.",
    )
    improvement_scan_subparsers = improvement_scan_parser.add_subparsers(
        dest="improvement_scan_command",
        required=True,
    )

    improvement_scan_create_parser = improvement_scan_subparsers.add_parser(
        "create",
        help="Create a post-story improvement scan packet.",
    )
    improvement_scan_create_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    improvement_scan_create_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    improvement_scan_create_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing improvement scan files.",
    )

    improvement_scan_record_parser = improvement_scan_subparsers.add_parser(
        "record",
        help="Record post-story improvement suggestions into the improvement queue.",
    )
    improvement_scan_record_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    improvement_scan_record_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    improvement_scan_record_parser.add_argument(
        "--suggestions-file",
        type=Path,
        required=True,
        help="Path to the completed improvement suggestions YAML file.",
    )

    maintenance_scan_parser = subparsers.add_parser(
        "maintenance-scan",
        help="Create and record reactive maintenance scan findings.",
    )
    maintenance_scan_subparsers = maintenance_scan_parser.add_subparsers(
        dest="maintenance_scan_command",
        required=True,
    )

    maintenance_scan_create_parser = maintenance_scan_subparsers.add_parser(
        "create",
        help="Create a reactive maintenance scan packet.",
    )
    maintenance_scan_create_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    maintenance_scan_create_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    maintenance_scan_create_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing maintenance scan files.",
    )
    maintenance_scan_create_parser.add_argument(
        "--logs-path",
        type=Path,
        help="Optional log file or folder to include in the maintenance scan packet.",
    )

    maintenance_scan_record_parser = maintenance_scan_subparsers.add_parser(
        "record",
        help="Record maintenance findings into the maintenance queue.",
    )
    maintenance_scan_record_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    maintenance_scan_record_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    maintenance_scan_record_parser.add_argument(
        "--findings-file",
        type=Path,
        required=True,
        help="Path to the completed maintenance findings YAML file.",
    )

    feature_scan_parser = subparsers.add_parser(
        "feature-scan",
        help="Create and record project-level feature discovery suggestions.",
    )
    feature_scan_subparsers = feature_scan_parser.add_subparsers(
        dest="feature_scan_command",
        required=True,
    )

    feature_scan_create_parser = feature_scan_subparsers.add_parser(
        "create",
        help="Create a project feature discovery scan packet.",
    )
    feature_scan_create_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    feature_scan_create_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing feature scan files.",
    )
    feature_scan_create_parser.add_argument(
        "--focus",
        help="Optional focus area for feature discovery.",
    )

    feature_scan_record_parser = feature_scan_subparsers.add_parser(
        "record",
        help="Record project-level feature suggestions into the feature queue.",
    )
    feature_scan_record_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    feature_scan_record_parser.add_argument(
        "--suggestions-file",
        type=Path,
        required=True,
        help="Path to the completed feature suggestions YAML file.",
    )

    merge_readiness_parser = subparsers.add_parser(
        "merge-readiness",
        help="Check whether a story is ready for the human owner to make the merge decision.",
    )
    merge_readiness_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    merge_readiness_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )

    micro_readiness_parser = subparsers.add_parser(
        "micro-readiness",
        help="Check whether a story is focused enough for agent-specific micro prompts.",
    )
    micro_readiness_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    micro_readiness_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    micro_readiness_parser.add_argument(
        "--target-chars",
        type=int,
        default=DEFAULT_TARGET_CHARACTERS,
        help="Target maximum characters per estimated agent micro prompt. Defaults to 2000.",
    )

    build_context_parser = subparsers.add_parser(
        "build-context",
        help="Build role-specific context packets for assigned story agents.",
    )
    build_context_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    build_context_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    build_context_parser.add_argument(
        "--agent",
        help="Build context for one assigned agent ID.",
    )
    build_context_parser.add_argument(
        "--all",
        action="store_true",
        help="Build context for every assigned agent. Defaults to all when --agent is omitted.",
    )
    build_context_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing role context packets.",
    )
    build_context_parser.add_argument(
        "--target-chars",
        type=int,
        default=DEFAULT_ROLE_CONTEXT_TARGET_CHARACTERS,
        help="Target maximum characters per context packet. Defaults to 8000.",
    )

    local_execute_parser = subparsers.add_parser(
        "local-execute",
        help="Execute assigned story roles with local models only.",
    )
    local_execute_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    local_execute_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    local_execute_parser.add_argument(
        "--role",
        help="Optional single role to execute, such as developer or test.",
    )
    local_execute_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the first required role that is not completed.",
    )
    local_execute_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show resolved models and execution order without executing roles.",
    )

    demo_subtasks_parser = subparsers.add_parser(
        "demo-subtasks",
        help="Run the Story 062 sandboxed subtask execution demo.",
    )
    add_demo_subtasks_arguments(demo_subtasks_parser)

    codex_task_parser = subparsers.add_parser(
        "codex-task",
        help="Create Codex-ready task files from role context packets.",
    )
    codex_task_subparsers = codex_task_parser.add_subparsers(
        dest="codex_task_command",
        required=True,
    )

    codex_task_create_parser = codex_task_subparsers.add_parser(
        "create",
        help="Create Codex-ready task files for one or all assigned agents.",
    )
    codex_task_create_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    codex_task_create_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    codex_task_create_parser.add_argument(
        "--agent",
        help="Create a Codex task for one agent ID.",
    )
    codex_task_create_parser.add_argument(
        "--all",
        action="store_true",
        help="Create Codex tasks for every role context packet. Defaults to all when --agent is omitted.",
    )
    codex_task_create_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing Codex task files.",
    )
    codex_task_create_parser.add_argument(
        "--model",
        help="Write this model recommendation into the task file instead of reading runtime config.",
    )

    project_status_parser = subparsers.add_parser(
        "project-status",
        help="Summarize workflow status across story workspaces.",
    )
    project_status_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    project_status_parser.add_argument(
        "--story",
        help="Optional story folder name under the project's stories folder.",
    )

    artifact_policy_parser = subparsers.add_parser(
        "artifact-policy",
        help="Fail when forbidden generated artifacts or environment files are tracked.",
    )
    artifact_policy_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    public_readiness_parser = subparsers.add_parser(
        "public-readiness",
        help="Check whether tracked files are safe for eventual public release.",
    )
    public_readiness_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    runtime_config_parser = subparsers.add_parser(
        "runtime-config",
        help="Show or validate the project runtime config.",
    )
    runtime_config_subparsers = runtime_config_parser.add_subparsers(
        dest="runtime_config_command",
        required=True,
    )

    runtime_config_show_parser = runtime_config_subparsers.add_parser(
        "show",
        help="Print the project runtime config.",
    )
    runtime_config_show_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    runtime_config_validate_parser = runtime_config_subparsers.add_parser(
        "validate",
        help="Validate the project runtime config.",
    )
    runtime_config_validate_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    local_model_parser = subparsers.add_parser(
        "local-model",
        help="Validate and test a local OpenAI-compatible model runtime.",
    )
    local_model_subparsers = local_model_parser.add_subparsers(
        dest="local_model_command",
        required=True,
    )

    local_model_validate_parser = local_model_subparsers.add_parser(
        "validate",
        help="Validate the local model runtime config.",
    )
    local_model_validate_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    local_model_dry_run_parser = local_model_subparsers.add_parser(
        "dry-run",
        help="Send a simple prompt to the configured local model and save a report.",
    )
    local_model_dry_run_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    local_model_dry_run_parser.add_argument(
        "--prompt",
        default=DEFAULT_DRY_RUN_PROMPT,
        help="Prompt to send to the local model. Defaults to a LOCAL_MODEL_OK check.",
    )

    local_model_scorecard_create_parser = local_model_subparsers.add_parser(
        "scorecard-create",
        help="Create public-safe local model scorecard prompts and scoring template.",
    )
    local_model_scorecard_create_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    local_model_scorecard_create_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing scorecard prompt and template files.",
    )

    local_model_scorecard_run_parser = local_model_subparsers.add_parser(
        "scorecard-run",
        help="Run scorecard prompts against the configured local model and save responses.",
    )
    local_model_scorecard_run_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    local_model_scorecard_run_parser.add_argument(
        "--model-label",
        required=True,
        help="Local label for this model run, such as qwen3-coder-30b.",
    )
    local_model_scorecard_run_parser.add_argument(
        "--prompt-dir",
        type=Path,
        help=(
            "Folder containing scorecard prompt markdown files. Defaults to "
            ".agentic/local_model_scorecard/prompts."
        ),
    )

    local_model_scorecard_report_parser = local_model_subparsers.add_parser(
        "scorecard-report",
        help="Create a manual local model scorecard report from saved results.",
    )
    local_model_scorecard_report_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    local_model_scorecard_scaffold_scores_parser = local_model_subparsers.add_parser(
        "scorecard-scaffold-scores",
        help="Create a blank human scoring file from saved scorecard responses.",
    )
    local_model_scorecard_scaffold_scores_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    local_model_scorecard_scaffold_scores_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing scorecard_scores.yaml file.",
    )

    local_model_scorecard_recommend_parser = local_model_subparsers.add_parser(
        "scorecard-recommend",
        help="Create advisory local model role recommendations from human scores.",
    )
    local_model_scorecard_recommend_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    local_agent_parser = subparsers.add_parser(
        "local-agent",
        help="Run bounded local-agent actions using the local model runtime.",
    )
    local_agent_subparsers = local_agent_parser.add_subparsers(
        dest="local_agent_command",
        required=True,
    )

    local_agent_run_prompt_parser = local_agent_subparsers.add_parser(
        "run-prompt",
        help="Send a prompt file to the local model and save the raw response.",
    )
    local_agent_run_prompt_parser.add_argument(
        "--prompt-file",
        type=Path,
        required=True,
        help="Prompt file to send to the local model.",
    )
    local_agent_run_prompt_parser.add_argument(
        "--output-file",
        type=Path,
        required=True,
        help="File where the raw local model response should be saved.",
    )
    local_agent_run_prompt_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    local_agent_draft_parser = local_agent_subparsers.add_parser(
        "draft",
        help="Send story context to the local model and save a draft report.",
    )
    local_agent_draft_parser.add_argument(
        "--story",
        required=True,
        help="Story folder name under the project's stories folder.",
    )
    local_agent_draft_parser.add_argument(
        "--agent",
        required=True,
        choices=[
            "developer_agent",
            "test_agent",
            "docs_agent",
            "reviewer_agent",
            "maintenance_agent",
        ],
        help="Local draft agent prompt to run.",
    )
    local_agent_draft_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )
    local_agent_draft_parser.add_argument(
        "--prompt-file",
        type=Path,
        help="Optional prompt file override. Relative paths are resolved from the project root.",
    )
    local_agent_draft_parser.add_argument(
        "--prompt-mode",
        choices=["full", "micro", "slim"],
        default="slim",
        help=(
            "Prompt mode for local-agent drafts. slim builds a local-model-friendly context "
            "packet and is the default. micro builds the smallest final-answer-focused "
            "context. full uses the story prompt_pack file. Ignored when --prompt-file is "
            "provided."
        ),
    )
    local_agent_draft_parser.add_argument(
        "--output-file",
        type=Path,
        help="Optional draft output file override. Relative paths are resolved from the project root.",
    )
    local_agent_draft_parser.add_argument(
        "--model-label",
        help="Optional safe label for the loaded local model.",
    )
    local_agent_draft_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing draft output and metadata file.",
    )

    support_ticket_parser = subparsers.add_parser(
        "support-ticket",
        help="Create and manage structured support tickets for blocked agents.",
    )
    support_ticket_subparsers = support_ticket_parser.add_subparsers(
        dest="support_ticket_command",
        required=True,
    )

    support_ticket_create_parser = support_ticket_subparsers.add_parser(
        "create",
        help="Create a support ticket for cloud-model review.",
    )
    support_ticket_create_parser.add_argument("--story", required=True, help="Story folder name.")
    support_ticket_create_parser.add_argument("--agent", required=True, help="Blocked agent name.")
    support_ticket_create_parser.add_argument(
        "--blocker-type",
        required=True,
        help="Short category for the blocker.",
    )
    support_ticket_create_parser.add_argument(
        "--question",
        required=True,
        help="Structured question for the cloud model or human reviewer.",
    )
    support_ticket_create_parser.add_argument(
        "--details",
        help="Optional extra context for the ticket.",
    )
    support_ticket_create_parser.add_argument(
        "--severity",
        default="medium",
        help="Ticket severity. Defaults to medium.",
    )
    support_ticket_create_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    support_ticket_list_parser = support_ticket_subparsers.add_parser(
        "list",
        help="List pending, answered, escalated, and closed support tickets.",
    )
    support_ticket_list_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    support_ticket_cloud_packet_parser = support_ticket_subparsers.add_parser(
        "cloud-packet",
        help="Create a cloud-model-ready packet for a support ticket.",
    )
    support_ticket_cloud_packet_parser.add_argument(
        "--ticket",
        required=True,
        help="Support ticket ID, for example SUPPORT-20260530-120000.",
    )
    support_ticket_cloud_packet_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    support_ticket_answer_parser = support_ticket_subparsers.add_parser(
        "answer",
        help="Record an answer for a support ticket and move it to answered.",
    )
    support_ticket_answer_parser.add_argument(
        "--ticket",
        required=True,
        help="Support ticket ID.",
    )
    support_ticket_answer_parser.add_argument(
        "--answer-file",
        type=Path,
        required=True,
        help="Path to a file containing the answer text.",
    )
    support_ticket_answer_parser.add_argument(
        "--answered-by",
        default="cloud_model",
        help="Responder name. Defaults to cloud_model.",
    )
    support_ticket_answer_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    support_ticket_close_parser = support_ticket_subparsers.add_parser(
        "close",
        help="Close a support ticket and move it to closed.",
    )
    support_ticket_close_parser.add_argument(
        "--ticket",
        required=True,
        help="Support ticket ID.",
    )
    support_ticket_close_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    queue_parser = subparsers.add_parser(
        "queue",
        help="Create and manage improvement, maintenance, and feature queue items.",
    )
    queue_subparsers = queue_parser.add_subparsers(
        dest="queue_command",
        required=True,
    )

    queue_create_parser = queue_subparsers.add_parser(
        "create",
        help="Create a queue item in the selected queue's pending folder.",
    )
    queue_create_parser.add_argument(
        "--type",
        dest="queue_type",
        choices=QUEUE_TYPES,
        required=True,
        help="Queue type.",
    )
    queue_create_parser.add_argument("--title", required=True, help="Queue item title.")
    queue_create_parser.add_argument(
        "--source-story",
        help="Optional source story folder name.",
    )
    queue_create_parser.add_argument(
        "--category",
        help="Optional category for grouping the item.",
    )
    queue_create_parser.add_argument(
        "--priority",
        default="medium",
        help="Queue item priority. Defaults to medium.",
    )
    queue_create_parser.add_argument(
        "--details",
        help="Optional details for the queue item.",
    )
    queue_create_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    queue_list_parser = queue_subparsers.add_parser(
        "list",
        help="List queue items by type and status.",
    )
    queue_list_parser.add_argument(
        "--type",
        dest="queue_type",
        choices=ALL_QUEUE_TYPES,
        default="all",
        help="Queue type filter. Defaults to all.",
    )
    queue_list_parser.add_argument(
        "--status",
        choices=ALL_QUEUE_STATUSES,
        default="all",
        help="Queue status filter. Defaults to all.",
    )
    queue_list_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    queue_show_parser = queue_subparsers.add_parser(
        "show",
        help="Show one queue item clearly.",
    )
    queue_show_parser.add_argument("--item", required=True, help="Queue item ID.")
    queue_show_parser.add_argument(
        "--type",
        dest="queue_type",
        choices=QUEUE_TYPES,
        help="Optional queue type hint.",
    )
    queue_show_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    queue_set_status_parser = queue_subparsers.add_parser(
        "set-status",
        help="Move a queue item to a new status folder and record the decision.",
    )
    queue_set_status_parser.add_argument("--item", required=True, help="Queue item ID.")
    queue_set_status_parser.add_argument(
        "--status",
        choices=QUEUE_STATUSES,
        required=True,
        help="New queue status.",
    )
    queue_set_status_parser.add_argument(
        "--decision-note",
        help="Optional note explaining the status decision.",
    )
    queue_set_status_parser.add_argument(
        "--type",
        dest="queue_type",
        choices=QUEUE_TYPES,
        help="Optional queue type hint.",
    )
    queue_set_status_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    queue_promote_parser = queue_subparsers.add_parser(
        "promote-to-story",
        help="Promote an approved queue item into a blueprint story and story workspace.",
    )
    queue_promote_parser.add_argument("--item", required=True, help="Queue item ID.")
    queue_promote_parser.add_argument(
        "--type",
        dest="queue_type",
        choices=QUEUE_TYPES,
        help="Optional queue type hint.",
    )
    queue_promote_parser.add_argument(
        "--allow-pending",
        action="store_true",
        help="Allow manually promoting a pending item.",
    )
    post_promotion_group = queue_promote_parser.add_mutually_exclusive_group()
    post_promotion_group.add_argument(
        "--close-after-promotion",
        action="store_true",
        help="Move the queue item to closed after promotion.",
    )
    post_promotion_group.add_argument(
        "--park-after-promotion",
        action="store_true",
        help="Move the queue item to parked after promotion.",
    )
    queue_promote_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Target project folder. Defaults to the current directory.",
    )

    args = parser.parse_args()

    try:
        if args.command == "init":
            created_paths = init_project(args.project)

            print(f"Initialized agentic project at: {args.project.resolve()}")

            if created_paths:
                print("\nCreated:")
                for path in created_paths:
                    print(f"  - {path}")
            else:
                print("\nNo new files created. Project already appears initialized.")

        if args.command == "review-bundle":
            result = create_review_bundle(
                args.project,
                args.story,
                base_ref=args.base_ref,
                strict_clean=args.strict_clean,
                diagnose_git_state=args.diagnose_git_state,
                allow_generated_artifacts=args.allow_generated_artifacts,
                host_identity_file=args.host_identity_file,
            )

            from agentic_dev.review_bundle import ReviewBundleDiagnosticsResult
            if isinstance(result, ReviewBundleDiagnosticsResult):
                print(result.diagnostics_report, end="")
            else:
                print(f"Review bundle created at: {result.review_bundle_path}")
                print(f"pytest passed: {result.pytest_passed}")
                print(f"ruff passed: {result.ruff_passed}")
                print("\nGenerated:")
                for path in result.generated_files:
                    print(f"  - {path}")
                if args.strict_clean and not result.strict_clean_passed:
                    import sys
                    print("Strict review bundle generation failed.", file=sys.stderr)
                    parser.exit(status=1)

        if args.command == "quality-gate":
            result = run_quality_gate_mode(args.project, args.story, mode=args.mode)

            print(f"Quality gate mode: {result.mode}")
            print(f"Quality gate status: {result.status}")
            print(f"Ready for review: {result.ready_for_review}")
            if result.result_path is not None:
                print(f"Result written to: {result.result_path}")
            if result.report_path is not None:
                print(f"Report written to: {result.report_path}")
            print(f"Next action: {result.next_action}")

            if result.status not in {"READY_FOR_REVIEW", "POST_MERGE_VERIFIED"}:
                parser.exit(status=1)

        if args.command == "test-layers":
            result = run_test_layers(args.project, args.story)

            print(f"Test layer status: {result.status}")
            print(f"Result written to: {result.result_path}")
            print(f"Report written to: {result.report_path}")
            print(f"Next action: {result.next_action}")

        if args.command == "generate-stories":
            created_paths = generate_stories(args.project, args.blueprint)

            print(f"Generated story workspaces in: {args.project.resolve() / 'stories'}")

            if created_paths:
                print("\nCreated:")
                for path in created_paths:
                    print(f"  - {path}")
            else:
                print("\nNo new files created. Story workspaces already exist.")

        if args.command == "assign-agents":
            agent_plan_path = assign_agents(args.project, args.story, args.force)

            print(f"Agent plan created at: {agent_plan_path}")

        if args.command == "generate-prompts":
            result = generate_prompt_pack(args.project, args.story, args.force)

            print(f"Prompt pack created at: {result.prompt_pack_path}")

            if result.created_files:
                print("\nCreated or updated:")
                for path in result.created_files:
                    print(f"  - {path}")
            else:
                print("\nNo prompt files created or updated.")

            if result.skipped_files:
                print("\nSkipped existing files:")
                for path in result.skipped_files:
                    print(f"  - {path}")
                print("\nUse --force to overwrite existing prompt files.")

        if args.command == "prepare-story":
            result = prepare_story(args.project, args.story, args.force)

            print(f"Story prepared: {result.story}")
            print(f"Agent plan: {result.agent_plan_path}")
            print(f"Prompt pack: {result.prompt_pack_path}")
            print(f"Runbook: {result.runbook_path}")
            print(f"Report: {result.report_path}")
            print(f"Status: {result.status_path}")

        if args.command == "next-step":
            result = run_next_step(args.project, args.story)
            print(result.terminal_summary)

        if args.command == "workflow-preview":
            result = run_workflow_preview(args.project, args.story)
            print(result.terminal_summary)

        if args.command == "workflow-run":
            result = run_workflow_run(
                args.project,
                args.story,
                phase=args.phase,
                execute=args.execute,
            )
            print(result.terminal_summary)

        if args.command == "run-story":
            result = run_story(args.project, args.story, execute=args.execute)
            print(result.terminal_summary)
            if args.execute and result.status not in {"completed"}:
                parser.exit(status=1)

        if args.command == "run-next-story":
            result = run_next_story(args.project, execute=args.execute)
            print(result.terminal_summary)
            if args.execute and result.status not in {"completed"}:
                parser.exit(status=1)

        if args.command == "finalize-story":
            result = finalize_story(args.project, args.story, args.force)

            print(f"Story finalized: {result.story}")
            print(f"Status: {result.status}")
            print(f"Ready for review: {result.ready_for_review}")
            print(f"Review bundle: {result.review_bundle_path}")
            print(f"Quality gate result: {result.quality_gate_result_path}")
            print(f"Finalize result: {result.finalize_result_path}")
            print(f"Finalize report: {result.finalize_report_path}")
            print(f"Next action: {result.next_action}")

        if args.command == "cloud-queue":
            application_service = build_default_application_service(args.project)
            batch_service = build_default_batch_service(args.project)

            if args.cloud_queue_command == "batch":
                if args.cloud_queue_batch_command == "list":
                    result = batch_service.list_batches()
                    if args.json:
                        print(json.dumps([asdict(record) for record in result], default=str, indent=2, sort_keys=True))
                    else:
                        print(format_batch_status(list(result)))

                if args.cloud_queue_batch_command == "show":
                    result = batch_service.show(args.batch)
                    if args.json:
                        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                    else:
                        print(format_batch_record(result))

                if args.cloud_queue_batch_command == "export":
                    result = batch_service.export(
                        request_ids=list(args.request) if args.request else None,
                        all_ready=args.all_ready,
                        batch_id=args.batch,
                    )
                    if args.json:
                        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                    else:
                        print(f"Batch export created: {result.export_path}")
                        print(f"Batch ID: {result.batch_record.batch_id}")
                        print(f"Request IDs: {', '.join(result.request_ids)}")
                        print(f"Manifest checksum: {result.batch_manifest_checksum}")

                if args.cloud_queue_batch_command == "import":
                    result = batch_service.import_bundle(Path(args.file), batch_id=args.batch)
                    if args.json:
                        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                    else:
                        print("Batch import complete:")
                        print(f"Imported: {result.imported_count}")
                        print(f"Valid: {result.valid_count}")
                        print(f"Invalid: {result.invalid_count}")
                        print(f"Skipped: {result.skipped_count}")

                if args.cloud_queue_batch_command == "plan-apply":
                    result = batch_service.plan_apply(args.batch, dry_run=False)
                    if args.json:
                        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                    else:
                        print(format_orchestration_plan(result.plan))

                if args.cloud_queue_batch_command == "apply":
                    result = batch_service.apply(args.batch, dry_run=args.dry_run)
                    if args.json:
                        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                    else:
                        print(f"Batch apply complete: {result.batch_id}")
                        print(f"Status: {result.status}")
                        print(f"Dry run: {result.dry_run}")
                        for item in result.item_results:
                            print(f"- {item.item_id}: {item.outcome}")

                if args.cloud_queue_batch_command == "resume":
                    result = batch_service.resume(args.batch)
                    if args.json:
                        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                    else:
                        print(f"Batch resume complete: {result.batch_id}")
                        print(f"Status: {result.status}")
                        print(f"Resume groups: {len(result.resume_groups)}")

                if args.cloud_queue_batch_command == "retry":
                    result = batch_service.retry(args.batch, reason=args.reason)
                    if args.json:
                        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                    else:
                        print(f"Batch retry created: {result.batch_id}")
                        print(f"Attempt ID: {result.attempt_id}")
                        print(f"Status: {result.status}")

                if args.cloud_queue_batch_command == "cancel":
                    result = batch_service.cancel(args.batch, reason=args.reason)
                    if args.json:
                        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                    else:
                        print(f"Batch canceled: {result.batch_id}")
                        print(f"Cancelled items: {', '.join(result.cancelled_item_ids) or 'none'}")

                if args.cloud_queue_batch_command == "rollback":
                    result = batch_service.rollback(args.batch, reason=args.reason)
                    if args.json:
                        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                    else:
                        print(f"Batch rollback: {result.batch_id}")
                        print(f"Status: {result.status}")
                        print(f"Rolled back items: {', '.join(result.rolled_back_item_ids) or 'none'}")

                if args.cloud_queue_batch_command == "status":
                    result = batch_service.status()
                    if args.json:
                        print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                    else:
                        print(format_batch_status(list(result.batches)))

            if args.cloud_queue_command == "plan-apply":
                result = application_service.plan_apply(args.request, dry_run=True)
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(result.terminal_summary)

            if args.cloud_queue_command == "apply":
                result = application_service.plan_apply(args.request, dry_run=args.dry_run)
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(result.terminal_summary)

            if args.cloud_queue_command == "resume":
                result = application_service.resume(args.request)
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(format_resume_result(result))

            if args.cloud_queue_command == "rollback":
                result = application_service.rollback(args.application)
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(format_application_record(result))

            if args.cloud_queue_command == "application-status":
                result = application_service.application_status()
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(format_application_status(result))

            if args.cloud_queue_command == "application-show":
                result = application_service.application_show(args.application)
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(format_application_record(result))

            if args.cloud_queue_command == "recover":
                result = application_service.recover()
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(format_recovery_result(result))

            if args.cloud_queue_command == "create":
                result = create_cloud_queue_request(
                    args.project,
                    story=args.story,
                    title=args.title,
                    details=args.details,
                    blocker_type=args.blocker_type,
                    requirements=args.requirement,
                    writable_paths=args.writable_path,
                    dependencies=args.dependency,
                    context_files=args.context_file,
                    notes=args.note,
                )
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(f"Cloud queue request created: {result.request.request_id}")
                    print(f"Request path: {result.request_path}")
                    print(f"Batch: {result.request.batch_id}")

            if args.cloud_queue_command == "list":
                result = list_cloud_queue_requests(
                    args.project,
                    state=None if args.state == "all" else args.state,
                )
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(format_request_list(result.requests))

            if args.cloud_queue_command == "show":
                result = show_cloud_queue_request(args.project, args.request)
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(format_request(result.request))
                    print(f"\nPath: {result.request_path}")

            if args.cloud_queue_command == "export":
                result = export_cloud_queue_request(
                    args.project,
                    request_id=args.request,
                    all_ready=args.all_ready,
                )
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(f"Cloud queue export created: {result.export_path}")
                    print(f"Request IDs: {', '.join(result.request_ids)}")
                    print(f"Packet checksum: {result.packet_checksum}")
                    print(f"Markdown export: {result.export_markdown_path}")

            if args.cloud_queue_command == "import":
                result = import_cloud_queue_response(args.project, Path(args.file))
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(format_import_result(result))

            if args.cloud_queue_command == "approve":
                result = approve_cloud_queue_request(
                    args.project,
                    args.request,
                    normalized_response_checksum_value=args.checksum,
                    operator_note=args.note,
                )
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(f"Cloud queue request approved: {result.request.request_id}")
                    print(f"Path: {result.request_path}")
                    print(f"Decision: {result.decision}")

            if args.cloud_queue_command == "reject":
                result = reject_cloud_queue_request(
                    args.project,
                    args.request,
                    operator_note=args.note,
                )
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(f"Cloud queue request rejected: {result.request.request_id}")
                    print(f"Path: {result.request_path}")
                    print(f"Decision: {result.decision}")

            if args.cloud_queue_command == "cancel":
                result = cancel_cloud_queue_request(args.project, args.request, reason=args.reason)
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(f"Cloud queue request canceled: {result.request.request_id}")
                    print(f"Path: {result.request_path}")
                    print(f"Decision: {result.decision}")

            if args.cloud_queue_command == "fail":
                result = fail_cloud_queue_request(args.project, args.request, reason=args.reason)
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(f"Cloud queue request failed: {result.request.request_id}")
                    print(f"Path: {result.request_path}")
                    print(f"Decision: {result.decision}")

            if args.cloud_queue_command == "status":
                result = cloud_queue_status(args.project)
                if args.json:
                    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
                else:
                    print(format_status(result))

        if args.command == "cloud-review-packet":
            result = create_cloud_review_packet(args.project, args.story, args.force)

            print(f"Cloud review packet created for: {result.story}")
            print(f"Packet path: {result.packet_path}")
            print("\nGenerated:")
            for path in result.generated_files:
                print(f"  - {path}")

            if result.missing_optional_files:
                print("\nMissing optional evidence:")
                for relative_path in result.missing_optional_files:
                    print(f"  - {relative_path}")

        if args.command == "record-cloud-review":
            result = record_cloud_review(args.project, args.story, args.result_file)

            print(f"Cloud review recorded for: {result.story}")
            print(f"Decision: {result.decision}")
            print(f"Ready for human merge decision: {result.ready_for_human_merge_decision}")
            print(f"Result: {result.cloud_review_result_path}")
            print(f"Report: {result.cloud_review_report_path}")
            print(f"Status: {result.status_path}")
            print(f"Next action: {result.next_action}")

        if args.command == "record-local-execution":
            result = record_local_execution(
                args.project,
                args.story,
                execution_type=args.execution_type,
                executor_name=args.executor_name,
                roles=args.roles,
                attestation_file=args.attestation_file,
                manifest_path=args.manifest_path,
                dry_run=args.dry_run,
                force=args.force,
            )

            if args.dry_run:
                return

            print(f"Local execution recorded for: {result.story}")
            print(f"Execution mode: {result.record.execution_mode}")
            print(f"Execution type: {result.record.execution_type}")
            print(f"Executor: {result.record.executor}")
            print(f"Record checksum: {result.record.record_checksum}")
            print("\nReports written:")
            for p in result.reports_written:
                print(f"  - {p}")

        if args.command == "record-local-review":
            result = record_local_review(
                args.project,
                args.story,
                reviewer=args.reviewer,
                decision=args.decision,
                notes=args.notes,
                force=args.force,
            )

            print(f"Local review recorded for: {result.story}")
            print(f"Decision: {result.decision.decision}")
            print(f"Reviewer: {result.decision.reviewer}")
            print(f"Decision checksum: {result.decision.attestation_checksum}")
            print(f"Report: {result.report_path}")

        if args.command == "remote-dev-packet":
            result = create_remote_dev_packet(args.project, args.story, args.force)

            print(f"Remote dev validation packet created for: {result.story}")
            print(f"Validation path: {result.validation_path}")
            print(f"Packet: {result.packet_path}")
            print(f"Template: {result.template_path}")
            print("\nGenerated:")
            for path in result.generated_files:
                print(f"  - {path}")

            if result.missing_optional_files:
                print("\nMissing optional evidence:")
                for relative_path in result.missing_optional_files:
                    print(f"  - {relative_path}")

        if args.command == "record-remote-dev":
            result = record_remote_dev_validation(args.project, args.story, args.result_file)

            print(f"Remote dev validation recorded for: {result.story}")
            print(f"Validation status: {result.validation_status}")
            print(f"Ready for review: {result.ready_for_review}")
            print(f"Environment: {result.environment_name}")
            print(f"Result: {result.result_path}")
            print(f"Report: {result.report_path}")
            print(f"Status: {result.status_path}")
            print(f"Next action: {result.next_action}")

        if args.command == "improvement-scan":
            if args.improvement_scan_command == "create":
                result = create_improvement_scan_packet(args.project, args.story, args.force)

                print(f"Improvement scan packet created for: {result.story}")
                print(f"Improvements path: {result.improvements_path}")
                print("\nGenerated:")
                for path in result.generated_files:
                    print(f"  - {path}")

                if result.missing_optional_files:
                    print("\nMissing optional evidence:")
                    for relative_path in result.missing_optional_files:
                        print(f"  - {relative_path}")

            if args.improvement_scan_command == "record":
                result = record_improvement_suggestions(
                    args.project,
                    args.story,
                    args.suggestions_file,
                )

                print(f"Improvement suggestions recorded for: {result.story}")
                print(f"Suggestions file: {result.suggestions_file}")
                print(f"Report: {result.report_path}")
                print("\nCreated queue items:")
                for item in result.queue_items:
                    print(f"  - {item.item_id}: {item.item_path}")

        if args.command == "maintenance-scan":
            if args.maintenance_scan_command == "create":
                result = create_maintenance_scan_packet(
                    args.project,
                    args.story,
                    args.force,
                    args.logs_path,
                )

                print(f"Maintenance scan packet created for: {result.story}")
                print(f"Maintenance path: {result.maintenance_path}")
                print("\nGenerated:")
                for path in result.generated_files:
                    print(f"  - {path}")

                if result.included_log_files:
                    print("\nIncluded log files:")
                    for path in result.included_log_files:
                        print(f"  - {path}")

                if result.missing_optional_files:
                    print("\nMissing optional evidence:")
                    for relative_path in result.missing_optional_files:
                        print(f"  - {relative_path}")

            if args.maintenance_scan_command == "record":
                result = record_maintenance_findings(
                    args.project,
                    args.story,
                    args.findings_file,
                )

                print(f"Maintenance findings recorded for: {result.story}")
                print(f"Findings file: {result.findings_file}")
                print(f"Report: {result.report_path}")
                print("\nCreated queue items:")
                for item in result.queue_items:
                    print(f"  - {item.item_id}: {item.item_path}")

        if args.command == "feature-scan":
            if args.feature_scan_command == "create":
                result = create_feature_scan_packet(
                    args.project,
                    force=args.force,
                    focus=args.focus,
                )

                print(f"Feature scan packet created for: {result.project_path}")
                print(f"Feature scan path: {result.feature_scan_path}")
                print("\nGenerated:")
                for path in result.generated_files:
                    print(f"  - {path}")

                if result.missing_optional_files:
                    print("\nMissing optional context:")
                    for relative_path in result.missing_optional_files:
                        print(f"  - {relative_path}")

            if args.feature_scan_command == "record":
                result = record_feature_suggestions(
                    args.project,
                    args.suggestions_file,
                )

                print(f"Feature suggestions recorded for: {result.project_path}")
                print(f"Suggestions file: {result.suggestions_file}")
                print(f"Report: {result.report_path}")
                print("\nCreated queue items:")
                for item in result.queue_items:
                    print(f"  - {item.item_id}: {item.item_path}")

        if args.command == "merge-readiness":
            result = run_merge_readiness(args.project, args.story)

            print(f"Merge readiness checked for: {result.story}")
            print(f"Status: {result.status}")
            print(
                "Ready for human merge decision: "
                f"{result.ready_for_human_merge_decision}"
            )
            print(f"Cloud review decision: {result.cloud_review_decision}")
            print(f"Result: {result.result_path}")
            print(f"Report: {result.report_path}")
            print(f"Status file: {result.status_path}")
            print(f"Next action: {result.next_action}")

        if args.command == "micro-readiness":
            result = run_micro_readiness(args.project, args.story, args.target_chars)
            print(result.terminal_summary)

        if args.command == "build-context":
            result = build_role_context(
                args.project,
                args.story,
                agent=args.agent,
                all_agents=args.all,
                force=args.force,
                target_chars=args.target_chars,
            )
            print(result.terminal_summary)

        if args.command == "local-execute":
            result = run_local_execution(
                args.project,
                args.story,
                role=args.role,
                resume=args.resume,
                dry_run=args.dry_run,
            )
            print(result.terminal_summary)

        if args.command == "demo-subtasks":
            result = run_demo_subtasks(
                args.project,
                mode=args.mode,
                scenario=args.scenario,
                keep_workspace=args.keep_workspace,
                workspace_root=args.workspace_root,
            )
            print(result.terminal_summary)
            if result.exit_code != 0:
                parser.exit(status=result.exit_code)

        if args.command == "codex-task":
            if args.codex_task_command == "create":
                result = create_codex_tasks(
                    args.project,
                    args.story,
                    agent=args.agent,
                    all_agents=args.all,
                    force=args.force,
                    model=args.model,
                )
                print(result.terminal_summary)

        if args.command == "project-status":
            result = run_project_status(args.project, args.story)
            print(result.terminal_summary)
            print(f"\nReport written to: {result.report_path}")

        if args.command == "artifact-policy":
            result = check_artifact_policy(args.project)
            print(format_artifact_policy_report(result))

            if not result.passed:
                parser.exit(status=1)

        if args.command == "public-readiness":
            result = run_public_readiness(args.project)
            print(format_public_readiness_terminal_report(result))

            if not result.passed:
                parser.exit(status=1)

        if args.command == "runtime-config":
            if args.runtime_config_command == "show":
                print(show_runtime_config(args.project).rstrip())

            if args.runtime_config_command == "validate":
                result = validate_runtime_config(args.project)
                print(f"Runtime config is valid: {result.config_path}")

        if args.command == "local-model":
            if args.local_model_command == "validate":
                result = validate_local_model_runtime_config(args.project)
                print(format_local_model_validation_result(result))

                if not result.passed:
                    parser.exit(status=1)

            if args.local_model_command == "dry-run":
                result = run_local_model_dry_run(args.project, args.prompt)
                print("Local model dry run succeeded.")
                print(f"Report written to: {result.report_path}")

            if args.local_model_command == "scorecard-create":
                result = create_local_model_scorecard(args.project, args.force)
                print(f"Local model scorecard created at: {result.scorecard_path}")

                if result.created_files:
                    print("\nCreated or updated:")
                    for path in result.created_files:
                        print(f"  - {path}")

                if result.skipped_files:
                    print("\nSkipped existing files:")
                    for path in result.skipped_files:
                        print(f"  - {path}")
                    print("\nUse --force to overwrite existing scorecard files.")

            if args.local_model_command == "scorecard-run":
                result = run_local_model_scorecard(
                    args.project,
                    args.model_label,
                    args.prompt_dir,
                )
                print("Local model scorecard run succeeded.")
                print(f"Results written to: {result.result_path}")
                print(f"Run summary written to: {result.run_summary_path}")
                print(
                    "Safety: output was saved only; no files were applied, no commands were "
                    "executed, and no Git/GitHub/deploy actions were taken."
                )

            if args.local_model_command == "scorecard-report":
                result = create_local_model_scorecard_report(args.project)
                print("Local model scorecard report created.")
                print(f"Report written to: {result.report_path}")

            if args.local_model_command == "scorecard-scaffold-scores":
                result = scaffold_local_model_scorecard_scores(args.project, args.force)
                print("Local model scorecard scores scaffold created.")
                print(f"Scores written to: {result.scores_path}")
                print(f"Scoring entries created: {len(result.entries)}")

            if args.local_model_command == "scorecard-recommend":
                result = recommend_local_model_roles(args.project)
                print("Local model role recommendation reports created.")
                print(f"Markdown report written to: {result.markdown_report_path}")
                print(f"YAML report written to: {result.yaml_report_path}")
                print(f"Complete scored entries used: {len(result.complete_entries)}")
                print(f"Incomplete scored entries ignored: {len(result.incomplete_entries)}")
                if not result.recommendations:
                    print("No complete scores found. No role winner was claimed.")

        if args.command == "local-agent":
            if args.local_agent_command == "run-prompt":
                result = run_local_agent_prompt(
                    args.project,
                    args.prompt_file,
                    args.output_file,
                )
                print("Local agent prompt run succeeded.")
                print(f"Output written to: {result.report_path}")
                print(f"Raw response written to: {result.raw_response_path}")
                print(
                    "Safety: output was saved only; no files were applied, no commands were "
                    "executed, and no Git/GitHub/deploy actions were taken."
                )

            if args.local_agent_command == "draft":
                result = run_local_agent_draft(
                    project_path=args.project,
                    story=args.story,
                    agent=args.agent,
                    prompt_file=args.prompt_file,
                    output_file=args.output_file,
                    model_label=args.model_label,
                    prompt_mode=args.prompt_mode,
                    force=args.force,
                )
                print("Local agent draft saved.")
                print(f"Status: {result.status}")
                print(f"Prompt mode: {result.prompt_mode}")
                print(f"Draft output: {result.output_file}")
                print(f"Metadata: {result.metadata_file}")
                print(f"Raw response: {result.raw_response_file}")
                if result.context_file is not None:
                    print(f"Context packet: {result.context_file}")
                for warning in result.warnings:
                    print(f"Warning: {warning}")
                print(
                    "Safety: draft output was saved only; no source files were edited, no model "
                    "output was executed, and no cloud, GitHub, commit, merge, or deploy actions "
                    "were taken."
                )

        if args.command == "support-ticket":
            if args.support_ticket_command == "create":
                result = create_support_ticket(
                    project_path=args.project,
                    story=args.story,
                    agent=args.agent,
                    blocker_type=args.blocker_type,
                    question=args.question,
                    details=args.details,
                    severity=args.severity,
                )
                print(f"Support ticket created: {result.ticket_id}")
                print(f"Ticket path: {result.ticket_path}")
                if result.story_status_path is not None:
                    print(f"Story status updated: {result.story_status_path}")

            if args.support_ticket_command == "list":
                result = list_support_tickets(args.project)
                print(format_support_ticket_list(result))

            if args.support_ticket_command == "cloud-packet":
                result = create_support_ticket_cloud_packet(args.project, args.ticket)
                print(f"Cloud packet created for: {result.ticket_id}")
                print(f"Ticket path: {result.ticket_path}")
                print(f"Packet path: {result.packet_path}")

            if args.support_ticket_command == "answer":
                result = answer_support_ticket(
                    project_path=args.project,
                    ticket_id=args.ticket,
                    answer_file=args.answer_file,
                    answered_by=args.answered_by,
                )
                print(f"Support ticket answered: {result.ticket_id}")
                print(f"Source path: {result.source_path}")
                print(f"Answered path: {result.destination_path}")
                print(f"Answered by: {result.answered_by}")

            if args.support_ticket_command == "close":
                result = close_support_ticket(args.project, args.ticket)
                print(f"Support ticket closed: {result.ticket_id}")
                print(f"Source path: {result.source_path}")
                print(f"Closed path: {result.destination_path}")

        if args.command == "queue":
            if args.queue_command == "create":
                result = create_queue_item(
                    project_path=args.project,
                    queue_type=args.queue_type,
                    title=args.title,
                    source_story=args.source_story,
                    category=args.category,
                    priority=args.priority,
                    details=args.details,
                )
                print(f"Queue item created: {result.item_id}")
                print(f"Item path: {result.item_path}")

            if args.queue_command == "list":
                result = list_queue_items(
                    project_path=args.project,
                    queue_type=args.queue_type,
                    status=args.status,
                )
                print(format_queue_list(result))

            if args.queue_command == "show":
                result = show_queue_item(
                    project_path=args.project,
                    item_id=args.item,
                    queue_type=args.queue_type,
                )
                print(format_queue_item(result))

            if args.queue_command == "set-status":
                result = set_queue_item_status(
                    project_path=args.project,
                    item_id=args.item,
                    status=args.status,
                    decision_note=args.decision_note,
                    queue_type=args.queue_type,
                )
                print(f"Queue item updated: {result.item_id}")
                print(f"Status: {result.old_status} -> {result.new_status}")
                print(f"Source path: {result.source_path}")
                print(f"Destination path: {result.destination_path}")

            if args.queue_command == "promote-to-story":
                result = promote_queue_item_to_story(
                    project_path=args.project,
                    item_id=args.item,
                    queue_type=args.queue_type,
                    allow_pending=args.allow_pending,
                    close_after_promotion=args.close_after_promotion,
                    park_after_promotion=args.park_after_promotion,
                )
                print(format_queue_promotion(result))
    except (FileNotFoundError, ValueError) as error:
        parser.exit(status=1, message=f"Error: {error}\n")
