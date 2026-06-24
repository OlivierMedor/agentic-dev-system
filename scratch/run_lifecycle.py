#!/usr/bin/env python
"""Run the full Story 067 lifecycle inside Docker and validate all evidence.

Steps:
1. review-bundle with host identity (strict-clean, allow-generated-artifacts)
2. record-local-execution
3. record-local-review ready_for_review
4. finalize-story
5. cloud-review-packet
"""
import subprocess
import sys

STORY = "evidence-derived-local-execution-recording"
HOST_ID_FILE = "/app/scratch/host_identity.yaml"

DOCKER_BASE = [
    "docker", "compose", "run", "--rm",
    "-e", f"AGENTIC_HOST_GIT_IDENTITY_FILE={HOST_ID_FILE}",
    "dev",
]


def run(cmd, check=True):
    full = DOCKER_BASE + cmd
    print(f"\n>>> {' '.join(full)}\n")
    result = subprocess.run(full, capture_output=False)
    if check and result.returncode != 0:
        print(f"\nFAILED with exit code {result.returncode}")
        sys.exit(result.returncode)
    return result.returncode


def main():
    # Step 1: strict review bundle with host parity
    rc = run([
        "agentic", "review-bundle",
        "--story", STORY,
        "--strict-clean",
        "--allow-generated-artifacts",
        "--host-identity-file", HOST_ID_FILE,
    ])
    print(f"review-bundle exit code: {rc}")

    # Step 2: record-local-execution
    run([
        "agentic", "record-local-execution",
        "--story", STORY,
        "--execution-type", "manual",
        "--executor", "local-operator",
    ])

    # Step 3: record-local-review
    run([
        "agentic", "record-local-review",
        "--story", STORY,
        "--decision", "ready_for_review",
        "--reviewer", "local-operator",
    ])

    # Step 4: finalize-story
    run([
        "agentic", "finalize-story",
        "--story", STORY,
    ])

    # Step 5: cloud-review-packet
    run([
        "agentic", "cloud-review-packet",
        "--story", STORY,
        "--force",
    ])

    print("\n\n=== All lifecycle steps completed ===")


if __name__ == "__main__":
    main()
