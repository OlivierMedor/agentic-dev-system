from __future__ import annotations

from collections.abc import Iterable

from agentic_dev.cloud_queue.models import QUEUE_STATES, TERMINAL_QUEUE_STATES


TRANSITION_MAP: dict[str, tuple[str, ...]] = {
    "new": ("ready", "canceled", "failed"),
    "ready": ("exported", "rejected", "canceled", "failed"),
    "exported": ("imported", "failed"),
    "imported": ("classified_safe", "approval_required", "validated_safe", "validated_failed", "failed"),
    "classified_safe": ("validated_safe", "approval_required", "rejected", "imported"),
    "approval_required": ("approved", "rejected", "validated_failed", "imported"),
    "validated_safe": ("canceled", "imported"),
    "validated_failed": ("rejected", "canceled", "imported"),
    "approved": (),
    "rejected": (),
    "canceled": (),
    "failed": (),
}


def allowed_transitions(state: str) -> tuple[str, ...]:
    if state not in TRANSITION_MAP:
        raise ValueError(f"Unknown cloud queue state: {state}")
    return TRANSITION_MAP[state]


def validate_state(state: str) -> None:
    if state not in QUEUE_STATES:
        raise ValueError(
            f"Invalid cloud queue state: {state}. Expected one of: {', '.join(QUEUE_STATES)}.",
        )


def validate_transition(current_state: str, next_state: str) -> None:
    validate_state(current_state)
    validate_state(next_state)
    if current_state == next_state:
        raise ValueError(f"Repeated state transition is not allowed: {current_state} -> {next_state}")
    allowed = allowed_transitions(current_state)
    if next_state not in allowed:
        raise ValueError(
            f"Invalid cloud queue transition: {current_state} -> {next_state}. "
            f"Allowed transitions: {', '.join(allowed) or 'none'}.",
        )


def is_terminal_state(state: str) -> bool:
    validate_state(state)
    return state in TERMINAL_QUEUE_STATES


def normalize_transition_path(transitions: Iterable[str]) -> tuple[str, ...]:
    result = tuple(transitions)
    for current, next_state in zip(result, result[1:], strict=False):
        validate_transition(current, next_state)
    return result
