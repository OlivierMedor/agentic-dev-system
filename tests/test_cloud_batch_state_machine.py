from __future__ import annotations

import pytest

from agentic_dev.cloud_batch.models import BATCH_STATUSES, BATCH_TERMINAL_STATUSES
from agentic_dev.cloud_batch.state_machine import (
    TRANSITION_MAP,
    allowed_batch_transitions,
    is_terminal_batch_state,
    validate_batch_status,
    validate_batch_transition,
)


def test_allowed_transitions_match_transition_map() -> None:
    for state, transitions in TRANSITION_MAP.items():
        assert allowed_batch_transitions(state) == transitions


@pytest.mark.parametrize("state", BATCH_STATUSES)
def test_validate_batch_status_accepts_known_states(state: str) -> None:
    validate_batch_status(state)


@pytest.mark.parametrize("state", BATCH_TERMINAL_STATUSES)
def test_terminal_states_are_terminal(state: str) -> None:
    assert is_terminal_batch_state(state) is True


def test_repeated_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="Repeated batch state transition"):
        validate_batch_transition("ready", "ready")


def test_invalid_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid batch transition"):
        validate_batch_transition("draft", "applied")

