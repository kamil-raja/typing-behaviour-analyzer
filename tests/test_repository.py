"""Persistence tests for the session repository (P0-D2-02)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping
from typing import Any

import pytest

import app.repository as repository_module
from app.db import apply_schema, connect
from app.engine import SessionAnalysis, analyze_session
from app.engine.keys import CHAR_TO_CODE
from app.repository import SessionRepository
from app.validators import ValidatedSessionPayload

TEXT = "alpha bravo"


@pytest.fixture()
def repository_database(tmp_path) -> Iterator[str]:
    """A temporary file database with the full schema applied."""
    database = str(tmp_path / "typing.db")
    connection = connect(database)
    apply_schema(connection)
    connection.close()
    yield database


@pytest.fixture()
def repository(repository_database: str) -> Iterator[SessionRepository]:
    yield SessionRepository(repository_database)


def _events(text: str, *, final_up: bool = True) -> list[dict[str, Any]]:
    """One down/up pair per character of ``text``.

    Typing the text exactly completes the session at the final keystroke, so
    with ``final_up=True`` replay drops that last keyup after end.
    """
    events: list[dict[str, Any]] = []
    seq = 0
    t = 0.0
    for index, character in enumerate(text):
        code = CHAR_TO_CODE[character]
        events.append(
            {
                "seq": seq,
                "type": "down",
                "t": t,
                "code": code,
                "key": character,
                "repeat": False,
            }
        )
        seq += 1
        t += 60.0
        if final_up or index < len(text) - 1:
            events.append(
                {
                    "seq": seq,
                    "type": "up",
                    "t": t,
                    "code": code,
                    "key": None,
                    "repeat": False,
                }
            )
            seq += 1
            t += 120.0
    return events


def _payload(events: list[dict[str, Any]]) -> ValidatedSessionPayload:
    """Build a validator-shaped payload; the validator itself is out of scope."""
    return ValidatedSessionPayload(
        schema_version=1,
        mode="time",
        duration_limit_ms=30000,
        text_ref={"type": "words", "seed": 20261106, "count": 2},
        started_at="2026-11-09T10:05:00.000Z",
        client={
            "user_agent": "pytest",
            "platform": "test",
            "layout_hint": "unknown",
        },
        ignored={
            "repeat_keydowns": 0,
            "shortcuts": 0,
            "unsupported_keys": 0,
            "unsupported_chars": 0,
            "paste_attempts": 0,
        },
        events=tuple(events),
    )


def _analysis_with(
    payload: ValidatedSessionPayload,
    *,
    text: str = TEXT,
) -> SessionAnalysis:
    return analyze_session(
        text,
        payload.mode,
        payload.duration_limit_ms,
        payload.events,
    )


def _event_rows(database: str, session_id: str) -> list[sqlite3.Row]:
    connection = connect(database)
    try:
        return connection.execute(
            "SELECT seq, type, code, key, repeat FROM keystroke_events "
            "WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
    finally:
        connection.close()


def _table_rows(database: str, table: str, session_id: str) -> int:
    connection = connect(database)
    try:
        return connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
    finally:
        connection.close()


# --- Round trip -----------------------------------------------------------


def test_round_trip_save_and_retrieve(repository: SessionRepository) -> None:
    """Retrieving what was saved reproduces the engine's stored values."""
    # Four characters never complete the passage text and every down is
    # released, so the timer ends the session with no data-quality warnings.
    payload = _payload(_events(TEXT[:4]))
    analysis = _analysis_with(payload)

    created = repository.create(payload, analysis)
    record = repository.get(created.session_id)

    assert record is not None
    assert record == created
    assert len(record.session_id) == 32
    int(record.session_id, 16)
    assert record.created_at.endswith("Z")
    assert record.mode == "time"
    assert record.duration_limit_ms == 30000
    assert record.schema_version == 1
    assert record.analysis_version == 1
    assert record.text_ref == {"type": "words", "seed": 20261106, "count": 2}
    assert record.layout_hint == "unknown"
    assert record.client["layout_hint"] == "unknown"
    assert record.passage_text == TEXT
    assert record.typed_text == TEXT[:4]
    assert record.active_duration_ms == analysis.replay.active_duration_ms
    assert record.end_reason == analysis.replay.end_reason
    assert record.warnings == ()

    expected = analysis.metrics
    for field in (
        "total_keystrokes",
        "correct_keystrokes",
        "incorrect_keystrokes",
        "final_length",
        "uncorrected_errors",
        "corrected_errors",
        "backspace_count",
        "backspace_presses",
        "dwell_count",
        "iki_valid_count",
        "pause_count",
        "zero_interval_count",
        "total_pause_ms",
        "gross_wpm",
        "net_wpm",
        "accuracy_pct",
        "final_accuracy_pct",
        "avg_dwell_ms",
        "avg_iki_ms",
        "median_iki_ms",
        "iki_sd_ms",
        "iki_cv",
        "consistency_score",
        "longest_pause_ms",
    ):
        assert getattr(record.metrics, field) == getattr(expected, field), field


def test_read_back_error_rate_matches_documented_identity(
    repository: SessionRepository,
) -> None:
    """error_rate is restored as 100 - accuracy_pct (docs/METRICS.md §4.4)."""
    payload = _payload(_events(TEXT[:4], final_up=False))
    record = repository.create(payload, _analysis_with(payload))

    metrics = repository.get(record.session_id).metrics

    assert metrics.accuracy_pct == 100.0
    assert metrics.error_rate == 100.0 - metrics.accuracy_pct


def test_events_up_to_derived_end_are_stored(
    repository: SessionRepository,
    repository_database: str,
) -> None:
    """Only validated events up to the derived end reach the event log."""
    events = _events(TEXT)[:-1]  # finish at the completing keystroke
    tail = {
        "seq": len(events),
        "type": "down",
        "t": 1000.0,
        "code": CHAR_TO_CODE["a"],
        "key": "a",
        "repeat": False,
    }
    events.append(tail)
    payload = _payload(events)
    analysis = _analysis_with(payload)

    record = repository.create(payload, analysis)

    assert analysis.replay.dropped_after_end == 1
    assert record.typed_text == TEXT
    assert {(warning.code, warning.count) for warning in record.warnings} == {
        ("dropped_after_end", 1),
        ("open_at_end", 1),
    }
    rows = _event_rows(repository_database, record.session_id)
    assert len(rows) == len(payload.events) - 1
    assert [row["seq"] for row in rows] == [
        int(event["seq"]) for event in payload.events[:-1]
    ]


def test_all_events_stored_when_nothing_is_dropped(
    repository: SessionRepository,
    repository_database: str,
) -> None:
    """Sessions that end without the context already being closed keep all."""
    payload = _payload(_events(TEXT[:4], final_up=False))
    analysis = _analysis_with(payload)

    record = repository.create(payload, analysis)

    assert analysis.replay.dropped_after_end == 0
    assert len(_event_rows(repository_database, record.session_id)) == len(
        payload.events
    )


def test_key_stats_round_trip(repository: SessionRepository) -> None:
    """Per-key sums are stored once and returned unchanged, ordered by code."""
    payload = _payload(_events(TEXT, final_up=False))
    analysis = _analysis_with(payload)

    record = repository.create(payload, analysis)
    stats = repository.get_key_stats(record.session_id)

    expected = analysis.session_key_stats
    assert [stat.key_code for stat in stats] == sorted(expected)
    for stat in stats:
        source = expected[stat.key_code]
        assert stat.attempts == source.attempts
        assert stat.errors == source.errors
        assert stat.dwell_count == source.dwell_count
        assert stat.dwell_sum_ms == source.dwell_sum_ms
        assert stat.iki_count == source.iki_count
        assert stat.iki_sum_ms == source.iki_sum_ms


def test_unknown_id_returns_none(repository: SessionRepository) -> None:
    """A session that was never saved is not found."""
    assert repository.get("missing") is None


def test_records_persist_across_repository_instances(
    repository_database: str,
) -> None:
    """Persistence is no longer process-local (ADR-032 replaced by ADR-034)."""
    first = SessionRepository(repository_database)
    payload = _payload(_events(TEXT[:4]))
    created = first.create(payload, _analysis_with(payload))

    fresh = SessionRepository(repository_database)

    assert fresh.count() == 1
    assert fresh.get(created.session_id) is not None


# --- Transaction integrity ------------------------------------------------


def test_fk_cascade_removes_child_rows(
    repository: SessionRepository,
    repository_database: str,
) -> None:
    """Deleting a session removes its metrics, events and key stats."""
    payload = _payload(_events(TEXT[:4], final_up=False))
    record = repository.create(payload, _analysis_with(payload))

    connection = connect(repository_database)
    try:
        connection.execute(
            "DELETE FROM sessions WHERE id = ?",
            (record.session_id,),
        )
        connection.commit()
        for table in ("session_metrics", "keystroke_events", "session_key_stats"):
            assert _table_rows(repository_database, table, record.session_id) == 0
    finally:
        connection.close()


def test_rollback_on_mid_save_failure(
    repository: SessionRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure after the session row inserts leaves no partial data.

    The duplicated ``seq`` passes validation and replay but violates the
    ``keystroke_events(session_id, seq)`` uniqueness rule mid-transaction.
    """
    stamps = iter(f"2026-11-09T10:00:0{index}.000Z" for index in range(4))
    monkeypatch.setattr(repository_module, "_utc_now_iso", lambda: next(stamps))

    events = _events(TEXT[:2])
    events[-1]["seq"] = 0  # duplicates the first down's seq
    payload = _payload(events)

    with pytest.raises(sqlite3.IntegrityError):
        repository.create(payload, _analysis_with(payload))

    assert repository.count() == 0
    items, total = repository.list_sessions(limit=10)
    assert (items, total) == ([], 0)


# --- Paginated session list -----------------------------------------------


def test_paginated_list_returns_total_and_items(
    repository: SessionRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The list is newest first with the exact total across pages."""
    stamps = iter(f"2026-11-09T10:00:0{index}.000Z" for index in range(3))
    monkeypatch.setattr(repository_module, "_utc_now_iso", lambda: next(stamps))

    payload = _payload(_events(TEXT[:4], final_up=False))
    analysis = _analysis_with(payload)
    ids = [repository.create(payload, analysis).session_id for _ in range(3)]

    page_one, total = repository.list_sessions(limit=2)
    assert total == 3
    assert [item.session_id for item in page_one] == [ids[2], ids[1]]

    page_two, total = repository.list_sessions(limit=2, offset=2)
    assert total == 3
    assert [item.session_id for item in page_two] == [ids[0]]

    latest = page_one[0]
    assert latest.mode == "time"
    assert latest.end_reason == "time_up"
    assert latest.active_duration_ms == 30000.0
    assert latest.net_wpm == analysis.metrics.net_wpm
    assert latest.accuracy_pct == 100.0
    assert latest.consistency_score == analysis.metrics.consistency_score
