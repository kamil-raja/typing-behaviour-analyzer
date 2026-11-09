"""JSON API routes.

The text endpoint contracts are fixed by ADR-029. ``POST /api/sessions`` parses
the payload, delegates validation to ``app.validators``, resolves the text
through ``app.texts``, runs the pure engine and persists the result through
``app.repository`` before returning the documented response shape.

Routes contain no metric math and no SQL.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import asdict
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request, url_for

from ..config import (
    MAX_SESSION_BODY_BYTES,
    SESSION_MIN_K,
    SESSION_MIN_T_MS,
    WORD_COUNT_MAX,
    WORD_COUNT_MIN,
)
from ..engine import analyze_session
from ..engine.replay import END_COMPLETED, InvalidEventSequence
from ..errors import (
    INCOMPLETE_SESSION,
    INVALID_EVENT_SEQUENCE,
    INVALID_JSON,
    NOT_FOUND,
    PAYLOAD_TOO_LARGE,
    SESSION_TOO_SHORT,
    VALIDATION_ERROR,
    json_error,
)
from ..repository import STORE_EXTENSION_KEY, SessionRecord, SessionRepository
from ..texts import (
    TextNotFoundError,
    generate_words,
    get_passage,
    get_passages,
    resolve_text,
)
from ..validators import (
    PayloadTooLargeError,
    ValidationError,
    validate_session_payload,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")

PASSAGE_LABEL_LENGTH = 40
_COUNT_PATTERN = re.compile(r"[0-9]{1,3}")
_SEED_LIMIT = 2**31


def _passage_text_ref(passage_id: str) -> dict[str, str]:
    """Return the canonical text_ref object for a passage."""
    return {"type": "passage", "id": passage_id}


def _passage_label(text: str) -> str:
    """Return the first 40 characters of a passage as ASCII UI label text."""
    label = text[:PASSAGE_LABEL_LENGTH].rstrip()
    if len(text) > PASSAGE_LABEL_LENGTH:
        label = f"{label}..."
    return label


def _invalid_count(problem: str) -> tuple[Response, int]:
    """Return the documented validation error for the words endpoint."""
    return json_error(
        VALIDATION_ERROR,
        "The count query parameter is invalid.",
        [{"field": "count", "problem": problem}],
        status=422,
    )


def _session_metrics(record: SessionRecord) -> dict[str, Any]:
    """Shape the persisted engine metrics for the submission response.

    This is serialisation only: every number was computed by the engine before
    the repository stored it and is read back unchanged.
    """
    metrics = asdict(record.metrics)
    metrics.update(
        {
            "mode": record.mode,
            "duration_limit_ms": record.duration_limit_ms,
            "active_duration_ms": record.active_duration_ms,
            "end_reason": record.end_reason,
            "analysis_version": record.analysis_version,
        }
    )
    return metrics


def _session_warnings(record: SessionRecord) -> list[dict[str, Any]]:
    """Shape the persisted data-quality warnings for JSON."""
    return [
        {
            "code": warning.code,
            "count": warning.count,
            "message": warning.message,
        }
        for warning in record.warnings
    ]


def _session_detail(record: SessionRecord) -> dict[str, Any]:
    """Shape the stored session metadata; metrics and key stats are separate."""
    return {
        "session_id": record.session_id,
        "created_at": record.created_at,
        "schema_version": record.schema_version,
        "mode": record.mode,
        "duration_limit_ms": record.duration_limit_ms,
        "text_ref": dict(record.text_ref),
        "passage_text": record.passage_text,
        "typed_text": record.typed_text,
        "active_duration_ms": record.active_duration_ms,
        "end_reason": record.end_reason,
        "client": dict(record.client),
        "layout_hint": record.layout_hint,
        "analysis_version": record.analysis_version,
        "warnings": _session_warnings(record),
    }


@api_bp.get("/texts/passages")
def list_passages() -> Response:
    """List every passage in frozen source order with a display label."""
    passages = get_passages()
    return jsonify(
        {
            "passages": [
                {
                    "text_ref": _passage_text_ref(passage.id),
                    "label": _passage_label(passage.text),
                }
                for passage in passages
            ]
        }
    )


@api_bp.get("/texts/passages/<passage_id>")
def get_passage_text(passage_id: str) -> Response | tuple[Response, int]:
    """Return one passage's text_ref and text body."""
    try:
        text = get_passage(passage_id)
    except TextNotFoundError as error:
        return json_error(
            error.code,
            error.message,
            error.details,
            status=error.status,
        )
    return jsonify(
        {
            "text_ref": _passage_text_ref(passage_id),
            "text": text,
        }
    )


@api_bp.get("/texts/words")
def get_word_text() -> Response | tuple[Response, int]:
    """Generate deterministic word-mode text and return the chosen seed."""
    raw_count = request.args.get("count")
    if raw_count is None:
        return _invalid_count("is required")

    if _COUNT_PATTERN.fullmatch(raw_count) is None:
        return _invalid_count(
            f"must be an integer between {WORD_COUNT_MIN} and {WORD_COUNT_MAX}"
        )

    count = int(raw_count)
    if not WORD_COUNT_MIN <= count <= WORD_COUNT_MAX:
        return _invalid_count(
            f"must be an integer between {WORD_COUNT_MIN} and {WORD_COUNT_MAX}"
        )

    seed = secrets.randbelow(_SEED_LIMIT)
    return jsonify(
        {
            "text_ref": {"type": "words", "seed": seed, "count": count},
            "text": generate_words(seed, count),
        }
    )


@api_bp.post("/sessions")
def create_session() -> Response | tuple[Response, int]:
    """Validate, resolve, replay and store one submitted typing session."""
    raw = request.get_data(cache=True)
    if len(raw) > MAX_SESSION_BODY_BYTES:
        return json_error(
            PAYLOAD_TOO_LARGE,
            "Request body is too large.",
            [
                {
                    "field": "body",
                    "problem": f"must not exceed {MAX_SESSION_BODY_BYTES} bytes",
                }
            ],
            status=413,
        )

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return json_error(
            INVALID_JSON,
            "Request body must be valid JSON.",
            [{"field": "body", "problem": "is not valid JSON"}],
            status=400,
        )

    try:
        validated = validate_session_payload(
            payload,
            body_size_bytes=len(raw),
        )
    except PayloadTooLargeError as error:
        return json_error(
            error.code,
            error.message,
            error.details,
            status=error.status,
        )
    except ValidationError as error:
        return json_error(
            error.code,
            error.message,
            error.details,
            status=error.status,
        )

    try:
        text = resolve_text(validated.text_ref)
    except TextNotFoundError as error:
        return json_error(
            error.code,
            error.message,
            error.details,
            status=error.status,
        )

    try:
        analysis = analyze_session(
            text=text,
            mode=validated.mode,
            duration_limit_ms=validated.duration_limit_ms,
            events=validated.events,
        )
    except InvalidEventSequence as error:
        return json_error(
            INVALID_EVENT_SEQUENCE,
            "The event sequence is invalid.",
            [{"field": "events", "problem": str(error)}],
            status=422,
        )

    if validated.mode == "passage" and analysis.replay.end_reason != END_COMPLETED:
        return json_error(
            INCOMPLETE_SESSION,
            "The passage was not completed.",
            [
                {
                    "field": "events",
                    "problem": "the final buffer does not match the passage",
                }
            ],
            status=422,
        )

    if (
        analysis.replay.K < SESSION_MIN_K
        or analysis.replay.active_duration_ms < SESSION_MIN_T_MS
    ):
        return json_error(
            SESSION_TOO_SHORT,
            "This session is too short to save.",
            [
                {
                    "field": "events",
                    "problem": (
                        f"K must be at least {SESSION_MIN_K} and T must be "
                        f"at least {SESSION_MIN_T_MS} ms"
                    ),
                }
            ],
            status=422,
        )

    repository: SessionRepository = current_app.extensions[STORE_EXTENSION_KEY]
    record = repository.create(validated, analysis)

    return (
        jsonify(
            {
                "session_id": record.session_id,
                "metrics": _session_metrics(record),
                "warnings": _session_warnings(record),
                "links": {
                    "results": url_for(
                        "pages.results_page",
                        session_id=record.session_id,
                    )
                },
            }
        ),
        201,
    )


@api_bp.get("/sessions/<session_id>")
def get_session(session_id: str) -> Response | tuple[Response, int]:
    """Return one stored session's metadata, metrics and per-key sums."""
    repository: SessionRepository = current_app.extensions[STORE_EXTENSION_KEY]
    record = repository.get(session_id)
    if record is None:
        return json_error(
            NOT_FOUND,
            "Session not found.",
            [{"field": "session_id", "problem": "does not exist"}],
            status=404,
        )

    return jsonify(
        {
            "session": _session_detail(record),
            "metrics": asdict(record.metrics),
            "key_stats": [
                asdict(stat) for stat in repository.get_key_stats(session_id)
            ],
        }
    )
