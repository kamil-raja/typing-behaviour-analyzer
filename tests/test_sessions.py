"""API, integration and frontend-contract tests for the first vertical slice.

These tests exercise the documented flow: ``POST /api/sessions`` validates the
payload, resolves the text, runs the authoritative engine, stores the result in
memory and returns metrics plus a results link. The results page must render
those server-computed values, not provisional browser estimates.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.config import MAX_SESSION_BODY_BYTES
from app.engine import analyze_session
from app.engine.keys import CHAR_TO_CODE
from app.session_store import STORE_EXTENSION_KEY, InMemorySessionStore
from app.texts import generate_words, get_passage

ROOT = Path(__file__).resolve().parents[1]
WORDS_SEED = 20261106
WORDS_COUNT = 10


def _words_text() -> str:
    return generate_words(WORDS_SEED, WORDS_COUNT)


def _words_ref() -> dict[str, Any]:
    return {"type": "words", "seed": WORDS_SEED, "count": WORDS_COUNT}


def _typing_events(
    text: str,
    *,
    typed_text: str | None = None,
    interval_ms: float = 100.0,
    hold_ms: float = 45.0,
    include_final_up: bool = True,
) -> list[dict[str, Any]]:
    """Build a valid down/up sequence for ``typed_text``.

    Timestamps preserve the documented relative shape: each keydown is spaced by
    ``interval_ms`` and each keyup follows its keydown by ``hold_ms``. The final
    keyup is optionally omitted to mirror the real client, which stops capturing
    when the completing keystroke finishes the test.
    """
    typed = typed_text if typed_text is not None else text
    events: list[dict[str, Any]] = []

    for index, character in enumerate(typed):
        down_t = round(index * interval_ms, 1)
        code = CHAR_TO_CODE[character]
        events.append(
            {
                "seq": len(events),
                "type": "down",
                "t": down_t,
                "code": code,
                "key": character,
                "repeat": False,
            }
        )
        if index == len(typed) - 1 and not include_final_up:
            continue
        events.append(
            {
                "seq": len(events),
                "type": "up",
                "t": round(down_t + hold_ms, 1),
                "code": code,
                "key": None,
                "repeat": False,
            }
        )

    return events


def _append(
    events: list[dict[str, Any]],
    event_type: str,
    t: float,
    code: str,
    key: str | None,
    *,
    repeat: bool = False,
) -> None:
    events.append(
        {
            "seq": len(events),
            "type": event_type,
            "t": t,
            "code": code,
            "key": key,
            "repeat": repeat,
        }
    )


def _payload(
    text_ref: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    mode: str = "time",
    duration_limit_ms: int | None = 30000,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": mode,
        "duration_limit_ms": duration_limit_ms,
        "text_ref": text_ref,
        "started_at": "2026-11-06T10:05:00.000Z",
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
    }


def _store(app: Flask) -> InMemorySessionStore:
    return app.extensions[STORE_EXTENSION_KEY]


def test_create_session_returns_authoritative_engine_metrics(
    app: Flask,
    client: FlaskClient,
) -> None:
    """A clean time-mode submission returns the engine's numbers, not estimates."""
    text = _words_text()
    events = _typing_events(text, typed_text=text[:15])
    payload = _payload(_words_ref(), events)

    response = client.post("/api/sessions", json=payload)

    assert response.status_code == 201
    body = response.get_json()
    analysis = analyze_session(
        text,
        "time",
        30000,
        events,
    )

    assert len(body["session_id"]) == 32
    int(body["session_id"], 16)
    assert body["links"] == {"results": f"/results/{body['session_id']}"}
    assert body["warnings"] == []
    assert body["metrics"]["mode"] == "time"
    assert body["metrics"]["duration_limit_ms"] == 30000
    assert body["metrics"]["end_reason"] == "time_up"
    assert body["metrics"]["active_duration_ms"] == 30000.0
    assert body["metrics"]["analysis_version"] == 1

    expected = asdict(analysis.metrics)
    for field, value in expected.items():
        assert body["metrics"][field] == value, field

    stored = _store(app).get(body["session_id"])
    assert stored is not None
    assert stored.mode == "time"
    assert stored.text_ref == _words_ref()


def test_results_page_renders_server_metrics(
    client: FlaskClient,
) -> None:
    """The results page presents the stored server analysis, not provisional data."""
    text = _words_text()
    events = _typing_events(text, typed_text=text[:15])
    submission = client.post("/api/sessions", json=_payload(_words_ref(), events))
    body = submission.get_json()

    response = client.get(body["links"]["results"])

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Net WPM" in html
    assert "Accuracy" in html
    assert "Gross WPM" in html
    assert "About the measurements" in html
    assert "New test" in html
    assert "analysis version 1" in html
    assert "provisional" not in html.lower()

    net_wpm = body["metrics"]["net_wpm"]
    assert str(round(net_wpm, 1)) in html


def test_passage_completion_reports_completed_and_open_key(
    client: FlaskClient,
) -> None:
    """Passage mode completes only on an exact buffer match."""
    text = get_passage("p_001")
    events = _typing_events(text, include_final_up=False)
    payload = _payload(
        {"type": "passage", "id": "p_001"},
        events,
        mode="passage",
        duration_limit_ms=None,
    )

    response = client.post("/api/sessions", json=payload)

    assert response.status_code == 201
    body = response.get_json()
    metrics = body["metrics"]

    assert metrics["end_reason"] == "completed"
    assert metrics["active_duration_ms"] == round((len(text) - 1) * 100.0, 1)
    assert metrics["total_keystrokes"] == len(text)
    assert metrics["accuracy_pct"] == 100.0
    assert metrics["uncorrected_errors"] == 0
    assert metrics["corrected_errors"] == 0
    assert metrics["final_length"] == len(text)

    warning_codes = {warning["code"]: warning["count"] for warning in body["warnings"]}
    assert warning_codes == {"open_at_end": 1}


def test_timer_expiry_excludes_boundary_events(
    client: FlaskClient,
) -> None:
    """Events at or after the timer boundary are dropped and reported."""
    text = _words_text()
    events = _typing_events(text, typed_text=text[:12])
    _append(events, "down", 30000.0, CHAR_TO_CODE["x"], "x")
    _append(events, "up", 30040.0, CHAR_TO_CODE["x"], None)

    response = client.post("/api/sessions", json=_payload(_words_ref(), events))

    assert response.status_code == 201
    body = response.get_json()
    assert body["metrics"]["end_reason"] == "time_up"
    assert body["metrics"]["active_duration_ms"] == 30000.0
    assert body["metrics"]["total_keystrokes"] == 12

    warning_codes = {warning["code"]: warning["count"] for warning in body["warnings"]}
    assert warning_codes == {"dropped_after_end": 2}


def test_passage_without_exact_completion_is_incomplete(
    app: Flask,
    client: FlaskClient,
) -> None:
    """A passage attempt that never completes returns INCOMPLETE_SESSION."""
    text = get_passage("p_001")
    events = _typing_events(text, typed_text=text[:20])
    payload = _payload(
        {"type": "passage", "id": "p_001"},
        events,
        mode="passage",
        duration_limit_ms=None,
    )

    response = client.post("/api/sessions", json=payload)

    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "INCOMPLETE_SESSION"
    assert error["details"][0]["field"] == "events"
    assert _store(app).count() == 0


def test_short_time_session_is_rejected(
    app: Flask,
    client: FlaskClient,
) -> None:
    """K below the documented minimum is SESSION_TOO_SHORT."""
    text = _words_text()
    events = _typing_events(text, typed_text=text[:5])

    response = client.post("/api/sessions", json=_payload(_words_ref(), events))

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "SESSION_TOO_SHORT"
    assert _store(app).count() == 0


def test_fast_passage_completion_is_too_short(
    app: Flask,
    client: FlaskClient,
) -> None:
    """A completed passage under the 3-second minimum is still too short."""
    text = get_passage("p_001")
    events = _typing_events(
        text,
        interval_ms=10.0,
        hold_ms=5.0,
        include_final_up=False,
    )
    payload = _payload(
        {"type": "passage", "id": "p_001"},
        events,
        mode="passage",
        duration_limit_ms=None,
    )

    response = client.post("/api/sessions", json=payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "SESSION_TOO_SHORT"
    assert _store(app).count() == 0


def test_malformed_json_is_invalid_json(client: FlaskClient) -> None:
    """A body that is not JSON returns 400 INVALID_JSON."""
    response = client.post(
        "/api/sessions",
        data="{not json",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_JSON"


def test_non_object_payload_is_validation_error(client: FlaskClient) -> None:
    """Top-level JSON that is not an object is a 422 VALIDATION_ERROR."""
    response = client.post("/api/sessions", json=[])

    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["field"] == "payload"


def test_missing_fields_are_reported_together(client: FlaskClient) -> None:
    """Validation aggregates missing fields into one documented response."""
    response = client.post("/api/sessions", json={})

    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    fields = {detail["field"] for detail in error["details"]}
    assert {"schema_version", "mode", "text_ref", "started_at", "client"} <= fields


@pytest.mark.parametrize("field", ["ended_at_ms", "end_reason"])
def test_server_derived_fields_are_rejected(
    client: FlaskClient,
    field: str,
) -> None:
    """The client may not supply server-derived end state (ADR-025)."""
    text = _words_text()
    payload = _payload(_words_ref(), _typing_events(text, typed_text=text[:15]))
    payload[field] = None

    response = client.post("/api/sessions", json=payload)

    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == field for detail in error["details"])


def test_unknown_passage_is_text_not_found(
    app: Flask,
    client: FlaskClient,
) -> None:
    """Unknown passage ids are a 404 TEXT_NOT_FOUND from text resolution."""
    text = _words_text()
    events = _typing_events(text, typed_text=text[:15])
    payload = _payload(
        {"type": "passage", "id": "p_999"},
        events,
        mode="passage",
        duration_limit_ms=None,
    )

    response = client.post("/api/sessions", json=payload)

    assert response.status_code == 404
    error = response.get_json()["error"]
    assert error["code"] == "TEXT_NOT_FOUND"
    assert error["details"][0]["field"] == "text_ref.id"
    assert _store(app).count() == 0


def test_printable_key_at_full_buffer_is_invalid_sequence(
    app: Flask,
    client: FlaskClient,
) -> None:
    """A printable keydown at a full, incorrect buffer is INVALID_EVENT_SEQUENCE."""
    text = get_passage("p_001")
    typed = "x" + text[1:]
    events = _typing_events(text, typed_text=typed + "x")
    payload = _payload(
        {"type": "passage", "id": "p_001"},
        events,
        mode="passage",
        duration_limit_ms=None,
    )

    response = client.post("/api/sessions", json=payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "INVALID_EVENT_SEQUENCE"
    assert _store(app).count() == 0


def test_backspace_repeat_without_original_is_invalid_sequence(
    app: Flask,
    client: FlaskClient,
) -> None:
    """A repeat Backspace with no pending original is INVALID_EVENT_SEQUENCE."""
    text = _words_text()
    events: list[dict[str, Any]] = []
    _append(events, "down", 0.0, CHAR_TO_CODE[text[0]], text[0])
    _append(events, "down", 100.0, "Backspace", "Backspace", repeat=True)

    response = client.post("/api/sessions", json=_payload(_words_ref(), events))

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "INVALID_EVENT_SEQUENCE"
    assert _store(app).count() == 0


def test_oversized_body_is_payload_too_large(client: FlaskClient) -> None:
    """A body above the documented 2 MiB limit returns 413."""
    response = client.post(
        "/api/sessions",
        data=b" " * (MAX_SESSION_BODY_BYTES + 1),
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_erased_unresolved_error_is_shown_when_non_zero(
    client: FlaskClient,
) -> None:
    """Eu is rendered only when it is non-zero, with its documented label."""
    text = _words_text()
    typed = text[:10] + "x"
    events = _typing_events(text, typed_text=typed)
    _append(events, "down", 1200.0, "Backspace", "Backspace")
    _append(events, "up", 1245.0, "Backspace", None)

    response = client.post("/api/sessions", json=_payload(_words_ref(), events))

    assert response.status_code == 201
    body = response.get_json()
    assert body["metrics"]["erased_unresolved_errors"] == 1
    assert body["metrics"]["corrected_errors"] == 0

    html = client.get(body["links"]["results"]).get_data(as_text=True)
    assert "Erased, not retyped correctly" in html


def test_clean_result_hides_erased_unresolved_error(
    client: FlaskClient,
) -> None:
    """Eu is absent from the results page when its value is zero."""
    text = _words_text()
    events = _typing_events(text, typed_text=text[:15])
    body = client.post("/api/sessions", json=_payload(_words_ref(), events)).get_json()

    html = client.get(body["links"]["results"]).get_data(as_text=True)
    assert "Erased, not retyped correctly" not in html


def test_invalid_dwell_is_reported_as_a_warning(
    client: FlaskClient,
) -> None:
    """Zero-length dwell samples are excluded and reported."""
    text = _words_text()
    events = _typing_events(text, typed_text=text[:15], hold_ms=0.0)

    response = client.post("/api/sessions", json=_payload(_words_ref(), events))

    assert response.status_code == 201
    body = response.get_json()
    assert body["metrics"]["avg_dwell_ms"] is None
    assert body["metrics"]["dwell_count"] == 0
    assert body["metrics"]["invalid_dwell_count"] == 15
    warning_codes = {warning["code"]: warning["count"] for warning in body["warnings"]}
    assert warning_codes["invalid_dwell"] == 15

    html = client.get(body["links"]["results"]).get_data(as_text=True)
    assert "—" in html
    assert "None" not in html


def test_unknown_results_session_is_not_found(client: FlaskClient) -> None:
    """An unknown in-memory session id produces a 404 page."""
    response = client.get("/results/not-a-real-session")

    assert response.status_code == 404


def test_capture_accumulates_accepted_events_for_submission() -> None:
    """capture.js owns the accepted-event log and assigns contiguous seq values."""
    source = (ROOT / "app" / "static" / "js" / "capture.js").read_text(
        encoding="utf-8"
    )

    assert "getEvents" in source
    assert "seq: nextSeq" in source
    assert "nextSeq += 1" in source
    assert "record(eventObject)" in source
    assert "events = []" in source


def test_test_page_submits_the_documented_payload() -> None:
    """test-page.js posts once and never sends the server-derived end fields."""
    source = (ROOT / "app" / "static" / "js" / "test-page.js").read_text(
        encoding="utf-8"
    )

    assert '"/api/sessions"' in source
    assert "events: capture.getEvents()" in source
    assert "schema_version: SCHEMA_VERSION" in source
    assert "layout_hint" in source
    assert "ended_at_ms" not in source
    assert "end_reason" not in source


def test_completion_submission_is_deferred_until_the_final_event_is_recorded() -> None:
    """The completing keydown must be in the payload that finishes a passage.

    Passage mode calls ``onFinish`` from inside the keydown handler, before
    ``capture.js`` records the accepted event. Deferring submission to a
    microtask keeps the payload complete; without it the server replays an
    incomplete buffer and returns ``INCOMPLETE_SESSION``.
    """
    source = (ROOT / "app" / "static" / "js" / "test-page.js").read_text(
        encoding="utf-8"
    )

    assert "queueMicrotask(submitAttempt)" in source
    assert "submitAttempt();" not in source


def test_results_template_has_required_sections() -> None:
    """The results template carries the honesty note and a return path."""
    source = (ROOT / "app" / "templates" / "results.html").read_text(
        encoding="utf-8"
    )

    assert "About the measurements" in source
    assert "New test" in source
    assert "Take another test" in source
    assert "provisional" not in source.lower()
