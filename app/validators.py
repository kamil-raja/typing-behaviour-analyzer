"""Request and event validation for the Typing Behaviour Analyzer.

Responsibility: validate the session payload defined in
``docs/EVENT_SCHEMA.md`` §6–§7 before text resolution and replay. This module is
pure Python: it makes no HTTP calls, touches no database and performs no metric
calculations. Routes translate :class:`ValidationError` and
:class:`PayloadTooLargeError` through :func:`app.errors.json_error`.

The timer boundary is deliberately not a validation failure. Events at or after
``duration_limit_ms`` are structurally valid; replay excludes them and derives
``time_up`` (ADR-026).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, cast

from app.config import (
    ALLOWED_TIME_LIMITS_MS,
    MAX_SESSION_BODY_BYTES,
    MAX_SESSION_EVENTS,
    MIN_SESSION_EVENTS,
    SUPPORTED_SCHEMA_VERSION,
    WORD_COUNT_MAX,
    WORD_COUNT_MIN,
)
from app.errors import PAYLOAD_TOO_LARGE, VALIDATION_ERROR

KEY_PATTERN: Final = re.compile(r"[\x20-\x7E]")
CODE_PATTERN: Final = re.compile(r"[A-Za-z0-9]{1,32}")

_MODES: Final = frozenset({"time", "passage"})
_EVENT_TYPES: Final = frozenset({"down", "up"})
_LAYOUT_HINTS: Final = frozenset({"qwerty", "non-qwerty", "unknown"})
_IGNORED_COUNTERS: Final = (
    "repeat_keydowns",
    "shortcuts",
    "unsupported_keys",
    "unsupported_chars",
    "paste_attempts",
)
_FORBIDDEN_FIELDS: Final = ("ended_at_ms", "end_reason")
_MISSING: Final = object()

ValidationDetails = list[dict[str, str]]


class ValidationError(ValueError):
    """A request-validation failure in the documented API error shape.

    Routes should pass ``code``, ``message``, ``details`` and ``status`` to
    :func:`app.errors.json_error`.
    """

    code = VALIDATION_ERROR
    status = 422

    def __init__(
        self,
        message: str,
        details: ValidationDetails | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: ValidationDetails = list(details or [])


class PayloadTooLargeError(ValidationError):
    """The request body exceeds the documented 2 MB limit."""

    code = PAYLOAD_TOO_LARGE
    status = 413


@dataclass(frozen=True)
class ValidatedSessionPayload:
    """A structurally validated session payload.

    ``events`` remains a sequence of mappings so it can be passed directly to
    :func:`app.engine.analyze_session`. Text resolution and replay remain the
    responsibility of later layers.
    """

    schema_version: int
    mode: str
    duration_limit_ms: int | None
    text_ref: Mapping[str, Any]
    started_at: str
    client: Mapping[str, Any]
    ignored: Mapping[str, int]
    events: tuple[Mapping[str, Any], ...]


def _add(
    details: ValidationDetails,
    field: str,
    problem: str,
) -> None:
    """Append one ``{field, problem}`` detail."""
    details.append({"field": field, "problem": problem})


def _required(
    payload: Mapping[str, Any],
    field: str,
    details: ValidationDetails,
    *,
    path: str | None = None,
) -> Any:
    """Return ``payload[field]`` or the missing sentinel with a detail.

    ``path`` is the dotted/indexed location reported in ``details`` and
    defaults to ``field``. Nested objects should always pass it so that
    callers receive e.g. ``client.user_agent`` rather than ``user_agent``.
    """
    if field not in payload:
        _add(details, path or field, "is required")
        return _MISSING
    return payload[field]


def _is_finite_number(value: object) -> bool:
    """Return whether ``value`` is a finite JSON number, excluding booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _validate_schema_version(
    value: object,
    details: ValidationDetails,
) -> None:
    if value is _MISSING:
        return
    if type(value) is not int or value != SUPPORTED_SCHEMA_VERSION:
        _add(
            details,
            "schema_version",
            f"must be the integer {SUPPORTED_SCHEMA_VERSION}",
        )


def _validate_mode(value: object, details: ValidationDetails) -> None:
    if value is _MISSING:
        return
    if not isinstance(value, str) or value not in _MODES:
        _add(details, "mode", "must be 'time' or 'passage'")


def _validate_duration(
    mode: object,
    value: object,
    details: ValidationDetails,
) -> None:
    if value is _MISSING:
        return
    if mode == "time":
        if type(value) is not int or value not in ALLOWED_TIME_LIMITS_MS:
            _add(
                details,
                "duration_limit_ms",
                "must be one of 15000, 30000, 60000 milliseconds",
            )
    elif mode == "passage":
        if value is not None:
            _add(
                details,
                "duration_limit_ms",
                "must be null in passage mode",
            )


def _validate_text_ref(
    value: object,
    details: ValidationDetails,
) -> Mapping[str, Any] | None:
    if value is _MISSING:
        return None
    if not isinstance(value, Mapping):
        _add(details, "text_ref", "must be a JSON object")
        return None

    ref_type = _required(value, "type", details, path="text_ref.type")
    if ref_type is _MISSING:
        return value
    if not isinstance(ref_type, str):
        _add(details, "text_ref.type", "must be 'passage' or 'words'")
        return value

    if ref_type == "passage":
        passage_id = _required(value, "id", details, path="text_ref.id")
        if passage_id is not _MISSING and (
            not isinstance(passage_id, str) or not passage_id
        ):
            _add(details, "text_ref.id", "must be a non-empty string")
    elif ref_type == "words":
        seed = _required(value, "seed", details, path="text_ref.seed")
        if seed is not _MISSING and type(seed) is not int:
            _add(details, "text_ref.seed", "must be an integer")

        count = _required(value, "count", details, path="text_ref.count")
        if count is not _MISSING and (
            type(count) is not int
            or count < WORD_COUNT_MIN
            or count > WORD_COUNT_MAX
        ):
            _add(
                details,
                "text_ref.count",
                f"must be an integer between {WORD_COUNT_MIN} and "
                f"{WORD_COUNT_MAX}",
            )
    else:
        _add(details, "text_ref.type", "must be 'passage' or 'words'")

    return value


def _validate_started_at(value: object, details: ValidationDetails) -> None:
    if value is _MISSING:
        return
    if not isinstance(value, str) or not value:
        _add(details, "started_at", "must be a non-empty string")


def _validate_client(
    value: object,
    details: ValidationDetails,
) -> Mapping[str, Any] | None:
    if value is _MISSING:
        return None
    if not isinstance(value, Mapping):
        _add(details, "client", "must be a JSON object")
        return None

    for field in ("user_agent", "platform"):
        field_value = _required(value, field, details, path=f"client.{field}")
        if field_value is not _MISSING and not isinstance(field_value, str):
            _add(details, f"client.{field}", "must be a string")

    layout_hint = _required(
        value, "layout_hint", details, path="client.layout_hint"
    )
    if layout_hint is not _MISSING and (
        not isinstance(layout_hint, str) or layout_hint not in _LAYOUT_HINTS
    ):
        _add(
            details,
            "client.layout_hint",
            "must be one of 'qwerty', 'non-qwerty', 'unknown'",
        )

    return value


def _validate_ignored(
    value: object,
    details: ValidationDetails,
) -> dict[str, int]:
    if value is _MISSING:
        return {}
    if not isinstance(value, Mapping):
        _add(details, "ignored", "must be a JSON object")
        return {}

    counts: dict[str, int] = {}
    for field in _IGNORED_COUNTERS:
        count = _required(value, field, details, path=f"ignored.{field}")
        if count is _MISSING:
            continue
        if type(count) is not int or count < 0:
            _add(
                details,
                f"ignored.{field}",
                "must be a non-negative integer",
            )
            continue
        counts[field] = count
    return counts


def _validate_event(
    event: Mapping[str, Any],
    index: int,
    previous_t: object,
    details: ValidationDetails,
) -> object:
    """Validate one event and return the latest valid timestamp."""
    prefix = f"events[{index}]"

    seq = _required(event, "seq", details, path=f"{prefix}.seq")
    if seq is not _MISSING and type(seq) is not int:
        _add(details, f"{prefix}.seq", "must be an integer")
    elif seq is not _MISSING and seq != index:
        _add(details, f"{prefix}.seq", "must equal its array index")

    next_previous_t = previous_t
    t = _required(event, "t", details, path=f"{prefix}.t")
    if t is not _MISSING:
        if not _is_finite_number(t):
            _add(details, f"{prefix}.t", "must be a finite number >= 0")
        elif t < 0:
            _add(details, f"{prefix}.t", "must be a finite number >= 0")
        else:
            if (
                isinstance(previous_t, (int, float))
                and not isinstance(previous_t, bool)
                and t < previous_t
            ):
                _add(details, f"{prefix}.t", "must be non-decreasing")
            next_previous_t = t

    event_type = _required(event, "type", details, path=f"{prefix}.type")
    if event_type is not _MISSING and (
        not isinstance(event_type, str) or event_type not in _EVENT_TYPES
    ):
        _add(details, f"{prefix}.type", "must be 'down' or 'up'")

    code = _required(event, "code", details, path=f"{prefix}.code")
    if code is not _MISSING and (
        not isinstance(code, str) or CODE_PATTERN.fullmatch(code) is None
    ):
        _add(
            details,
            f"{prefix}.code",
            "must match [A-Za-z0-9]{1,32}",
        )

    key = _required(event, "key", details, path=f"{prefix}.key")
    repeat = _required(event, "repeat", details, path=f"{prefix}.repeat")
    repeat_is_bool = isinstance(repeat, bool)
    if repeat is not _MISSING and not repeat_is_bool:
        _add(details, f"{prefix}.repeat", "must be a boolean")

    if event_type == "down":
        if key is not _MISSING:
            key_is_valid = isinstance(key, str) and (
                key == "Backspace" or KEY_PATTERN.fullmatch(key) is not None
            )
            if not key_is_valid:
                _add(
                    details,
                    f"{prefix}.key",
                    "must be one printable ASCII character 32-126 "
                    "or 'Backspace'",
                )
            elif repeat is True:
                if key != "Backspace":
                    _add(
                        details,
                        f"{prefix}.repeat",
                        "must be false for printable keydowns",
                    )
    elif event_type == "up":
        if key is not _MISSING and key is not None:
            _add(details, f"{prefix}.key", "must be null for keyup")
        if repeat is True:
            _add(details, f"{prefix}.repeat", "must be false for keyup")

    return next_previous_t


def _validate_first_event(
    events: list[Any],
    details: ValidationDetails,
) -> None:
    """The first event must be a non-repeat printable keydown."""
    if not events or not isinstance(events[0], Mapping):
        return
    first = events[0]
    key = first.get("key")
    valid = (
        first.get("type") == "down"
        and first.get("repeat") is False
        and isinstance(key, str)
        and KEY_PATTERN.fullmatch(key) is not None
    )
    if not valid:
        _add(
            details,
            "events[0]",
            "must be a non-repeat printable keydown",
        )


def _validate_events(
    value: object,
    details: ValidationDetails,
) -> tuple[Mapping[str, Any], ...]:
    if value is _MISSING:
        return ()
    if not isinstance(value, list):
        _add(details, "events", "must be a JSON array")
        return ()

    if not MIN_SESSION_EVENTS <= len(value) <= MAX_SESSION_EVENTS:
        _add(
            details,
            "events",
            f"must contain between {MIN_SESSION_EVENTS} and "
            f"{MAX_SESSION_EVENTS} events",
        )

    previous_t: object = None
    for index, event in enumerate(value):
        if not isinstance(event, Mapping):
            _add(
                details,
                f"events[{index}]",
                "must be a JSON object",
            )
            continue
        previous_t = _validate_event(event, index, previous_t, details)

    _validate_first_event(value, details)
    return cast(tuple[Mapping[str, Any], ...], tuple(value))


def validate_session_payload(
    payload: object,
    *,
    body_size_bytes: int | None = None,
) -> ValidatedSessionPayload:
    """Validate one session payload and return its typed form.

    Args:
        payload: The decoded JSON value. It must be a JSON object.
        body_size_bytes: Optional raw request-body length. When supplied, a body
            larger than ``MAX_SESSION_BODY_BYTES`` raises
            :class:`PayloadTooLargeError` before field validation.

    Raises:
        PayloadTooLargeError: if the body exceeds the documented limit.
        ValidationError: if any field, event or sequence rule fails.
    """
    if body_size_bytes is not None:
        if body_size_bytes < 0:
            raise ValueError("body_size_bytes must not be negative")
        if body_size_bytes > MAX_SESSION_BODY_BYTES:
            raise PayloadTooLargeError(
                "Request body is too large.",
                [
                    {
                        "field": "body",
                        "problem": (
                            f"must not exceed {MAX_SESSION_BODY_BYTES} bytes"
                        ),
                    }
                ],
            )

    if not isinstance(payload, Mapping):
        raise ValidationError(
            "Request validation failed.",
            [{"field": "payload", "problem": "must be a JSON object"}],
        )

    details: ValidationDetails = []

    for field in _FORBIDDEN_FIELDS:
        if field in payload:
            _add(
                details,
                field,
                "is server-derived and must not be supplied",
            )

    schema_version = _required(payload, "schema_version", details)
    _validate_schema_version(schema_version, details)

    mode = _required(payload, "mode", details)
    _validate_mode(mode, details)

    duration_limit_ms = _required(payload, "duration_limit_ms", details)
    _validate_duration(mode, duration_limit_ms, details)

    text_ref_value = _required(payload, "text_ref", details)
    text_ref = _validate_text_ref(text_ref_value, details)

    started_at = _required(payload, "started_at", details)
    _validate_started_at(started_at, details)

    client_value = _required(payload, "client", details)
    client = _validate_client(client_value, details)

    ignored_value = _required(payload, "ignored", details)
    ignored = _validate_ignored(ignored_value, details)

    events_value = _required(payload, "events", details)
    events = _validate_events(events_value, details)

    if details:
        raise ValidationError("Request validation failed.", details)

    return ValidatedSessionPayload(
        schema_version=SUPPORTED_SCHEMA_VERSION,
        mode=cast(str, mode),
        duration_limit_ms=cast(int | None, duration_limit_ms),
        text_ref=cast(Mapping[str, Any], text_ref),
        started_at=cast(str, started_at),
        client=cast(Mapping[str, Any], client),
        ignored=ignored,
        events=events,
    )
