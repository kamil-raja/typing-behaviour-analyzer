"""Structural checks for the golden example fixture files.

These tests do not replay events or calculate metrics; replay tests live in
``test_replay.py``. They only ensure the JSON fixtures are well-formed and
that fixture G carries the values approved for AMB-005.
"""

import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE_IDS = tuple("ABCDEFG")


def load_fixture(fixture_id: str) -> dict:
    """Load one golden fixture by its letter identifier."""
    path = FIXTURE_DIR / f"golden_{fixture_id.lower()}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_golden_fixture_is_well_formed(fixture_id: str) -> None:
    """Check the shared fixture structure without replaying events."""
    fixture = load_fixture(fixture_id)
    assert fixture["id"] == fixture_id
    assert fixture["mode"] in {"time", "passage"}

    if fixture_id == "G":
        assert fixture["text"] == (
            "the quick brown fox jumps over the lazy dog "
            "while another quiet fox watches from the green hill"
        )
        assert fixture["duration_limit_ms"] == 2000
    else:
        assert fixture["text"] == "cat"
        if fixture["mode"] == "passage":
            assert fixture["duration_limit_ms"] is None
        else:
            assert fixture["duration_limit_ms"] == 6000

    events = fixture["events"]
    assert events
    assert [event["seq"] for event in events] == list(range(len(events)))
    assert all(
        events[index]["t"] <= events[index + 1]["t"]
        for index in range(len(events) - 1)
    )

    for event in events:
        assert event["type"] in {"down", "up"}
        if event["type"] == "up":
            assert event["key"] is None
        else:
            assert isinstance(event["key"], str)
        if event["repeat"]:
            assert event["type"] == "down"
            assert event["key"] == "Backspace"

    assert "expected" in fixture or "expected_error" in fixture


def test_fixture_g_uses_approved_amb_005_values() -> None:
    """Fixture G carries the approved text, limit, end state and Backspace case."""
    fixture = load_fixture("G")
    expected = fixture["expected"]

    assert fixture["duration_limit_ms"] == 2000
    assert expected["end_reason"] == "timer_expiry"
    assert expected["active_duration_ms"] == 2000
    assert expected["typed_text"] == ""
    assert expected["backspace_deletions"] == 3
    assert expected["backspace_presses"] == 1
    assert expected["backspace_dwell_ms"] == 600.0
    assert expected["timed_actions"] == ["c", "a", "t", "Backspace"]
    assert expected["intervals_ms"] == [100, 100, 800]
    assert sum(1 for event in fixture["events"] if event["type"] == "up") == 1
    assert sum(1 for event in fixture["events"] if event["repeat"]) == 2
    assert "unresolved" not in fixture
