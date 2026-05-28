from __future__ import annotations

import argparse
from pathlib import Path

from agentic_dev.agent_assignment import assign_agents
from agentic_dev.finalize_story import finalize_story
from agentic_dev.prepare_story import prepare_story
from agentic_dev.prompt_pack import generate_prompt_pack
from agentic_dev.quality_gate import run_quality_gate
from agentic_dev.review_bundle import create_review_bundle
from agentic_dev.scaffolding import init_project
from agentic_dev.story_generator import generate_stories


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
    except (FileNotFoundError, ValueError) as error:
        parser.exit(status=1, message=f"Error: {error}\n")
