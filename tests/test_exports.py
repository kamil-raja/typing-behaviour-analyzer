"""sessions.csv export tests (P0-D2-07).

The exporter owns the documented CSV contract (UTF-8 BOM, fixed column order,
empty NULL cells, formula-injection guard) and the route owns only the HTTP
download headers. Rows come from the repository, so the tests seed stored
sessions and never touch the developer database.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from flask import Flask
from flask.testing import FlaskClient

from app.db import connect
from app.engine.keys import CHAR_TO_CODE
from app.exporters import SESSIONS_COLUMNS, SESSIONS_FILENAME, sessions_csv
from app.repository import SessionExportRow

BLUEPRINT_COLUMNS = (
    "session_id",
    "created_at",
    "mode",
    "duration_limit_ms",
    "active_duration_ms",
    "end_reason",
    "gross_wpm",
    "net_wpm",
    "accuracy_pct",
    "final_accuracy_pct",
    "total_keystrokes",
    "correct_keystrokes",
    "incorrect_keystrokes",
    "backspace_count",
)


def _base_row() -> SessionExportRow:
    return SessionExportRow(
        session_id="abc123",
        created_at="2026-11-14T10:00:00.000Z",
        mode="time",
        duration_limit_ms=30000,
        active_duration_ms=30000.0,
        end_reason="time_up",
        gross_wpm=12.5,
        net_wpm=10.0,
        accuracy_pct=95.0,
        final_accuracy_pct=90.0,
        total_keystrokes=100,
        correct_keystrokes=95,
        incorrect_keystrokes=5,
        backspace_count=2,
    )


def _parse(body: bytes) -> list[list[str]]:
    """Decode the download body the way a spreadsheet app would."""
    return list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))


def _insert_session(
    database: str,
    session_id: str,
    created_at: str,
    *,
    gross_wpm: float | None = 12.5,
    net_wpm: float | None = 10.0,
    accuracy_pct: float | None = 95.0,
    final_accuracy_pct: float | None = 90.0,
    total_keystrokes: int = 100,
    correct_keystrokes: int = 95,
    incorrect_keystrokes: int = 5,
    backspace_count: int = 2,
) -> None:
    """Insert one stored session with chosen export values."""
    connection = connect(database)
    try:
        connection.execute(
            "INSERT INTO sessions ("
            "id, created_at, mode, duration_limit_ms, text_ref_json, "
            "passage_text, typed_text, active_duration_ms, end_reason, "
            "client_json, layout_hint, schema_version, analysis_version"
            ") VALUES (?, ?, 'time', 30000, ?, 'alpha bravo', 'alpha bravo', "
            "30000.0, 'time_up', ?, 'unknown', 1, 1)",
            (
                session_id,
                created_at,
                json.dumps({"type": "words", "seed": 1, "count": 2}),
                json.dumps({"layout_hint": "unknown"}),
            ),
        )
        connection.execute(
            "INSERT INTO session_metrics ("
            "session_id, gross_wpm, net_wpm, accuracy_pct, final_accuracy_pct, "
            "total_keystrokes, correct_keystrokes, incorrect_keystrokes, "
            "final_length, uncorrected_errors, corrected_errors, "
            "erased_unresolved_errors, backspace_count, backspace_presses, "
            "dwell_count, iki_valid_count, pause_count, total_pause_ms, "
            "zero_interval_count"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, 10, 0, 0, 0, ?, 0, 0, 0, 0, "
            "0.0, 0)",
            (
                session_id,
                gross_wpm,
                net_wpm,
                accuracy_pct,
                final_accuracy_pct,
                total_keystrokes,
                correct_keystrokes,
                incorrect_keystrokes,
                backspace_count,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _post_session(client: FlaskClient) -> dict[str, Any]:
    """Submit one valid time-mode session and return the 201 body."""
    text = "alpha bravo charlie"
    events: list[dict[str, Any]] = []
    for index, character in enumerate(text):
        code = CHAR_TO_CODE[character]
        events.append(
            {
                "seq": len(events),
                "type": "down",
                "t": index * 250.0,
                "code": code,
                "key": character,
                "repeat": False,
            }
        )
        events.append(
            {
                "seq": len(events),
                "type": "up",
                "t": index * 250.0 + 50.0,
                "code": code,
                "key": None,
                "repeat": False,
            }
        )

    response = client.post(
        "/api/sessions",
        json={
            "schema_version": 1,
            "mode": "time",
            "duration_limit_ms": 30000,
            "text_ref": {"type": "words", "seed": 20261106, "count": 10},
            "started_at": "2026-11-14T10:05:00.000Z",
            "client": {
                "user_agent": "pytest",
                "platform": "test",
                "layout_hint": "unknown",
            },
            "ignored": {
                "repeat_keydowns": 0,
                "shortcuts": 0,
                "unsupported_keys": 0,
                "unsupported_chars": 0,
                "paste_attempts": 0,
            },
            "events": events,
        },
    )
    assert response.status_code == 201
    return response.get_json()


def test_sessions_columns_match_blueprint_order() -> None:
    """The export column tuple is exactly the blueprint §10 order."""
    assert SESSIONS_COLUMNS == BLUEPRINT_COLUMNS


def test_empty_database_returns_header_only_csv(client: FlaskClient) -> None:
    """An empty export is still a valid BOM-prefixed CSV with the header."""
    response = client.get("/api/export/sessions.csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert (
        response.headers["Content-Disposition"]
        == f'attachment; filename="{SESSIONS_FILENAME}"'
    )
    body = response.get_data()
    assert body.startswith(b"\xef\xbb\xbf")
    assert _parse(body) == [list(SESSIONS_COLUMNS)]
    assert body.endswith(b"\r\n")


def test_single_stored_session_exports_persisted_values(
    client: FlaskClient,
) -> None:
    """The export row mirrors the persisted session and its stored metrics."""
    created = _post_session(client)
    metrics = created["metrics"]

    rows = _parse(client.get("/api/export/sessions.csv").get_data())

    assert len(rows) == 2
    assert rows[0] == list(SESSIONS_COLUMNS)
    exported = dict(zip(SESSIONS_COLUMNS, rows[1], strict=True))
    assert exported["session_id"] == created["session_id"]
    assert exported["mode"] == "time"
    assert exported["duration_limit_ms"] == "30000"
    assert exported["end_reason"] == metrics["end_reason"]
    assert float(exported["gross_wpm"]) == metrics["gross_wpm"]
    assert float(exported["net_wpm"]) == metrics["net_wpm"]
    assert float(exported["accuracy_pct"]) == metrics["accuracy_pct"]
    assert float(exported["final_accuracy_pct"]) == metrics["final_accuracy_pct"]
    assert exported["total_keystrokes"] == str(metrics["total_keystrokes"])
    assert exported["correct_keystrokes"] == str(metrics["correct_keystrokes"])
    assert exported["incorrect_keystrokes"] == str(metrics["incorrect_keystrokes"])
    assert exported["backspace_count"] == str(metrics["backspace_count"])


def test_multiple_sessions_export_newest_first(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Every stored session is exported, newest first like the history list."""
    database = app.config["DATABASE"]
    _insert_session(database, "older", "2026-11-13T09:00:00.000Z")
    _insert_session(database, "newest", "2026-11-14T09:00:00.000Z")
    _insert_session(database, "middle", "2026-11-13T18:00:00.000Z")

    rows = _parse(client.get("/api/export/sessions.csv").get_data())

    assert [row[0] for row in rows[1:]] == ["newest", "middle", "older"]


def test_null_metrics_export_as_empty_cells(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Unavailable metrics are empty cells, never ``None`` or ``null``."""
    _insert_session(
        app.config["DATABASE"],
        "nomet",
        "2026-11-14T09:00:00.000Z",
        gross_wpm=None,
        net_wpm=None,
        accuracy_pct=None,
        final_accuracy_pct=None,
    )

    exported = dict(
        zip(
            SESSIONS_COLUMNS,
            _parse(client.get("/api/export/sessions.csv").get_data())[1],
            strict=True,
        )
    )

    for column in (
        "gross_wpm",
        "net_wpm",
        "accuracy_pct",
        "final_accuracy_pct",
    ):
        assert exported[column] == ""
    assert "None" not in exported.values()
    assert "null" not in exported.values()
    assert exported["total_keystrokes"] == "100"


def test_injection_guard_neutralises_formula_cells() -> None:
    """Cells starting with = + - @ get a leading apostrophe."""
    row = replace(
        _base_row(),
        session_id="=1+1",
        created_at="+cmd",
        mode="-2+3",
        end_reason="@SUM(A1)",
    )

    parsed = _parse(sessions_csv([row]))

    assert parsed[1][0] == "'=1+1"
    assert parsed[1][1] == "'+cmd"
    assert parsed[1][2] == "'-2+3"
    assert parsed[1][5] == "'@SUM(A1)"
    assert parsed[1][3] == "30000"


def test_csv_quotes_delimiters_and_unicode_round_trip() -> None:
    """Commas, quotes, newlines and non-ASCII text survive the round trip."""
    tricky = 'té,mode "quoted"\nsecond line'
    row = replace(_base_row(), mode=tricky)

    parsed = _parse(sessions_csv([row]))

    assert parsed[1][2] == tricky
    assert len(parsed) == 2


def test_export_is_repeatable_and_read_only(
    app: Flask,
    client: FlaskClient,
) -> None:
    """The download does not mutate stored data and is byte-stable."""
    _insert_session(app.config["DATABASE"], "s1", "2026-11-14T09:00:00.000Z")

    first = client.get("/api/export/sessions.csv").get_data()
    second = client.get("/api/export/sessions.csv").get_data()

    assert first == second
    connection = connect(app.config["DATABASE"])
    try:
        count = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    finally:
        connection.close()
    assert count == 1


def test_export_layers_stay_separate() -> None:
    """SQL stays in the repository; the route only builds the HTTP response."""
    root = Path(__file__).resolve().parents[1]
    route_source = (root / "app" / "routes" / "exports.py").read_text(
        encoding="utf-8"
    )
    exporter_source = (root / "app" / "exporters.py").read_text(encoding="utf-8")

    assert "list_export_rows" in route_source
    assert "sessions_csv" in route_source
    assert "SELECT" not in route_source
    assert "INSERT" not in route_source
    assert "sqlite3" not in exporter_source
    assert "flask" not in exporter_source
    assert "SELECT" not in exporter_source
