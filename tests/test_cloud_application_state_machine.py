from __future__ import annotations

import pytest

from agentic_dev.cloud_application.state_machine import (
    APPLICATION_STATES,
    TERMINAL_APPLICATION_STATES,
    allowed_application_transitions,
    is_terminal_application_state,
    validate_application_state,
    validate_application_transition,
)


def test_allowed_transitions_cover_planned_apply_resume_and_rollback() -> None:
    assert "ready_to_apply" in allowed_application_transitions("application_planned")
    assert "applying" in allowed_application_transitions("ready_to_apply")
    assert "applied" in allowed_application_transitions("applying")
    assert "resume_pending" in allowed_application_transitions("applied")
    assert "rolling_back" in allowed_application_transitions("rollback_available")


@pytest.mark.parametrize(
    "state",
    APPLICATION_STATES,
)
def test_validate_application_state_accepts_known_states(state: str) -> None:
    validate_application_state(state)


@pytest.mark.parametrize(
    "state",
    TERMINAL_APPLICATION_STATES,
)
def test_terminal_states_are_reported(state: str) -> None:
    assert is_terminal_application_state(state) is True


def test_rejected_transition_is_deterministic() -> None:
    with pytest.raises(ValueError, match="Invalid application transition"):
        validate_application_transition("application_planned", "applied")


def test_repeated_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="Repeated application state transition"):
        validate_application_transition("applied", "applied")

