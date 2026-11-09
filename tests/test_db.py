"""Schema and connection tests for P0-D2-01."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask

from app import create_app
from app.db import SCHEMA_VERSION, apply_schema, connect, get_db, init_db

SESSIONS_COLUMNS = [
    "id",
    "created_at",
    "mode",
    "duration_limit_ms",
    "text_ref_json",
    "passage_text",
    "typed_text",
    "active_duration_ms",
    "end_reason",
    "client_json",
    "layout_hint",
    "schema_version",
    "analysis_version",
]

METRICS_COLUMNS = [
    "session_id",
    "gross_wpm",
    "net_wpm",
    "accuracy_pct",
    "final_accuracy_pct",
    "total_keystrokes",
    "correct_keystrokes",
    "incorrect_keystrokes",
    "final_length",
    "uncorrected_errors",
    "corrected_errors",
    "erased_unresolved_errors",
    "backspace_count",
    "backspace_presses",
    "avg_dwell_ms",
    "median_dwell_ms",
    "dwell_count",
    "avg_iki_ms",
    "median_iki_ms",
    "iki_sd_ms",
    "iki_valid_count",
    "iki_cv",
    "consistency_score",
    "pause_count",
    "total_pause_ms",
    "longest_pause_ms",
    "zero_interval_count",
    "iki_hist_json",
    "data_quality_json",
]

EVENT_COLUMNS = [
    "id",
    "session_id",
    "seq",
    "type",
    "t_ms",
    "code",
    "key",
    "repeat",
]

KEY_STATS_COLUMNS = [
    "session_id",
    "key_code",
    "attempts",
    "errors",
    "dwell_count",
    "dwell_sum_ms",
    "iki_count",
    "iki_sum_ms",
]


@pytest.fixture()
def schema_conn() -> Iterator[sqlite3.Connection]:
    """An in-memory connection with the full schema applied."""
    connection = connect(":memory:")
    apply_schema(connection)
    try:
        yield connection
    finally:
        connection.close()


def _insert_session(
    connection: sqlite3.Connection,
    session_id: str = "s1",
    mode: str = "time",
    duration_limit_ms: int | None = 30_000,
) -> None:
    connection.execute(
        """
        INSERT INTO sessions (
            id, created_at, mode, duration_limit_ms, text_ref_json,
            passage_text, typed_text, active_duration_ms, end_reason,
            client_json, layout_hint, schema_version, analysis_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            "2026-11-08T10:00:00.000Z",
            mode,
            duration_limit_ms,
            '{"type": "passage", "id": "p_001"}',
            "hello",
            "hello",
            1000.0,
            "completed",
            '{"layout_hint": "unknown"}',
            "unknown",
            1,
            1,
        ),
    )


def _insert_metrics(
    connection: sqlite3.Connection,
    session_id: str = "s1",
) -> None:
    connection.execute(
        """
        INSERT INTO session_metrics (
            session_id, total_keystrokes, correct_keystrokes,
            incorrect_keystrokes, final_length, uncorrected_errors,
            corrected_errors, erased_unresolved_errors, backspace_count,
            backspace_presses, dwell_count, iki_valid_count, pause_count,
            total_pause_ms, zero_interval_count
        ) VALUES (?, 10, 10, 0, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0)
        """,
        (session_id,),
    )


def _insert_event(
    connection: sqlite3.Connection,
    session_id: str = "s1",
    seq: int = 0,
    event_type: str = "down",
    key: str | None = "a",
) -> None:
    connection.execute(
        """
        INSERT INTO keystroke_events (
            session_id, seq, type, t_ms, code, key, repeat
        ) VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (session_id, seq, event_type, 100.0 + seq, "KeyA", key),
    )


def _count(connection: sqlite3.Connection, table: str) -> int:
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# --- Fresh database initialisation ---------------------------------------


def test_first_run_creates_database_and_schema(tmp_path: Path) -> None:
    """create_app() initialises instance-style storage on first run."""
    database = tmp_path / "typing.db"

    create_app({"TESTING": True, "DATABASE": str(database)})

    assert database.is_file()
    connection = connect(str(database))
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert tables == {
            "sessions",
            "session_metrics",
            "keystroke_events",
            "session_key_stats",
        }
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        connection.close()


def test_apply_schema_is_idempotent(schema_conn: sqlite3.Connection) -> None:
    """Re-running initialisation leaves the schema intact."""
    apply_schema(schema_conn)

    assert _count(schema_conn, "sessions") == 0
    assert schema_conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_unknown_schema_version_aborts_startup(tmp_path: Path) -> None:
    """A database from an incompatible schema is not silently reused."""
    database = tmp_path / "typing.db"
    connection = connect(str(database))
    connection.execute("PRAGMA user_version = 99")
    connection.commit()
    connection.close()

    with pytest.raises(RuntimeError, match="does not match"):
        create_app({"TESTING": True, "DATABASE": str(database)})


# --- Blueprint fidelity ---------------------------------------------------


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        ("sessions", SESSIONS_COLUMNS),
        ("session_metrics", METRICS_COLUMNS),
        ("keystroke_events", EVENT_COLUMNS),
        ("session_key_stats", KEY_STATS_COLUMNS),
    ],
)
def test_columns_match_blueprint(
    schema_conn: sqlite3.Connection,
    table: str,
    expected: list[str],
) -> None:
    """Every table has exactly the blueprint §9 columns, in order."""
    actual = [
        row["name"]
        for row in schema_conn.execute(f"PRAGMA table_info({table})")
    ]
    assert actual == expected


def test_documented_indexes_exist(schema_conn: sqlite3.Connection) -> None:
    """sessions(created_at) and session_key_stats(key_code) are indexed."""
    session_indexes = {
        row["name"] for row in schema_conn.execute("PRAGMA index_list(sessions)")
    }
    key_stat_indexes = {
        row["name"]
        for row in schema_conn.execute("PRAGMA index_list(session_key_stats)")
    }

    assert "idx_sessions_created_at" in session_indexes
    assert "idx_session_key_stats_key_code" in key_stat_indexes


# --- Connection behaviour -------------------------------------------------


def test_connect_enables_foreign_keys() -> None:
    """Every factory connection enforces foreign keys."""
    connection = connect(":memory:")
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.row_factory is sqlite3.Row
    finally:
        connection.close()


def test_get_db_reuses_connection_and_teardown_closes(app: Flask) -> None:
    """One connection is shared per request and closed at app-context exit."""
    with app.app_context():
        first = get_db()
        assert get_db() is first
        assert first.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    with pytest.raises(sqlite3.ProgrammingError):
        first.execute("SELECT 1")


def test_init_db_can_run_twice(app: Flask) -> None:
    """Startup initialisation is safe to repeat."""
    init_db(app)

    with app.app_context():
        assert get_db().execute("PRAGMA user_version").fetchone()[0] == 1


# --- Constraints and foreign keys ----------------------------------------


def test_delete_session_cascades_to_child_tables(
    schema_conn: sqlite3.Connection,
) -> None:
    """Deleting a session removes its metrics, events and key stats."""
    _insert_session(schema_conn)
    _insert_metrics(schema_conn)
    _insert_event(schema_conn)
    schema_conn.execute(
        """
        INSERT INTO session_key_stats (
            session_id, key_code, attempts, errors, dwell_count,
            dwell_sum_ms, iki_count, iki_sum_ms
        ) VALUES ('s1', 'KeyA', 1, 0, 1, 80.0, 0, 0.0)
        """
    )

    schema_conn.execute("DELETE FROM sessions WHERE id = 's1'")

    assert _count(schema_conn, "session_metrics") == 0
    assert _count(schema_conn, "keystroke_events") == 0
    assert _count(schema_conn, "session_key_stats") == 0


def test_unknown_session_id_is_rejected(schema_conn: sqlite3.Connection) -> None:
    """Child rows require an existing parent session."""
    with pytest.raises(sqlite3.IntegrityError):
        _insert_event(schema_conn, session_id="missing")


@pytest.mark.parametrize(
    ("mode", "duration"),
    [("other", 30_000), ("time", None), ("passage", 30_000)],
)
def test_session_mode_and_duration_constraints(
    schema_conn: sqlite3.Connection,
    mode: str,
    duration: int | None,
) -> None:
    """mode and duration_limit_ms must satisfy the documented pairing."""
    with pytest.raises(sqlite3.IntegrityError):
        _insert_session(schema_conn, mode=mode, duration_limit_ms=duration)


def test_passage_session_accepts_null_duration(
    schema_conn: sqlite3.Connection,
) -> None:
    """The documented passage row is valid."""
    _insert_session(schema_conn, mode="passage", duration_limit_ms=None)

    assert _count(schema_conn, "sessions") == 1


@pytest.mark.parametrize(
    ("event_type", "key"),
    [("move", "a"), ("down", None), ("up", "a")],
)
def test_event_type_and_key_constraints(
    schema_conn: sqlite3.Connection,
    event_type: str,
    key: str | None,
) -> None:
    """type is down/up and only up events carry a null key."""
    _insert_session(schema_conn)

    with pytest.raises(sqlite3.IntegrityError):
        _insert_event(
            schema_conn,
            event_type=event_type,
            key=key,
        )


@pytest.mark.parametrize(
    "statement",
    [
        (
            "INSERT INTO keystroke_events "
            "(session_id, seq, type, t_ms, code, key, repeat) "
            "VALUES ('s1', 0, 'down', 10.0, 'KeyA', 'a', 2)"
        ),
        (
            "INSERT INTO keystroke_events "
            "(session_id, seq, type, t_ms, code, key, repeat) "
            "VALUES ('s1', -1, 'down', 10.0, 'KeyA', 'a', 0)"
        ),
        (
            "INSERT INTO keystroke_events "
            "(session_id, seq, type, t_ms, code, key, repeat) "
            "VALUES ('s1', 0, 'down', -1.0, 'KeyA', 'a', 0)"
        ),
    ],
)
def test_event_check_constraints(
    schema_conn: sqlite3.Connection,
    statement: str,
) -> None:
    """repeat, seq and t_ms enforce the documented bounds."""
    _insert_session(schema_conn)

    with pytest.raises(sqlite3.IntegrityError):
        schema_conn.execute(statement)


def test_duplicate_event_sequence_is_rejected(
    schema_conn: sqlite3.Connection,
) -> None:
    """(session_id, seq) is unique."""
    _insert_session(schema_conn)
    _insert_event(schema_conn, seq=0)

    with pytest.raises(sqlite3.IntegrityError):
        _insert_event(schema_conn, seq=0, event_type="up", key=None)


def test_duplicate_key_stat_row_is_rejected(
    schema_conn: sqlite3.Connection,
) -> None:
    """A session has at most one row per key_code."""
    _insert_session(schema_conn)
    row = ("s1", "KeyA", 1, 0, 1, 80.0, 0, 0.0)
    schema_conn.execute(
        """
        INSERT INTO session_key_stats (
            session_id, key_code, attempts, errors, dwell_count,
            dwell_sum_ms, iki_count, iki_sum_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        row,
    )

    with pytest.raises(sqlite3.IntegrityError):
        schema_conn.execute(
            """
            INSERT INTO session_key_stats (
                session_id, key_code, attempts, errors, dwell_count,
                dwell_sum_ms, iki_count, iki_sum_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
