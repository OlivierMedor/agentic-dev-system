from __future__ import annotations

import pytest

from agentic_dev.cloud_queue.models import QUEUE_STATES, TERMINAL_QUEUE_STATES
from agentic_dev.cloud_queue.state_machine import (
    TRANSITION_MAP,
    allowed_transitions,
    is_terminal_state,
    normalize_transition_path,
    validate_state,
    validate_transition,
)


@pytest.mark.parametrize(
    ("state", "expected"),
    [(state, transitions) for state, transitions in TRANSITION_MAP.items()],
)
def test_allowed_transitions_match_explicit_transition_map(state: str, expected: tuple[str, ...]) -> None:
    assert allowed_transitions(state) == expected


@pytest.mark.parametrize(
    ("current_state", "next_state"),
    [
        (current_state, next_state)
        for current_state, transitions in TRANSITION_MAP.items()
        for next_state in transitions
    ],
)
def test_every_allowed_transition_passes(current_state: str, next_state: str) -> None:
    validate_transition(current_state, next_state)


@pytest.mark.parametrize(
    ("current_state", "next_state"),
        [
            ("new", "approved"),
            ("ready", "approved"),
            ("exported", "approved"),
            ("imported", "approved"),
            ("classified_safe", "failed"),
            ("approval_required", "ready"),
            ("validated_safe", "approved"),
            ("validated_failed", "validated_safe"),
        ],
)
def test_prohibited_transitions_raise_clear_errors(current_state: str, next_state: str) -> None:
    with pytest.raises(ValueError, match="Invalid cloud queue transition"):
        validate_transition(current_state, next_state)


@pytest.mark.parametrize("state", TERMINAL_QUEUE_STATES)
def test_terminal_states_are_reported_correctly(state: str) -> None:
    assert is_terminal_state(state) is True


@pytest.mark.parametrize("state", [state for state in QUEUE_STATES if state not in TERMINAL_QUEUE_STATES])
def test_non_terminal_states_are_reported_correctly(state: str) -> None:
    assert is_terminal_state(state) is False


def test_repeated_transitions_are_rejected() -> None:
    with pytest.raises(ValueError, match="Repeated state transition is not allowed"):
        validate_transition("ready", "ready")


def test_approval_only_from_approval_required() -> None:
    validate_transition("approval_required", "approved")
    with pytest.raises(ValueError, match="Invalid cloud queue transition"):
        validate_transition("validated_safe", "approved")


def test_rejection_behavior_from_valid_states() -> None:
    validate_transition("classified_safe", "rejected")
    validate_transition("approval_required", "rejected")
    with pytest.raises(ValueError, match="Invalid cloud queue transition"):
        validate_transition("new", "rejected")


def test_normalize_transition_path_rejects_unsupported_sequence() -> None:
    assert normalize_transition_path(["new", "ready", "exported"]) == ("new", "ready", "exported")
    with pytest.raises(ValueError):
        normalize_transition_path(["new", "approved"])


def test_validate_state_rejects_unknown_state() -> None:
    with pytest.raises(ValueError, match="Invalid cloud queue state"):
        validate_state("unknown")
