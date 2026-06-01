from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactPolicyViolation:
    path: str
    reason: str


@dataclass(frozen=True)
class ArtifactPolicyResult:
    project_path: Path
    tracked_files: list[str]
    violations: list[ArtifactPolicyViolation]

    @property
    def passed(self) -> bool:
        return not self.violations


def normalize_git_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def find_artifact_policy_violations(tracked_files: list[str]) -> list[ArtifactPolicyViolation]:
    violations: list[ArtifactPolicyViolation] = []

    for tracked_file in tracked_files:
        normalized_path = normalize_git_path(tracked_file)
        parts = normalized_path.split("/") if normalized_path else []
        filename = parts[-1] if parts else normalized_path
        lowercase_filename = filename.lower()

        if is_generated_review_bundle_path(parts, filename):
            violations.append(
                ArtifactPolicyViolation(
                    path=normalized_path,
                    reason="generated review bundle file is tracked",
                ),
            )
            continue

        if is_generated_cloud_review_packet_path(parts, filename):
            violations.append(
                ArtifactPolicyViolation(
                    path=normalized_path,
                    reason="generated cloud review packet file is tracked",
                ),
            )
            continue

        if is_support_queue_runtime_path(parts, filename):
            violations.append(
                ArtifactPolicyViolation(
                    path=normalized_path,
                    reason="support queue runtime file is tracked",
                ),
            )
            continue

        if is_feature_scan_runtime_path(parts, filename):
            violations.append(
                ArtifactPolicyViolation(
                    path=normalized_path,
                    reason="feature scan runtime file is tracked",
                ),
            )
            continue

        if parts and parts[0] == "review_to_chatgpt":
            violations.append(
                ArtifactPolicyViolation(
                    path=normalized_path,
                    reason="review_to_chatgpt artifact is tracked",
                ),
            )
            continue

        if lowercase_filename.endswith(".zip"):
            violations.append(
                ArtifactPolicyViolation(
                    path=normalized_path,
                    reason="zip artifact is tracked",
                ),
            )
            continue

        if is_env_file(filename):
            violations.append(
                ArtifactPolicyViolation(
                    path=normalized_path,
                    reason="environment file is tracked",
                ),
            )

    return violations


def is_generated_review_bundle_path(parts: list[str], filename: str) -> bool:
    return is_generated_story_artifact_path(parts, "review_bundle", filename)


def is_generated_cloud_review_packet_path(parts: list[str], filename: str) -> bool:
    return is_generated_story_artifact_path(parts, "cloud_review_packet", filename)


def is_generated_story_artifact_path(parts: list[str], folder_name: str, filename: str) -> bool:
    if filename == ".gitkeep":
        return False

    return len(parts) >= 4 and parts[0] == "stories" and folder_name in parts[2:]


def is_support_queue_runtime_path(parts: list[str], filename: str) -> bool:
    if filename == ".gitkeep":
        return False

    if len(parts) < 4 or parts[0] != ".agentic" or parts[1] != "support_queue":
        return False

    return Path(filename).suffix.lower() in {".yaml", ".md"}


def is_feature_scan_runtime_path(parts: list[str], filename: str) -> bool:
    if filename == ".gitkeep":
        return False

    if len(parts) < 3 or parts[0] != ".agentic" or parts[1] != "feature_scan":
        return False

    return Path(filename).suffix.lower() in {".yaml", ".md"}


def is_env_file(filename: str) -> bool:
    if filename == ".env.example":
        return False

    return filename == ".env" or filename.startswith(".env.")


def run_git_ls_files(project_path: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=project_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "git ls-files failed"
        raise ValueError(message)

    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def check_artifact_policy(project_path: Path) -> ArtifactPolicyResult:
    resolved_project_path = project_path.resolve()
    tracked_files = run_git_ls_files(resolved_project_path)

    return ArtifactPolicyResult(
        project_path=resolved_project_path,
        tracked_files=tracked_files,
        violations=find_artifact_policy_violations(tracked_files),
    )


def format_artifact_policy_report(result: ArtifactPolicyResult) -> str:
    if result.passed:
        return (
            "Artifact policy passed: no forbidden generated artifacts or environment files "
            f"are tracked in {result.project_path}."
        )

    lines = [
        "Artifact policy failed: forbidden tracked files were found.",
        "",
        "Tracked files must not include generated review artifacts, support queue runtime files, "
        "feature scan runtime files, zip files, or environment files.",
        "",
        "Violations:",
    ]

    for violation in result.violations:
        lines.append(f"  - {violation.path}: {violation.reason}")

    return "\n".join(lines)
