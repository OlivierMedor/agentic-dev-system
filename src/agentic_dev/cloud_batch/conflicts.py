from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from agentic_dev.cloud_batch.models import BatchItem


@dataclass(frozen=True)
class ConflictEdge:
    left_item_id: str
    right_item_id: str
    reason: str
    severity: str = "blocked"
    details: dict[str, Any] = None  # type: ignore[assignment]

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_item_id": self.left_item_id,
            "right_item_id": self.right_item_id,
            "reason": self.reason,
            "severity": self.severity,
            "details": dict(self.details or {}),
        }


@dataclass(frozen=True)
class ConflictResult:
    conflicts: tuple[ConflictEdge, ...]
    writable_path_overlaps: tuple[ConflictEdge, ...]
    revision_conflicts: tuple[ConflictEdge, ...]
    requirements_conflicts: tuple[ConflictEdge, ...]
    architecture_conflicts: tuple[ConflictEdge, ...]
    source_revision_conflicts: tuple[ConflictEdge, ...]

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


def detect_batch_conflicts(items: list[BatchItem]) -> ConflictResult:
    conflicts: list[ConflictEdge] = []
    writable_path_overlaps: list[ConflictEdge] = []
    revision_conflicts: list[ConflictEdge] = []
    requirements_conflicts: list[ConflictEdge] = []
    architecture_conflicts: list[ConflictEdge] = []
    source_revision_conflicts: list[ConflictEdge] = []

    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            overlap = _path_overlap(left.writable_paths, right.writable_paths)
            if overlap:
                conflict = ConflictEdge(
                    left_item_id=left.item_id,
                    right_item_id=right.item_id,
                    reason=f"overlapping writable paths: {', '.join(overlap)}",
                    details={"overlap": overlap},
                )
                conflicts.append(conflict)
                writable_path_overlaps.append(conflict)
            if left.request_checksum and right.request_checksum and left.request_checksum == right.request_checksum:
                conflict = ConflictEdge(left.item_id, right.item_id, "same-task modification conflict")
                conflicts.append(conflict)
                revision_conflicts.append(conflict)
            if left.response_checksum and right.response_checksum and left.response_checksum == right.response_checksum:
                conflict = ConflictEdge(left.item_id, right.item_id, "one application invalidating another")
                conflicts.append(conflict)
                architecture_conflicts.append(conflict)
            if left.approval_checksum and right.approval_checksum and left.approval_checksum == right.approval_checksum:
                conflict = ConflictEdge(left.item_id, right.item_id, "requirement mapping conflict")
                conflicts.append(conflict)
                requirements_conflicts.append(conflict)
            if left.revision_id and right.revision_id and left.revision_id != right.revision_id and _same_revision_family(left.revision_id, right.revision_id):
                conflict = ConflictEdge(left.item_id, right.item_id, "competing source revision assumptions")
                conflicts.append(conflict)
                source_revision_conflicts.append(conflict)
    return ConflictResult(
        conflicts=tuple(conflicts),
        writable_path_overlaps=tuple(writable_path_overlaps),
        revision_conflicts=tuple(revision_conflicts),
        requirements_conflicts=tuple(requirements_conflicts),
        architecture_conflicts=tuple(architecture_conflicts),
        source_revision_conflicts=tuple(source_revision_conflicts),
    )


def _path_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    overlap: list[str] = []
    for left_path in left:
        for right_path in right:
            if _paths_conflict(left_path, right_path):
                overlap.append(str(PurePosixPath(left_path)))
                overlap.append(str(PurePosixPath(right_path)))
    return tuple(dict.fromkeys(overlap))


def _paths_conflict(left: str, right: str) -> bool:
    left_parts = PurePosixPath(left).parts
    right_parts = PurePosixPath(right).parts
    min_len = min(len(left_parts), len(right_parts))
    return left_parts[:min_len] == right_parts[:min_len] or left.startswith(right.rstrip("/*")) or right.startswith(left.rstrip("/*"))


def _same_revision_family(left_revision_id: str, right_revision_id: str) -> bool:
    left_prefix = left_revision_id.split("-", 1)[0]
    right_prefix = right_revision_id.split("-", 1)[0]
    return left_prefix == right_prefix

