"""Progress endpoint and analytics page tests (P0-D2-06).

The endpoint must read stored sessions through the repository, return them in
chronological order and attach the engine-computed trailing moving average. The
page is a thin shell; ``analytics-page.js`` formats values and ``charts.js``
draws them, so no metric may be recomputed in the browser.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.config import (
    HEATMAP_MIN_N,
    PROGRESS_DEFAULT_SCOPE,
    PROGRESS_MOVING_AVERAGE_WINDOW,
)
from app.db import connect
from app.engine.keys import (
    CHAR_TO_CODE,
    HEATMAP_METHOD,
    KEY_CODE_LABELS,
    wilson_ci,
)
from app.texts import generate_words


def _insert_session(
    database: str,
    session_id: str,
    created_at: str,
    *,
    net_wpm: float | None,
    accuracy_pct: float | None,
    backspace_presses: int = 0,
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
            ") VALUES (?, ?, ?, ?, NULL, 10, 10, 0, 10, 0, 0, 0, 0, ?, "
            "0, 0, 0, 0.0, 0)",
            (session_id, net_wpm, net_wpm, accuracy_pct, backspace_presses),
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


def _insert_key_stat(
    database: str,
    session_id: str,
    key_code: str,
    *,
    attempts: int = 0,
    errors: int = 0,
    dwell_count: int = 0,
    dwell_sum_ms: float = 0.0,
    iki_count: int = 0,
    iki_sum_ms: float = 0.0,
) -> None:
    """Insert one stored per-session key row."""
    connection = connect(database)
    try:
        connection.execute(
            "INSERT INTO session_key_stats ("
            "session_id, key_code, attempts, errors, dwell_count, "
            "dwell_sum_ms, iki_count, iki_sum_ms"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                key_code,
                attempts,
                errors,
                dwell_count,
                dwell_sum_ms,
                iki_count,
                iki_sum_ms,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _post_text_session(client: FlaskClient, text: str) -> Any:
    """Submit a deterministic time-mode session for ``text``."""
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
    return client.post(
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
    created = _post_text_session(client, text)
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


# --- Historical key statistics --------------------------------------------


def _key(body: dict[str, Any], code: str) -> dict[str, Any]:
    """Return one key entry from a heatmap response."""
    return next(item for item in body["keys"] if item["code"] == code)


def test_keys_empty_history(client: FlaskClient) -> None:
    """No sessions still return every renderable key, all grey."""
    response = client.get("/api/analytics/keys")

    assert response.status_code == 200
    body = response.get_json()
    assert body["scope"] == PROGRESS_DEFAULT_SCOPE
    assert body["method"] == HEATMAP_METHOD
    assert body["min_observations"] == HEATMAP_MIN_N
    assert body["baseline_error_rate"] is None
    assert body["overall_mean_dwell_ms"] is None
    assert body["scoped_session_count"] == 0
    assert len(body["keys"]) == len(KEY_CODE_LABELS)
    assert {item["class"] for item in body["keys"]} == {"insufficient"}
    assert {item["attempts"] for item in body["keys"]} == {0}
    assert _key(body, "Backspace")["backspace_presses"] == 0


@pytest.mark.parametrize("scope", ["last5", "last_10x", "", "LAST_10", "recent"])
def test_keys_rejects_unknown_scope(client: FlaskClient, scope: str) -> None:
    """The key endpoint reuses the progress scope values and error format."""
    response = client.get("/api/analytics/keys", query_string={"scope": scope})

    assert response.status_code == 422
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == [
        {"field": "scope", "problem": "must be one of last_10, last_30, all"}
    ]


def test_keys_aggregates_across_sessions(app: Flask, client: FlaskClient) -> None:
    """Sums add up and the error rate comes from the pooled totals."""
    database = app.config["DATABASE"]
    _insert_session(
        database, "s1", "2026-11-14T10:00:00.000Z", net_wpm=10.0, accuracy_pct=90.0
    )
    _insert_session(
        database, "s2", "2026-11-14T10:01:00.000Z", net_wpm=20.0, accuracy_pct=80.0
    )
    _insert_key_stat(
        database,
        "s1",
        "KeyA",
        attempts=10,
        errors=1,
        dwell_count=10,
        dwell_sum_ms=1_000.0,
        iki_count=9,
        iki_sum_ms=900.0,
    )
    _insert_key_stat(
        database,
        "s2",
        "KeyA",
        attempts=90,
        errors=18,
        dwell_count=80,
        dwell_sum_ms=8_000.0,
        iki_count=70,
        iki_sum_ms=7_000.0,
    )
    _insert_key_stat(
        database, "s1", "KeyB", attempts=5, dwell_count=5, dwell_sum_ms=500.0
    )

    body = client.get("/api/analytics/keys?scope=all").get_json()
    key_a = _key(body, "KeyA")

    assert body["scope"] == "all"
    assert body["scoped_session_count"] == 2
    assert key_a["attempts"] == 100
    assert key_a["errors"] == 19
    assert key_a["error_rate"] == pytest.approx(0.19)
    assert key_a["session_count"] == 2
    assert key_a["dwell_count"] == 90
    assert key_a["mean_dwell_ms"] == pytest.approx(100.0)
    assert key_a["iki_count"] == 79
    assert key_a["mean_iki_ms"] == pytest.approx(100.0)
    assert body["baseline_error_rate"] == pytest.approx(19 / 105)
    assert body["overall_mean_dwell_ms"] == pytest.approx(100.0)
    assert _key(body, "KeyQ")["attempts"] == 0
    assert _key(body, "KeyQ")["session_count"] == 0


def test_keys_scope_isolation(app: Flask, client: FlaskClient) -> None:
    """last_10 uses only the ten newest sessions and restarts the totals."""
    database = app.config["DATABASE"]
    for index in range(12):
        _insert_session(
            database,
            f"s{index:02d}",
            f"2026-11-14T10:00:{index:02d}.000Z",
            net_wpm=float(index),
            accuracy_pct=90.0,
            backspace_presses=1 if index == 0 else 0,
        )
        _insert_key_stat(
            database,
            f"s{index:02d}",
            "KeyA",
            attempts=10,
            errors=2 if index == 0 else 0,
        )

    all_body = client.get("/api/analytics/keys?scope=all").get_json()
    assert all_body["scoped_session_count"] == 12
    assert _key(all_body, "KeyA")["attempts"] == 120
    assert _key(all_body, "KeyA")["errors"] == 2
    assert _key(all_body, "KeyA")["session_count"] == 12
    assert all_body["baseline_error_rate"] == pytest.approx(2 / 120)
    assert _key(all_body, "Backspace")["backspace_presses"] == 1

    recent = client.get("/api/analytics/keys?scope=last_10").get_json()
    assert recent["scope"] == "last_10"
    assert recent["scoped_session_count"] == 10
    assert _key(recent, "KeyA")["attempts"] == 100
    assert _key(recent, "KeyA")["errors"] == 0
    assert _key(recent, "KeyA")["session_count"] == 10
    assert _key(recent, "Backspace")["backspace_presses"] == 0

    default_body = client.get("/api/analytics/keys").get_json()
    assert default_body["scope"] == "all"
    assert default_body["scoped_session_count"] == 12

    thirty = client.get("/api/analytics/keys?scope=last_30").get_json()
    assert thirty["scoped_session_count"] == 12


def test_keys_counts_sessions_without_key_statistics(
    app: Flask,
    client: FlaskClient,
) -> None:
    """A session with no stored key rows counts but contributes nothing."""
    database = app.config["DATABASE"]
    _insert_session(
        database, "s1", "2026-11-14T10:00:00.000Z", net_wpm=10.0, accuracy_pct=90.0
    )
    _insert_session(
        database, "s2", "2026-11-14T10:01:00.000Z", net_wpm=20.0, accuracy_pct=80.0
    )
    _insert_key_stat(database, "s2", "KeyA", attempts=4, errors=1)

    body = client.get("/api/analytics/keys").get_json()

    assert body["scoped_session_count"] == 2
    assert _key(body, "KeyA")["attempts"] == 4
    assert _key(body, "KeyA")["session_count"] == 1


def test_keys_response_structure_and_classification(
    app: Flask,
    client: FlaskClient,
) -> None:
    """The response carries the documented fields and a correct class."""
    database = app.config["DATABASE"]
    _insert_session(
        database, "s1", "2026-11-14T10:00:00.000Z", net_wpm=10.0, accuracy_pct=90.0
    )
    _insert_key_stat(database, "s1", "KeyA", attempts=20, errors=6)
    _insert_key_stat(database, "s1", "KeyB", attempts=180, errors=17)

    body = client.get("/api/analytics/keys").get_json()
    key_a = _key(body, "KeyA")

    assert set(key_a) == {
        "code",
        "label",
        "attempts",
        "errors",
        "error_rate",
        "ci_low",
        "ci_high",
        "dwell_count",
        "mean_dwell_ms",
        "iki_count",
        "mean_iki_ms",
        "class",
        "dwell_flag",
        "reason",
        "session_count",
        "backspace_presses",
    }
    assert key_a["label"] == "A"
    assert key_a["class"] == "weak"
    assert key_a["ci_low"] == pytest.approx(wilson_ci(6, 20)[0])
    assert key_a["ci_high"] == pytest.approx(wilson_ci(6, 20)[1])
    assert key_a["dwell_flag"] is None
    assert "weak" in key_a["reason"]
    assert _key(body, "KeyB")["class"] == "strong"
    assert "significant" not in json.dumps(body)


def test_keys_backspace_presses_are_separate_from_dwell(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Stored press count is reported even when no valid keyup added dwell."""
    database = app.config["DATABASE"]
    _insert_session(
        database,
        "s1",
        "2026-11-14T10:00:00.000Z",
        net_wpm=10.0,
        accuracy_pct=90.0,
        backspace_presses=3,
    )
    _insert_key_stat(
        database, "s1", "Backspace", dwell_count=1, dwell_sum_ms=250.0
    )

    body = client.get("/api/analytics/keys").get_json()
    backspace = _key(body, "Backspace")

    assert backspace["backspace_presses"] == 3
    assert backspace["dwell_count"] == 1
    assert backspace["mean_dwell_ms"] == pytest.approx(250.0)
    assert backspace["class"] == "insufficient"
    assert _key(body, "KeyA")["backspace_presses"] is None


def test_keys_reads_newly_persisted_sessions(client: FlaskClient) -> None:
    """A submitted session's stored key rows appear in the heatmap."""
    text = generate_words(20261106, 10)
    created = _post_text_session(client, text)
    assert created.status_code == 201

    body = client.get("/api/analytics/keys").get_json()
    key_a = _key(body, "KeyA")

    assert body["scoped_session_count"] == 1
    assert key_a["attempts"] == text.count("a")
    assert key_a["errors"] == 0
    assert key_a["session_count"] == 1
    assert _key(body, "KeyZ")["attempts"] == 0


def test_keys_route_delegates_sql_and_aggregation() -> None:
    """The route holds no SQL and delegates the aggregation to the engine."""
    source = (
        Path(__file__).resolve().parents[1] / "app" / "routes" / "api.py"
    ).read_text(encoding="utf-8")

    assert "list_scoped_key_stats" in source
    assert "build_key_heatmap" in source
    assert "SELECT" not in source
