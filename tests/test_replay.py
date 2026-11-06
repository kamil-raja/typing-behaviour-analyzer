"""Replay-engine tests against the golden fixtures and the §4 edge rules.

The fixtures are the hand-computed examples in ``docs/METRICS.md`` §13. Every
replayable fixture is checked against its expected counts and the three global
invariants. Focused tests cover the pending-key rules that the fixtures do not
exercise directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.engine import analyze_session
from app.engine.replay import (
    InvalidEventSequence,
    ReplayResult,
    TimedAction,
    replay_events,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REPLAYABLE_FIXTURES = tuple("ABCDFG")
ALL_FIXTURES = tuple("ABCDEFG")

# AMB-005 was approved using the descriptive label "timer_expiry". The engine
# and stored schema use the canonical blueprint value "time_up".
END_REASON_ALIASES = {"timer_expiry": "time_up"}


def load_fixture(fixture_id: str) -> dict[str, Any]:
    """Load one golden fixture by its letter identifier."""
    path = FIXTURE_DIR / f"golden_{fixture_id.lower()}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def replay_fixture(fixture_id: str) -> ReplayResult:
    """Replay one golden fixture through the engine."""
    fixture = load_fixture(fixture_id)
    return replay_events(
        text=fixture["text"],
        mode=fixture["mode"],
        duration_limit_ms=fixture["duration_limit_ms"],
        events=fixture["events"],
    )


def canonical_end_reason(value: str) -> str:
    """Map a fixture-level end-reason label to the engine's canonical value."""
    return END_REASON_ALIASES.get(value, value)


def interval_list(actions: list[TimedAction]) -> list[float]:
    """Return consecutive timed-action intervals."""
    return [
        actions[index].t - actions[index - 1].t
        for index in range(1, len(actions))
    ]


def action_labels(actions: list[TimedAction]) -> list[str]:
    """Render timed actions using the fixture's printable/Backspace labels."""
    return [
        "Backspace" if action.kind == "backspace" else str(action.typed)
        for action in actions
    ]


def assert_invariants(result: ReplayResult) -> None:
    """Assert the invariants required for every fixture."""
    assert result.E == result.U + result.Ec + result.Eu
    assert result.K == result.C + result.E
    assert result.N <= result.K


def event(
    seq: int,
    event_type: str,
    t: float,
    code: str,
    key: str | None,
    repeat: bool = False,
) -> dict[str, Any]:
    """Build an event object in the documented payload shape."""
    return {
        "seq": seq,
        "type": event_type,
        "t": t,
        "code": code,
        "key": key,
        "repeat": repeat,
    }


@pytest.mark.parametrize("fixture_id", ALL_FIXTURES)
def test_fixtures_hold_the_required_invariants(fixture_id: str) -> None:
    """Every golden fixture satisfies the global metric invariants."""
    assert_invariants(replay_fixture(fixture_id))


@pytest.mark.parametrize("fixture_id", REPLAYABLE_FIXTURES)
def test_golden_fixture_counts_and_end_state(fixture_id: str) -> None:
    """Each replayable fixture matches its expected counts and end state."""
    fixture = load_fixture(fixture_id)
    expected = fixture["expected"]
    result = replay_fixture(fixture_id)

    assert result.K == expected["K"]
    assert result.C == expected["C"]
    assert result.E == expected["E"]
    assert result.N == expected["N"]
    assert result.U == expected["U"]
    assert result.Ec == expected["corrected_errors"]
    assert result.Eu == expected["erased_unresolved_errors"]
    assert result.end_reason == canonical_end_reason(expected["end_reason"])
    assert result.active_duration_ms == expected["active_duration_ms"]

    if "dropped_after_end" in expected:
        assert result.dropped_after_end == expected["dropped_after_end"]
    if "typed_text" in expected:
        assert result.typed_final == expected["typed_text"]
    if "backspace_deletions" in expected:
        assert result.backspace_deletions == expected["backspace_deletions"]
    if "backspace_presses" in expected:
        assert result.backspace_presses == expected["backspace_presses"]

    assert_invariants(result)


def test_golden_g_backspace_hold_is_one_press_one_dwell() -> None:
    """A held Backspace deletes per repeat but keeps the original dwell."""
    expected = load_fixture("G")["expected"]
    result = replay_fixture("G")

    assert result.typed_final == ""
    assert result.backspace_deletions == 3
    assert result.backspace_presses == 1
    assert len(result.dwell_samples) == 1

    dwell = result.dwell_samples[0]
    assert dwell.code == "Backspace"
    assert dwell.is_backspace is True
    assert dwell.dwell_ms == expected["backspace_dwell_ms"]

    assert action_labels(result.timed_actions) == expected["timed_actions"]
    assert interval_list(result.timed_actions) == expected["intervals_ms"]


def test_golden_e_is_an_incomplete_passage() -> None:
    """A wrong final character leaves a passage run incomplete."""
    fixture = load_fixture("E")
    result = replay_fixture("E")

    assert fixture["expected_error"] == "INCOMPLETE_SESSION"
    assert result.end_reason is None
    assert result.is_complete is False
    assert result.typed_final == "cax"
    assert result.K == 3
    assert result.C == 2
    assert result.E == 1
    assert result.N == 3
    assert result.U == 1
    assert result.Ec == 0
    assert result.Eu == 0
    assert_invariants(result)


def test_analyze_session_exposes_replay_stage() -> None:
    """The engine entry point exposes the replay result."""
    fixture = load_fixture("A")
    analysis = analyze_session(
        text=fixture["text"],
        mode=fixture["mode"],
        duration_limit_ms=fixture["duration_limit_ms"],
        events=fixture["events"],
    )

    assert isinstance(analysis.replay, ReplayResult)
    assert analysis.replay.K == 4
    assert analysis.replay.end_reason == "completed"


def test_repeat_printable_keydown_is_discarded() -> None:
    """A repeat printable is not a keystroke and does not touch pending."""
    events = [
        event(0, "down", 0, "KeyC", "c"),
        event(1, "down", 100, "KeyC", "c", repeat=True),
        event(2, "up", 200, "KeyC", None),
    ]
    result = replay_events("cat", "passage", None, events)

    assert result.K == 1
    assert result.C == 1
    assert result.discarded_repeat_keydowns == 1
    assert len(result.dwell_samples) == 1
    assert result.dwell_samples[0].dwell_ms == 200


def test_orphan_up_is_dropped_and_counted() -> None:
    """An up with no pending original creates no dwell sample."""
    events = [
        event(0, "down", 0, "KeyC", "c"),
        event(1, "up", 100, "KeyX", None),
        event(2, "up", 300, "KeyC", None),
    ]
    result = replay_events("cat", "passage", None, events)

    assert result.orphan_up == 1
    assert len(result.dwell_samples) == 1
    assert result.dwell_samples[0].dwell_ms == 300


def test_second_non_repeat_down_counts_missing_up() -> None:
    """A repeated non-repeat down replaces the pending entry and counts the miss."""
    events = [
        event(0, "down", 0, "KeyC", "c"),
        event(1, "down", 100, "KeyC", "c"),
        event(2, "up", 200, "KeyC", None),
    ]
    result = replay_events("cat", "passage", None, events)

    assert result.K == 2
    assert result.missing_up == 1
    assert len(result.dwell_samples) == 1
    assert result.dwell_samples[0].dwell_ms == 100
    assert result.open_at_end == 0


def test_printable_at_full_wrong_buffer_is_invalid() -> None:
    """The server rejects a printable down once the buffer is full."""
    events = [
        event(0, "down", 0, "KeyC", "c"),
        event(1, "down", 100, "KeyA", "a"),
        event(2, "down", 200, "KeyX", "x"),
        event(3, "down", 300, "KeyT", "t"),
    ]

    with pytest.raises(InvalidEventSequence):
        replay_events("cat", "passage", None, events)


def test_backspace_repeat_without_pending_original_is_invalid() -> None:
    """A repeat down is valid only when its original is still pending."""
    events = [
        event(0, "down", 0, "KeyC", "c"),
        event(1, "down", 100, "Backspace", "Backspace", repeat=True),
    ]

    with pytest.raises(InvalidEventSequence):
        replay_events("cat", "passage", None, events)


def test_timer_boundary_rejects_keystroke_at_the_limit() -> None:
    """Timer expiry wins at t == duration_limit_ms."""
    events = [
        event(0, "down", 0, "KeyC", "c"),
        event(1, "down", 500, "KeyA", "a"),
        event(2, "down", 1000, "KeyT", "t"),
        event(3, "up", 1100, "KeyT", None),
    ]
    result = replay_events("cat", "time", 1000, events)

    assert result.end_reason == "time_up"
    assert result.active_duration_ms == 1000
    assert result.K == 2
    assert result.typed_final == "ca"
    assert result.dropped_after_end == 2


def test_completion_is_accepted_strictly_before_the_limit() -> None:
    """Completion at t < duration_limit_ms ends with the completion timestamp."""
    events = [
        event(0, "down", 0, "KeyC", "c"),
        event(1, "down", 500, "KeyA", "a"),
        event(2, "down", 999, "KeyT", "t"),
    ]
    result = replay_events("cat", "time", 1000, events)

    assert result.end_reason == "completed"
    assert result.active_duration_ms == 999
    assert result.dropped_after_end == 0


def test_backspace_on_empty_buffer_counts_a_press_not_a_deletion() -> None:
    """A Backspace with an empty buffer is a press but not a timed action."""
    events = [
        event(0, "down", 0, "KeyC", "c"),
        event(1, "down", 100, "Backspace", "Backspace"),
        event(2, "up", 150, "Backspace", None),
        event(3, "down", 200, "Backspace", "Backspace"),
        event(4, "up", 250, "Backspace", None),
    ]
    result = replay_events("cat", "passage", None, events)

    assert result.backspace_presses == 2
    assert result.backspace_deletions == 1
    assert action_labels(result.timed_actions) == ["c", "Backspace"]
    assert interval_list(result.timed_actions) == [100]
