from __future__ import annotations

import argparse
from pathlib import Path

from agentic_dev.agent_assignment import assign_agents
from agentic_dev.artifact_policy import check_artifact_policy, format_artifact_policy_report
from agentic_dev.cloud_review_packet import create_cloud_review_packet
from agentic_dev.cloud_review_result import record_cloud_review
from agentic_dev.finalize_story import finalize_story
from agentic_dev.improvement_scan import (
    create_improvement_scan_packet,
    record_improvement_suggestions,
)
from agentic_dev.merge_readiness import run_merge_readiness
from agentic_dev.prepare_story import prepare_story
from agentic_dev.project_status import run_project_status
from agentic_dev.prompt_pack import generate_prompt_pack
from agentic_dev.quality_gate import run_quality_gate
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
from agentic_dev.runtime_config import show_runtime_config, validate_runtime_config
from agentic_dev.scaffolding import init_project
from agentic_dev.story_generator import generate_stories
from agentic_dev.support_queue import (
    answer_support_ticket,
    close_support_ticket,
    create_support_ticket,
    create_support_ticket_cloud_packet,
    format_support_ticket_list,
    list_support_tickets,
)
from agentic_dev.test_layers import run_test_layers


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
            result = create_review_bundle(args.project, args.story)

            print(f"Review bundle created at: {result.review_bundle_path}")
            print(f"pytest passed: {result.pytest_passed}")
            print(f"ruff passed: {result.ruff_passed}")
            print("\nGenerated:")
            for path in result.generated_files:
                print(f"  - {path}")

        if args.command == "quality-gate":
            result = run_quality_gate(args.project, args.story)

            print(f"Quality gate status: {result.status}")
            print(f"Ready for review: {result.ready_for_review}")
            print(f"Result written to: {result.result_path}")
            print(f"Report written to: {result.report_path}")
            print(f"Next action: {result.next_action}")

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

        if args.command == "project-status":
            result = run_project_status(args.project, args.story)
            print(result.terminal_summary)
            print(f"\nReport written to: {result.report_path}")

        if args.command == "artifact-policy":
            result = check_artifact_policy(args.project)
            print(format_artifact_policy_report(result))

            if not result.passed:
                parser.exit(status=1)

        if args.command == "runtime-config":
            if args.runtime_config_command == "show":
                print(show_runtime_config(args.project).rstrip())

            if args.runtime_config_command == "validate":
                result = validate_runtime_config(args.project)
                print(f"Runtime config is valid: {result.config_path}")

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
