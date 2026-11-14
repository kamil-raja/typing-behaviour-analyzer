"""Progress endpoint and analytics page tests (P0-D2-06).

The endpoint must read stored sessions through the repository, return them in
chronological order and attach the engine-computed trailing moving average. The
page is a thin shell; ``analytics-page.js`` formats values and ``charts.js``
draws them, so no metric may be recomputed in the browser.
"""

from __future__ import annotations

import json
from typing import Any
import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.config import PROGRESS_DEFAULT_SCOPE, PROGRESS_MOVING_AVERAGE_WINDOW
from app.db import connect
from app.engine.keys import CHAR_TO_CODE


def _insert_session(
    database: str,
    session_id: str,
    created_at: str,
    *,
    net_wpm: float | None,
    accuracy_pct: float | None,
) -> None:
    """Insert one stored session with chosen derived values."""
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
            ") VALUES (?, ?, ?, ?, NULL, 10, 10, 0, 10, 0, 0, 0, 0, 0, "
            "0, 0, 0, 0.0, 0)",
            (session_id, net_wpm, net_wpm, accuracy_pct),
        )
        connection.commit()
    finally:
        connection.close()


def _seed_series(
    database: str,
    values: list[tuple[float | None, float | None]],
) -> None:
    for index, (net_wpm, accuracy_pct) in enumerate(values):
        _insert_session(
            database,
            f"s{index:02d}",
            f"2026-11-14T10:00:{index:02d}.000Z",
            net_wpm=net_wpm,
            accuracy_pct=accuracy_pct,
        )


def test_progress_empty_history(client: FlaskClient) -> None:
    """No stored sessions produce an empty series, not fake points."""
    response = client.get("/api/analytics/progress")

    assert response.status_code == 200
    assert response.get_json() == {
        "scope": PROGRESS_DEFAULT_SCOPE,
        "window": PROGRESS_MOVING_AVERAGE_WINDOW,
        "sessions": [],
    }


@pytest.mark.parametrize(
    "scope",
    ["last5", "last_10x", "", "LAST_10", "recent"],
)
def test_progress_rejects_unknown_scope(client: FlaskClient, scope: str) -> None:
    """Only the three documented scope values are accepted."""
    response = client.get("/api/analytics/progress", query_string={"scope": scope})

    assert response.status_code == 422
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == [
        {"field": "scope", "problem": "must be one of last_10, last_30, all"}
    ]


def test_progress_series_is_chronological_with_moving_average(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Sessions come oldest first with a trailing five-session average."""
    _seed_series(
        app.config["DATABASE"],
        [
            (10.0, 70.0),
            (20.0, 75.0),
            (30.0, 80.0),
            (40.0, 85.0),
            (50.0, 90.0),
            (60.0, 95.0),
            (70.0, 100.0),
        ],
    )

    body = client.get("/api/analytics/progress?scope=all").get_json()

    assert body["scope"] == "all"
    assert body["window"] == 5
    assert [item["session_id"] for item in body["sessions"]] == [
        "s00",
        "s01",
        "s02",
        "s03",
        "s04",
        "s05",
        "s06",
    ]
    assert [item["net_wpm"] for item in body["sessions"]] == [
        10.0,
        20.0,
        30.0,
        40.0,
        50.0,
        60.0,
        70.0,
    ]
    assert [item["moving_average_net_wpm"] for item in body["sessions"]] == [
        10.0,
        15.0,
        20.0,
        25.0,
        30.0,
        40.0,
        50.0,
    ]
    assert [item["moving_average_accuracy_pct"] for item in body["sessions"]] == [
        70.0,
        72.5,
        75.0,
        77.5,
        80.0,
        85.0,
        90.0,
    ]

    first = body["sessions"][0]
    assert first["created_at"] == "2026-11-14T10:00:00.000Z"
    assert first["mode"] == "time"
    assert first["duration_limit_ms"] == 30000


def test_progress_scope_limits_to_most_recent_sessions(
    app: Flask,
    client: FlaskClient,
) -> None:
    """last_10 keeps the ten newest sessions and restarts the average there."""
    _seed_series(
        app.config["DATABASE"],
        [(float(index), 90.0) for index in range(12)],
    )

    body = client.get("/api/analytics/progress?scope=last_10").get_json()

    assert [item["session_id"] for item in body["sessions"]] == [
        f"s{index:02d}" for index in range(2, 12)
    ]
    assert body["sessions"][0]["moving_average_net_wpm"] == 2.0
    assert body["sessions"][1]["moving_average_net_wpm"] == 2.5

    all_body = client.get("/api/analytics/progress?scope=last_30").get_json()
    assert len(all_body["sessions"]) == 12

    default_body = client.get("/api/analytics/progress").get_json()
    assert default_body["scope"] == "all"
    assert len(default_body["sessions"]) == 12


def test_progress_missing_metrics_stay_null(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Unavailable values stay null and are skipped by the moving average."""
    _seed_series(
        app.config["DATABASE"],
        [
            (10.0, None),
            (None, 80.0),
            (30.0, None),
        ],
    )

    sessions = client.get("/api/analytics/progress").get_json()["sessions"]

    assert [item["net_wpm"] for item in sessions] == [10.0, None, 30.0]
    assert [item["moving_average_net_wpm"] for item in sessions] == [
        10.0,
        10.0,
        20.0,
    ]
    assert [item["accuracy_pct"] for item in sessions] == [None, 80.0, None]
    assert [item["moving_average_accuracy_pct"] for item in sessions] == [
        None,
        80.0,
        80.0,
    ]


def test_progress_reads_newly_persisted_sessions(
    client: FlaskClient,
) -> None:
    """A submitted session appears in the progress series unchanged."""
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

    created = client.post(
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
    assert created.status_code == 201
    metrics = created.get_json()["metrics"]

    sessions = client.get("/api/analytics/progress").get_json()["sessions"]

    assert len(sessions) == 1
    assert sessions[0]["session_id"] == created.get_json()["session_id"]
    assert sessions[0]["net_wpm"] == metrics["net_wpm"]
    assert sessions[0]["accuracy_pct"] == metrics["accuracy_pct"]
    assert sessions[0]["moving_average_net_wpm"] == metrics["net_wpm"]
    assert sessions[0]["moving_average_accuracy_pct"] == metrics["accuracy_pct"]


def test_analytics_page_markup_and_navigation(client: FlaskClient) -> None:
    """The analytics page carries the scope toggle, charts and empty state."""
    response = client.get("/analytics")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "data-analytics-root" in html
    assert 'data-scope="all"' in html
    assert 'data-scope-option="last_10"' in html
    assert 'data-scope-option="last_30"' in html
    assert 'data-scope-option="all"' in html
    assert "No sessions yet." in html
    assert 'data-chart="wpm"' in html
    assert 'data-chart="accuracy"' in html
    assert "What to look for" in html
    assert "5-session moving average" in html
    assert "vendor/chart.umd.min.js" in html
    assert "js/analytics-page.js" in html
    assert 'aria-current="page"' in html
    assert "http://" not in html
    assert "https://" not in html


def test_analytics_assets_and_javascript_contract(client: FlaskClient) -> None:
    """Charts use the vendored build, server averages and theme events."""
    for path in (
        "/static/js/charts.js",
        "/static/js/analytics-page.js",
        "/static/vendor/chart.umd.min.js",
    ):
        assert client.get(path).status_code == 200, path

    page_script = client.get("/static/js/analytics-page.js").get_data(as_text=True)
    assert 'from "./charts.js"' in page_script
    assert "/api/analytics/progress?scope=" in page_script
    assert "moving_average_net_wpm" in page_script
    assert "moving_average_accuracy_pct" in page_script
    assert "tba:themechange" in page_script
    assert "applyChartTheme" in page_script
    assert ".destroy()" in page_script

    charts_script = client.get("/static/js/charts.js").get_data(as_text=True)
    assert "window.Chart" in charts_script
    assert "getPropertyValue" in charts_script
    assert 'chart.update("none")' in charts_script
    assert "spanGaps: false" in charts_script
    assert "tbaRole" in charts_script
