from __future__ import annotations

from agentic_dev.cloud_application.models import APPLICATION_STATES, TERMINAL_APPLICATION_STATES

TRANSITION_MAP: dict[str, tuple[str, ...]] = {
    "application_planned": ("application_validation_failed", "ready_to_apply", "cancelled"),
    "application_validation_failed": ("application_planned", "cancelled"),
    "ready_to_apply": ("applying", "cancelled"),
    "applying": ("applied", "application_validation_failed", "rollback_available", "resume_failed"),
    "applied": ("resume_pending", "superseded", "rollback_available", "rolling_back"),
    "resume_pending": ("resuming", "cancelled", "rolling_back"),
    "resuming": ("resumed", "resume_failed"),
    "resumed": ("rollback_available", "superseded", "rolling_back"),
    "resume_failed": ("rollback_available", "cancelled"),
    "rollback_available": ("rolling_back", "superseded"),
    "rolling_back": ("rolled_back", "rollback_failed"),
    "rolled_back": (),
    "rollback_failed": (),
    "superseded": (),
    "cancelled": (),
}


def allowed_application_transitions(state: str) -> tuple[str, ...]:
    if state not in TRANSITION_MAP:
        raise ValueError(f"Unknown application state: {state}")
    return TRANSITION_MAP[state]


def validate_application_state(state: str) -> None:
    if state not in APPLICATION_STATES:
        raise ValueError(
            f"Invalid application state: {state}. Expected one of: {', '.join(APPLICATION_STATES)}.",
        )


def validate_application_transition(current_state: str, next_state: str) -> None:
    validate_application_state(current_state)
    validate_application_state(next_state)
    if current_state == next_state:
        raise ValueError(f"Repeated application state transition is not allowed: {current_state} -> {next_state}")
    allowed = allowed_application_transitions(current_state)
    if next_state not in allowed:
        raise ValueError(
            f"Invalid application transition: {current_state} -> {next_state}. "
            f"Allowed transitions: {', '.join(allowed) or 'none'}.",
        )


def is_terminal_application_state(state: str) -> bool:
    validate_application_state(state)
    return state in TERMINAL_APPLICATION_STATES

