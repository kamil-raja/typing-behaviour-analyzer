"""Structural checks for the golden example fixture files.

These tests do not replay events or calculate metrics; that begins in
P0-D1-03. They only ensure the JSON fixtures are well-formed and that
fixture G does not contain invented values for fields the blueprint leaves
unspecified.
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
        assert fixture["text"] is None
        assert "duration_limit_ms" not in fixture
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


def test_fixture_g_keeps_unspecified_values_unresolved() -> None:
    """Fixture G must not guess its text, duration limit, or derived end."""
    fixture = load_fixture("G")
    expected = fixture["expected"]
    unresolved = set(fixture["unresolved"])

    assert {"text", "duration_limit_ms", "end_reason", "active_duration_ms"} <= unresolved
    assert fixture["text"] is None
    assert "duration_limit_ms" not in fixture
    assert "end_reason" not in expected
    assert "active_duration_ms" not in expected
    assert sum(1 for event in fixture["events"] if event["type"] == "up") == 1
    assert sum(1 for event in fixture["events"] if event["repeat"]) == 2
