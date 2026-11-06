"""Validator tests for the session payload and its event stream.

The cases follow ``docs/EVENT_SCHEMA.md`` §3, §6 and §7 and the P0-D1-06 list in
``docs/TASKS.md``. They cover the ASCII pitfalls, enums, required fields,
sequence integrity, payload limits, the forbidden server-derived fields and the
timer-boundary division of responsibility between validation and replay.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from app.config import (
    MAX_SESSION_BODY_BYTES,
    MAX_SESSION_EVENTS,
    MIN_SESSION_EVENTS,
)
from app.engine.replay import replay_events
from app.errors import PAYLOAD_TOO_LARGE, VALIDATION_ERROR
from app.validators import (
    PayloadTooLargeError,
    ValidationError,
    validate_session_payload,
)


def down(
    seq: int,
    t: float | int,
    key: str = "a",
    code: str = "KeyA",
    repeat: bool = False,
) -> dict[str, Any]:
    """Build a printable keydown event."""
    return {
        "seq": seq,
        "type": "down",
        "t": t,
        "code": code,
        "key": key,
        "repeat": repeat,
    }


def up(
    seq: int,
    t: float | int,
    code: str = "KeyA",
    repeat: bool = False,
) -> dict[str, Any]:
    """Build a keyup event."""
    return {
        "seq": seq,
        "type": "up",
        "t": t,
        "code": code,
        "key": None,
        "repeat": repeat,
    }


def backspace_down(seq: int, t: float | int, repeat: bool = False) -> dict[str, Any]:
    """Build a Backspace keydown event."""
    return {
        "seq": seq,
        "type": "down",
        "t": t,
        "code": "Backspace",
        "key": "Backspace",
        "repeat": repeat,
    }


def valid_payload(**overrides: Any) -> dict[str, Any]:
    """Return a minimal structurally valid time-mode payload."""
    payload: dict[str, Any] = {
        "schema_version": 1,
        "mode": "time",
        "duration_limit_ms": 15_000,
        "text_ref": {"type": "words", "seed": 482_913, "count": 50},
        "started_at": "2026-11-06T10:05:00.000Z",
        "client": {
            "user_agent": "pytest",
            "platform": "Win32",
            "layout_hint": "qwerty",
        },
        "ignored": {
            "repeat_keydowns": 0,
            "shortcuts": 0,
            "unsupported_keys": 0,
            "unsupported_chars": 0,
            "paste_attempts": 0,
        },
        "events": [
            down(0, 0.0),
            up(1, 100.0),
        ],
    }
    payload.update(overrides)
    return payload


def payload_with_events(*events: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Return a valid payload with a supplied event list."""
    return valid_payload(events=list(events), **overrides)


def assert_field(error: ValidationError, field: str) -> dict[str, str]:
    """Assert one detail exists for ``field`` and return it."""
    matches = [detail for detail in error.details if detail["field"] == field]
    assert matches, f"no detail for {field!r}: {error.details!r}"
    return matches[0]


def assert_problem(error: ValidationError, field: str, fragment: str) -> None:
    """Assert the field's problem text contains ``fragment``."""
    detail = assert_field(error, field)
    assert fragment in detail["problem"]


# --- Valid payloads -------------------------------------------------------


def test_valid_time_payload_is_returned_as_typed_values() -> None:
    """A conforming payload is accepted and exposed in typed form."""
    validated = validate_session_payload(valid_payload())

    assert validated.schema_version == 1
    assert validated.mode == "time"
    assert validated.duration_limit_ms == 15_000
    assert validated.text_ref["type"] == "words"
    assert validated.started_at == "2026-11-06T10:05:00.000Z"
    assert validated.client["layout_hint"] == "qwerty"
    assert validated.ignored["shortcuts"] == 0
    assert len(validated.events) == 2
    assert validated.events[0]["key"] == "a"


def test_valid_passage_payload_is_accepted() -> None:
    """Passage mode requires a null duration and a passage id."""
    validated = validate_session_payload(
        valid_payload(
            mode="passage",
            duration_limit_ms=None,
            text_ref={"type": "passage", "id": "p_003"},
        )
    )

    assert validated.mode == "passage"
    assert validated.duration_limit_ms is None
    assert validated.text_ref["id"] == "p_003"


@pytest.mark.parametrize("limit", [15_000, 30_000, 60_000])
def test_all_documented_time_limits_are_accepted(limit: int) -> None:
    """The three documented time-mode durations are valid."""
    validated = validate_session_payload(
        valid_payload(duration_limit_ms=limit)
    )
    assert validated.duration_limit_ms == limit


@pytest.mark.parametrize("layout_hint", ["qwerty", "non-qwerty", "unknown"])
def test_all_documented_layout_hints_are_accepted(layout_hint: str) -> None:
    """All documented layout hints are valid."""
    payload = valid_payload()
    payload["client"]["layout_hint"] = layout_hint

    validate_session_payload(payload)


def test_unknown_top_level_fields_are_allowed() -> None:
    """Forward-compatible extra fields are ignored, per ADR-026."""
    validated = validate_session_payload(valid_payload(future_field="ignored"))
    assert validated.mode == "time"


# --- Request size and top-level shape ------------------------------------


def test_body_at_the_limit_is_accepted() -> None:
    """Exactly 2 MiB is allowed."""
    validate_session_payload(
        valid_payload(),
        body_size_bytes=MAX_SESSION_BODY_BYTES,
    )


def test_oversized_body_raises_payload_too_large() -> None:
    """One byte over the limit is a 413 PAYLOAD_TOO_LARGE error."""
    with pytest.raises(PayloadTooLargeError) as info:
        validate_session_payload(
            valid_payload(),
            body_size_bytes=MAX_SESSION_BODY_BYTES + 1,
        )

    error = info.value
    assert isinstance(error, ValidationError)
    assert error.code == PAYLOAD_TOO_LARGE
    assert error.status == 413
    assert_field(error, "body")


def test_negative_body_size_is_a_programming_error() -> None:
    """A negative body size is not a client validation problem."""
    with pytest.raises(ValueError):
        validate_session_payload(valid_payload(), body_size_bytes=-1)


@pytest.mark.parametrize("payload", [None, [], "text", 1, True])
def test_payload_must_be_a_json_object(payload: object) -> None:
    """Non-object JSON values are rejected."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(payload)

    assert info.value.code == VALIDATION_ERROR
    assert info.value.status == 422
    assert_field(info.value, "payload")


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "mode",
        "duration_limit_ms",
        "text_ref",
        "started_at",
        "client",
        "ignored",
        "events",
    ],
)
def test_every_required_top_level_field_is_enforced(field: str) -> None:
    """Removing any required field produces a detail for that field."""
    payload = valid_payload()
    del payload[field]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(payload)

    assert_problem(info.value, field, "required")


# --- Scalar enums and types ----------------------------------------------


@pytest.mark.parametrize("value", [0, 2, "1", 1.0, True, None])
def test_schema_version_must_be_the_integer_one(value: object) -> None:
    """Only integer 1 is accepted; booleans and floats are not integers."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(schema_version=value))

    assert_field(info.value, "schema_version")


@pytest.mark.parametrize("value", ["", "speed", 1, None])
def test_mode_must_be_time_or_passage(value: object) -> None:
    """Unknown modes are rejected."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(mode=value))

    assert_field(info.value, "mode")


@pytest.mark.parametrize(
    ("mode", "duration"),
    [
        ("time", None),
        ("time", 20_000),
        ("time", "30000"),
        ("time", True),
        ("passage", 15_000),
        ("passage", 0),
    ],
)
def test_duration_must_match_the_mode(mode: str, duration: object) -> None:
    """Time mode has a fixed set; passage mode requires null."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(
            valid_payload(mode=mode, duration_limit_ms=duration)
        )

    assert_field(info.value, "duration_limit_ms")


@pytest.mark.parametrize("value", [None, 1, ""])
def test_started_at_must_be_a_non_empty_string(value: object) -> None:
    """``started_at`` is required and informational, but not empty."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(started_at=value))

    assert_field(info.value, "started_at")


# --- text_ref -------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "p_003", [], 1])
def test_text_ref_must_be_an_object(value: object) -> None:
    """``text_ref`` is a discriminated object."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(text_ref=value))

    assert_field(info.value, "text_ref")


def test_text_ref_requires_a_type() -> None:
    """A missing discriminator is rejected."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(text_ref={"id": "p_003"}))

    assert_problem(info.value, "text_ref.type", "required")


@pytest.mark.parametrize("ref_type", ["unknown", "", 1, None])
def test_text_ref_type_must_be_passage_or_words(ref_type: object) -> None:
    """Unknown text-ref types are rejected."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(text_ref={"type": ref_type}))

    assert_field(info.value, "text_ref.type")


@pytest.mark.parametrize("value", [None, "", 1])
def test_passage_id_must_be_a_non_empty_string(value: object) -> None:
    """Passage references require a non-empty id."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(
            valid_payload(text_ref={"type": "passage", "id": value})
        )

    assert_field(info.value, "text_ref.id")


def test_passage_reference_missing_id_is_rejected() -> None:
    """A missing passage id is a required-field error."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(text_ref={"type": "passage"}))

    assert_problem(info.value, "text_ref.id", "required")


@pytest.mark.parametrize("value", [None, "1", 1.0, True])
def test_word_seed_must_be_an_integer(value: object) -> None:
    """Word mode requires an integer seed."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(
            valid_payload(
                text_ref={"type": "words", "seed": value, "count": 50}
            )
        )

    assert_field(info.value, "text_ref.seed")


@pytest.mark.parametrize("value", [9, 401, None, "50", 50.0, True])
def test_word_count_must_be_an_integer_in_range(value: object) -> None:
    """Word count is restricted to the documented 10..400 range."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(
            valid_payload(
                text_ref={"type": "words", "seed": 1, "count": value}
            )
        )

    assert_field(info.value, "text_ref.count")


@pytest.mark.parametrize("count", [10, 400])
def test_word_count_range_boundaries_are_inclusive(count: int) -> None:
    """10 and 400 are both accepted."""
    validate_session_payload(
        valid_payload(
            text_ref={"type": "words", "seed": 1, "count": count}
        )
    )


# --- client and ignored ---------------------------------------------------


@pytest.mark.parametrize("value", [None, "client", [], 1])
def test_client_must_be_an_object(value: object) -> None:
    """``client`` is a required object."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(client=value))

    assert_field(info.value, "client")


@pytest.mark.parametrize("field", ["user_agent", "platform", "layout_hint"])
def test_required_client_fields_are_enforced(field: str) -> None:
    """Each documented client field is required."""
    payload = valid_payload()
    del payload["client"][field]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(payload)

    assert_problem(info.value, f"client.{field}", "required")


@pytest.mark.parametrize("field", ["user_agent", "platform"])
def test_client_string_fields_must_be_strings(field: str) -> None:
    """User agent and platform are strings."""
    payload = valid_payload()
    payload["client"][field] = 1

    with pytest.raises(ValidationError) as info:
        validate_session_payload(payload)

    assert_field(info.value, f"client.{field}")


@pytest.mark.parametrize("value", ["", "AZERTY", 1, None])
def test_layout_hint_must_be_a_documented_enum(value: object) -> None:
    """Only the three documented layout hints are accepted."""
    payload = valid_payload()
    payload["client"]["layout_hint"] = value

    with pytest.raises(ValidationError) as info:
        validate_session_payload(payload)

    assert_field(info.value, "client.layout_hint")


@pytest.mark.parametrize("value", [None, [], "ignored", 1])
def test_ignored_must_be_an_object(value: object) -> None:
    """``ignored`` is a required object."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(ignored=value))

    assert_field(info.value, "ignored")


@pytest.mark.parametrize(
    "field",
    [
        "repeat_keydowns",
        "shortcuts",
        "unsupported_keys",
        "unsupported_chars",
        "paste_attempts",
    ],
)
def test_every_ignored_counter_is_required(field: str) -> None:
    """All five ignored counters are part of the payload."""
    payload = valid_payload()
    del payload["ignored"][field]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(payload)

    assert_problem(info.value, f"ignored.{field}", "required")


@pytest.mark.parametrize("value", [-1, 1.5, "1", True, None])
def test_ignored_counters_are_non_negative_integers(value: object) -> None:
    """Counters cannot be negative, fractional or boolean."""
    payload = valid_payload()
    payload["ignored"]["shortcuts"] = value

    with pytest.raises(ValidationError) as info:
        validate_session_payload(payload)

    assert_field(info.value, "ignored.shortcuts")


# --- Event-list shape and limits -----------------------------------------


@pytest.mark.parametrize("value", [None, {}, "events", 1])
def test_events_must_be_an_array(value: object) -> None:
    """``events`` must be a JSON array."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=value))

    assert_field(info.value, "events")


@pytest.mark.parametrize(
    "events",
    [
        [],
        [down(0, 0)],
    ],
)
def test_event_count_lower_bound(events: list[dict[str, Any]]) -> None:
    """At least two events are required."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_problem(info.value, "events", str(MIN_SESSION_EVENTS))


def test_maximum_event_count_is_accepted() -> None:
    """10 000 structurally valid events are allowed."""
    events = [down(index, index) for index in range(MAX_SESSION_EVENTS)]
    validated = validate_session_payload(valid_payload(events=events))

    assert len(validated.events) == MAX_SESSION_EVENTS


def test_oversized_event_list_is_rejected() -> None:
    """10 001 events exceed the documented maximum."""
    events = [down(index, index) for index in range(MAX_SESSION_EVENTS + 1)]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_problem(info.value, "events", str(MAX_SESSION_EVENTS))


def test_non_object_event_is_rejected() -> None:
    """Every event must be a JSON object."""
    events = [down(0, 0), "up"]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_field(info.value, "events[1]")


# --- Event fields ---------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    ["seq", "type", "t", "code", "key", "repeat"],
)
def test_every_required_event_field_is_enforced(field: str) -> None:
    """Removing an event field produces a detail for that field."""
    events = [down(0, 0), up(1, 100)]
    del events[0][field]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_problem(info.value, f"events[0].{field}", "required")


@pytest.mark.parametrize(
    "events",
    [
        [down(1, 0), up(2, 100)],
        [down(0, 0), up(2, 100)],
        [down(0, 0), up(0, 100)],
    ],
)
def test_seq_must_start_at_zero_and_be_contiguous(
    events: list[dict[str, Any]],
) -> None:
    """A gap, offset or duplicate seq is rejected."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert any(
        detail["field"].endswith(".seq") for detail in info.value.details
    )


@pytest.mark.parametrize("value", ["0", 0.0, True, None])
def test_seq_must_be_an_integer(value: object) -> None:
    """Non-integer seq values are rejected."""
    events = [down(0, 0), up(1, 100)]
    events[1]["seq"] = value

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_field(info.value, "events[1].seq")


@pytest.mark.parametrize(
    "value",
    [
        -1,
        "0",
        True,
        None,
        float("nan"),
        float("inf"),
        float("-inf"),
        10**400,
    ],
)
def test_t_must_be_a_finite_non_negative_number(value: object) -> None:
    """Boolean, non-numeric, negative, NaN and infinite timestamps fail."""
    events = [down(0, value), up(1, 100)]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_field(info.value, "events[0].t")


def test_t_must_be_non_decreasing() -> None:
    """A decreasing timestamp is rejected."""
    events = [down(0, 100), up(1, 50)]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_problem(info.value, "events[1].t", "non-decreasing")


def test_equal_consecutive_timestamps_are_allowed() -> None:
    """Non-decreasing permits zero intervals."""
    validated = validate_session_payload(
        valid_payload(events=[down(0, 100), up(1, 100)])
    )
    assert len(validated.events) == 2


@pytest.mark.parametrize("value", ["press", "", 1, None])
def test_event_type_must_be_down_or_up(value: object) -> None:
    """Only the two documented event types are accepted."""
    events = [down(0, 0), up(1, 100)]
    events[1]["type"] = value

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_field(info.value, "events[1].type")


@pytest.mark.parametrize(
    "code",
    [
        "KeyÉ",
        "KeyA\n",
        "٣",
        "",
        "has-dash",
        "has space",
        "A" * 33,
        None,
        1,
    ],
)
def test_code_must_be_ascii_alphanumeric(code: object) -> None:
    """The code regex is ASCII-only and length-bounded."""
    events = [down(0, 0), up(1, 100)]
    events[1]["code"] = code

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_field(info.value, "events[1].code")


@pytest.mark.parametrize("code", ["Backspace", "KeyA", "1", "a", "A" * 32])
def test_valid_code_values_are_accepted(code: str) -> None:
    """ASCII alphanumeric codes of 1–32 characters are valid."""
    events = [down(0, 0), up(1, 100, code=code)]
    validate_session_payload(valid_payload(events=events))


@pytest.mark.parametrize(
    "key",
    [
        "é",
        "ß",
        "\u00a0",
        "😀",
        "\n",
        "\x7f",
        "Dead",
        "",
        "ab",
        "Space",
        None,
        1,
    ],
)
def test_key_must_be_printable_ascii_or_backspace(key: object) -> None:
    """Non-ASCII, multi-character and control keys are rejected."""
    events = [down(0, 0, key=key), up(1, 100)]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_field(info.value, "events[0].key")


@pytest.mark.parametrize("key", [" ", "~", "Backspace"])
def test_printable_ascii_and_backspace_keys_are_accepted(key: str) -> None:
    """Space and tilde are valid; Backspace is valid outside first position."""
    if key == "Backspace":
        events = [
            down(0, 0),
            up(1, 100),
            backspace_down(2, 200),
            up(3, 300, code="Backspace"),
        ]
    else:
        events = [down(0, 0, key=key), up(1, 100)]

    validate_session_payload(valid_payload(events=events))


@pytest.mark.parametrize("key", ["", "a", "Backspace", 0, 1])
def test_up_key_must_be_null(key: object) -> None:
    """Keyup events never carry a key value."""
    events = [down(0, 0), up(1, 100)]
    events[1]["key"] = key

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_field(info.value, "events[1].key")


@pytest.mark.parametrize("value", ["false", 1, 0, None])
def test_repeat_must_be_a_boolean(value: object) -> None:
    """Integer 0/1 and strings are not booleans."""
    events = [down(0, 0), up(1, 100)]
    events[1]["repeat"] = value

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_field(info.value, "events[1].repeat")


def test_repeat_printable_keydown_is_rejected() -> None:
    """A repeated printable down is never a valid keystroke."""
    events = [down(0, 0), up(1, 100), down(2, 200, repeat=True)]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_problem(info.value, "events[2].repeat", "printable")


def test_repeat_backspace_down_is_structurally_valid() -> None:
    """Backspace repeats belong to replay, not schema rejection."""
    events = [
        down(0, 0),
        up(1, 100),
        backspace_down(2, 200),
        backspace_down(3, 300, repeat=True),
        up(4, 400, code="Backspace"),
    ]
    validate_session_payload(valid_payload(events=events))


def test_repeat_up_is_rejected() -> None:
    """Repeat is only meaningful for a Backspace keydown."""
    events = [down(0, 0), up(1, 100, repeat=True)]

    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_problem(info.value, "events[1].repeat", "keyup")


# --- First event ----------------------------------------------------------


@pytest.mark.parametrize(
    "events",
    [
        [up(0, 0), down(1, 100)],
        [down(0, 0, repeat=True), up(1, 100)],
        [backspace_down(0, 0), up(1, 100, code="Backspace")],
        [down(0, 0, key="é"), up(1, 100)],
    ],
)
def test_first_event_must_be_a_non_repeat_printable_down(
    events: list[dict[str, Any]],
) -> None:
    """The session starts only on an accepted printable keydown."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(events=events))

    assert_field(info.value, "events[0]")


# --- Forbidden server-derived fields -------------------------------------


@pytest.mark.parametrize("field", ["ended_at_ms", "end_reason"])
@pytest.mark.parametrize("value", [None, 0, "completed"])
def test_client_supplied_end_fields_are_rejected(
    field: str, value: object
) -> None:
    """ended_at_ms and end_reason are server-derived only (ADR-025)."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(valid_payload(**{field: value}))

    assert_problem(info.value, field, "server-derived")


def test_both_forbidden_fields_are_reported_together() -> None:
    """Validation aggregates every offending top-level field."""
    with pytest.raises(ValidationError) as info:
        validate_session_payload(
            valid_payload(ended_at_ms=15000, end_reason="completed")
        )

    assert_field(info.value, "ended_at_ms")
    assert_field(info.value, "end_reason")


# --- Timer boundary belongs to replay ------------------------------------


@pytest.mark.parametrize("final_t", [15_000, 20_000])
def test_events_at_or_after_the_limit_are_structurally_valid(
    final_t: int,
) -> None:
    """ADR-026: the validator does not reject a timer-boundary event."""
    events = [
        down(0, 0),
        up(1, 100),
        down(2, final_t),
    ]
    validated = validate_session_payload(
        valid_payload(events=events, duration_limit_ms=15_000)
    )
    assert len(validated.events) == 3


@pytest.mark.parametrize("final_t", [15_000, 20_000])
def test_replay_excludes_events_at_or_after_the_limit(final_t: int) -> None:
    """Timer expiry wins: the boundary event is dropped, not a keystroke."""
    events = [
        down(0, 0),
        up(1, 100),
        down(2, final_t),
    ]
    validated = validate_session_payload(
        valid_payload(events=events, duration_limit_ms=15_000)
    )

    replay = replay_events(
        text="a" * 100,
        mode=validated.mode,
        duration_limit_ms=validated.duration_limit_ms,
        events=validated.events,
    )

    assert replay.end_reason == "time_up"
    assert replay.active_duration_ms == 15_000
    assert replay.K == 1
    assert replay.dropped_after_end == 1


def test_completion_at_the_exact_limit_resolves_as_time_up() -> None:
    """A completing keystroke at the limit is not accepted (regression 2)."""
    events = [
        down(0, 0),
        down(1, 15_000),
    ]
    validated = validate_session_payload(
        valid_payload(events=events, duration_limit_ms=15_000)
    )

    replay = replay_events(
        text="aa",
        mode=validated.mode,
        duration_limit_ms=validated.duration_limit_ms,
        events=validated.events,
    )

    assert replay.end_reason == "time_up"
    assert replay.N == 1
    assert replay.dropped_after_end == 1


def test_math_nan_is_not_accepted_as_a_timestamp() -> None:
    """A direct NaN value is rejected even though JSON normally forbids it."""
    assert math.isnan(float("nan"))

    with pytest.raises(ValidationError):
        validate_session_payload(
            valid_payload(events=[down(0, float("nan")), up(1, 100)])
        )
