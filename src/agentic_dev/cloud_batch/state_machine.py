from __future__ import annotations

from agentic_dev.cloud_batch.models import BATCH_STATUSES, BATCH_TERMINAL_STATUSES


TRANSITION_MAP: dict[str, tuple[str, ...]] = {
    "draft": ("ready", "cancelled", "superseded"),
    "ready": ("exported", "cancelled", "superseded"),
    "exported": ("awaiting_responses", "cancelled", "superseded"),
    "awaiting_responses": ("responses_imported", "validation_partial", "cancelled", "superseded"),
    "responses_imported": ("validation_partial", "validation_complete", "cancelled", "superseded"),
    "validation_partial": ("validation_complete", "planning", "cancelled", "superseded"),
    "validation_complete": ("planning", "cancelled", "superseded"),
    "planning": ("planned", "failed", "cancelled", "superseded"),
    "planned": ("applying", "resume_pending", "rollback_pending", "cancelled", "superseded"),
    "applying": ("partially_applied", "applied", "failed", "rollback_pending", "cancelled"),
    "partially_applied": ("applying", "applied", "failed", "rollback_pending", "cancelled"),
    "applied": ("resume_pending", "rollback_pending", "superseded"),
    "resume_pending": ("resuming", "cancelled", "superseded"),
    "resuming": ("partially_resumed", "resumed", "partially_failed", "failed", "cancelled"),
    "partially_resumed": ("resuming", "resumed", "partially_failed", "failed", "cancelled"),
    "resumed": ("rollback_pending", "superseded"),
    "partially_failed": ("planning", "retry_pending", "rollback_pending", "cancelled"),
    "failed": ("retry_pending", "rollback_pending", "cancelled", "superseded"),
    "rollback_pending": ("rolling_back", "cancelled"),
    "rolling_back": ("partially_rolled_back", "rolled_back", "failed"),
    "partially_rolled_back": ("rolling_back", "rolled_back", "failed", "cancelled"),
    "rolled_back": (),
    "cancelled": (),
    "superseded": (),
}


def allowed_batch_transitions(state: str) -> tuple[str, ...]:
    if state not in TRANSITION_MAP:
        raise ValueError(f"Unknown batch state: {state}")
    return TRANSITION_MAP[state]


def validate_batch_status(status: str) -> None:
    if status not in BATCH_STATUSES:
        raise ValueError(
            f"Invalid batch state: {status}. Expected one of: {', '.join(BATCH_STATUSES)}.",
        )


def validate_batch_transition(current_state: str, next_state: str) -> None:
    validate_batch_status(current_state)
    validate_batch_status(next_state)
    if current_state == next_state:
        raise ValueError(f"Repeated batch state transition is not allowed: {current_state} -> {next_state}")
    allowed = allowed_batch_transitions(current_state)
    if next_state not in allowed:
        raise ValueError(
            f"Invalid batch transition: {current_state} -> {next_state}. "
            f"Allowed transitions: {', '.join(allowed) or 'none'}.",
        )


def is_terminal_batch_state(state: str) -> bool:
    validate_batch_status(state)
    return state in BATCH_TERMINAL_STATUSES

