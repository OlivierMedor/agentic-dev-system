from __future__ import annotations

import argparse
from pathlib import Path

from agentic_dev.scaffolding import init_project


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

    args = parser.parse_args()

    if args.command == "init":
        created_paths = init_project(args.project)

        print(f"Initialized agentic project at: {args.project.resolve()}")

        if created_paths:
            print("\nCreated:")
            for path in created_paths:
                print(f"  - {path}")
        else:
            print("\nNo new files created. Project already appears initialized.")