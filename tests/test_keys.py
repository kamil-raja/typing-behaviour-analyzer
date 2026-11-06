"""Key-map, Wilson-interval, classification and merge tests.

The reference values come from ``docs/METRICS.md`` §12 and blueprint §14.2
regression group 5. Focused tests cover the 95-character table, the Wilson
formula boundaries, the ``n = 19`` / ``n = 20`` gate, all three weak-key
conditions, the rule that dwell never changes the error class, and the merge of
the metric layer's character- and code-keyed maps.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.engine import analyze_session
from app.engine.keys import (
    AVERAGE,
    CHAR_TO_CODE,
    INSUFFICIENT,
    STRONG,
    WEAK,
    SessionKeyStat,
    classify_key,
    classify_key_stat,
    classify_observation,
    code_for_char,
    merge_session_key_stats,
    pooled_baseline_error_rate,
    wilson_ci,
)
from app.engine.metrics import (
    KeyDwellStats,
    KeyObservationStats,
    KeyStats,
    compute_key_stats,
)
from app.engine.replay import replay_events

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PRINTABLE_ASCII = {chr(code) for code in range(32, 127)}
CODE_PATTERN = r"[A-Za-z0-9]{1,32}"


def load_fixture(fixture_id: str) -> dict[str, Any]:
    """Load one golden fixture by its letter identifier."""
    path = FIXTURE_DIR / f"golden_{fixture_id.lower()}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def down(seq: int, t: float, key: str, code: str) -> dict[str, Any]:
    """Build a printable non-repeat keydown event."""
    return {
        "seq": seq,
        "type": "down",
        "t": t,
        "code": code,
        "key": key,
        "repeat": False,
    }


def up(seq: int, t: float, code: str) -> dict[str, Any]:
    """Build a keyup event."""
    return {
        "seq": seq,
        "type": "up",
        "t": t,
        "code": code,
        "key": None,
        "repeat": False,
    }


def backspace(seq: int, t: float) -> dict[str, Any]:
    """Build a non-repeat Backspace keydown event."""
    return {
        "seq": seq,
        "type": "down",
        "t": t,
        "code": "Backspace",
        "key": "Backspace",
        "repeat": False,
    }


# --- CHAR_TO_CODE ---------------------------------------------------------


def test_char_to_code_covers_every_printable_ascii_character() -> None:
    """The table covers exactly ASCII 32–126 with no extra entries."""
    assert set(CHAR_TO_CODE) == PRINTABLE_ASCII
    assert len(CHAR_TO_CODE) == 95


def test_every_key_code_is_a_valid_event_code() -> None:
    """All mapped values satisfy ``EVENT_SCHEMA.md``'s code rule."""
    for char, code in CHAR_TO_CODE.items():
        assert re.fullmatch(CODE_PATTERN, code), (char, code)


def test_letters_and_shifted_symbols_share_their_base_key() -> None:
    """Capitals and shifted symbols map to the unshifted physical key."""
    for letter in "abcdefghijklmnopqrstuvwxyz":
        assert CHAR_TO_CODE[letter] == CHAR_TO_CODE[letter.upper()]
        assert CHAR_TO_CODE[letter] == f"Key{letter.upper()}"

    shifted_pairs = [
        ("1", "!"),
        ("2", "@"),
        ("3", "#"),
        ("4", "$"),
        ("5", "%"),
        ("6", "^"),
        ("7", "&"),
        ("8", "*"),
        ("9", "("),
        ("0", ")"),
        ("`", "~"),
        ("-", "_"),
        ("=", "+"),
        ("[", "{"),
        ("]", "}"),
        ("\\", "|"),
        (";", ":"),
        ("'", '"'),
        (",", "<"),
        (".", ">"),
        ("/", "?"),
    ]
    for base, shifted in shifted_pairs:
        assert CHAR_TO_CODE[base] == CHAR_TO_CODE[shifted]


def test_space_and_punctuation_base_codes() -> None:
    """Spot-check the physical names for Space and punctuation."""
    assert CHAR_TO_CODE[" "] == "Space"
    assert CHAR_TO_CODE["`"] == "Backquote"
    assert CHAR_TO_CODE["-"] == "Minus"
    assert CHAR_TO_CODE["="] == "Equal"
    assert CHAR_TO_CODE["["] == "BracketLeft"
    assert CHAR_TO_CODE["]"] == "BracketRight"
    assert CHAR_TO_CODE["\\"] == "Backslash"
    assert CHAR_TO_CODE[";"] == "Semicolon"
    assert CHAR_TO_CODE["'"] == "Quote"
    assert CHAR_TO_CODE[","] == "Comma"
    assert CHAR_TO_CODE["."] == "Period"
    assert CHAR_TO_CODE["/"] == "Slash"


def test_code_for_char_rejects_non_printable_input() -> None:
    """Unmapped characters raise instead of being silently dropped."""
    for char in ("é", "ß", "\u00a0", "😀", "\n", "\x7f", "", "ab"):
        with pytest.raises(ValueError):
            code_for_char(char)


# --- Wilson interval ------------------------------------------------------


def test_wilson_reference_value_for_three_of_twenty() -> None:
    """Blueprint reference: Wilson(3, 20) ≈ [0.052, 0.360]."""
    lo, hi = wilson_ci(3, 20)

    assert f"{lo:.3f}" == "0.052"
    assert f"{hi:.3f}" == "0.360"
    assert lo < hi


def test_wilson_interval_stays_inside_zero_to_one() -> None:
    """Both boundaries and the full range remain valid probabilities."""
    for x, n in ((0, 1), (0, 20), (1, 20), (19, 20), (20, 20), (3, 20)):
        lo, hi = wilson_ci(x, n)
        assert 0.0 <= lo <= hi <= 1.0

    zero_lo, _ = wilson_ci(0, 20)
    _, full_hi = wilson_ci(20, 20)
    assert zero_lo == 0.0
    assert full_hi == 1.0


@pytest.mark.parametrize(
    ("x", "n", "z"),
    [
        (0, 0, 1.96),
        (-1, 20, 1.96),
        (21, 20, 1.96),
        (3, 20, 0.0),
        (3, 20, -1.96),
    ],
)
def test_wilson_rejects_invalid_inputs(x: int, n: int, z: float) -> None:
    """Invalid counts or z-values fail loudly."""
    with pytest.raises(ValueError):
        wilson_ci(x, n, z)


# --- Baseline -------------------------------------------------------------


def test_pooled_baseline_applies_the_one_percent_floor() -> None:
    """The pooled rate is never below 1 %."""
    assert pooled_baseline_error_rate(0, 100) == pytest.approx(0.01)
    assert pooled_baseline_error_rate(5, 100) == pytest.approx(0.05)
    assert pooled_baseline_error_rate(0, 0) is None


def test_pooled_baseline_rejects_invalid_totals() -> None:
    """Negative totals and more errors than observations are invalid."""
    with pytest.raises(ValueError):
        pooled_baseline_error_rate(-1, 10)
    with pytest.raises(ValueError):
        pooled_baseline_error_rate(2, -1)
    with pytest.raises(ValueError):
        pooled_baseline_error_rate(11, 10)


# --- Classification -------------------------------------------------------


def test_nineteen_observations_is_insufficient() -> None:
    """n = 19 is grey, even with the same error rate as the n = 20 case."""
    result = classify_observation(19, 3, 0.05)

    assert result.classification == INSUFFICIENT
    assert result.ci_low is None
    assert result.ci_high is None
    assert result.error_rate == pytest.approx(3 / 19)


def test_twenty_observations_is_classified() -> None:
    """n = 20 crosses the gate; 3/20 vs a 5 % baseline is weak."""
    result = classify_observation(20, 3, 0.05)

    assert result.classification == WEAK
    assert result.ci_low == pytest.approx(0.0524, abs=1e-4)
    assert result.ci_high == pytest.approx(0.3604, abs=1e-4)


def test_weak_requires_the_lower_bound_above_the_baseline() -> None:
    """lo > b is mandatory: e > b alone is only average."""
    # e = 0.15, b = 0.06, lo = 0.052: not weak, e > b so average.
    assert classify_key(0.15, 0.06, 0.052, 0.36, 5) == AVERAGE


def test_weak_requires_the_two_point_practical_margin() -> None:
    """e - b >= 0.02 is mandatory even when lo > b and x >= 3."""
    # e = 0.115, b = 0.10, margin = 0.015, lo = 0.105.
    assert classify_key(0.115, 0.10, 0.105, 0.20, 5) == AVERAGE


def test_exact_two_point_margin_is_weak() -> None:
    """The decimal boundary 0.02 survives binary floating-point subtraction."""
    assert classify_key(0.12, 0.10, 0.11, 0.20, 5) == WEAK


def test_weak_requires_at_least_three_errors() -> None:
    """x >= 3 is mandatory even when the interval and margin pass."""
    assert classify_key(0.15, 0.05, 0.06, 0.36, 2) == AVERAGE
    assert classify_key(0.15, 0.05, 0.06, 0.36, 3) == WEAK


def test_strong_and_average_follow_the_remaining_rules() -> None:
    """Strong is e <= b; average is every other non-weak case."""
    # Not weak (lo is not above b) and e <= b.
    assert classify_key(0.05, 0.05, 0.01, 0.10, 3) == STRONG
    # Not weak (lo is not above b) and e > b.
    assert classify_key(0.10, 0.05, 0.01, 0.20, 3) == AVERAGE


def test_missing_bounds_mean_insufficient() -> None:
    """A key without a Wilson interval is grey."""
    assert classify_key(0.0, 0.01, None, None, 0) == INSUFFICIENT


def test_classify_key_rejects_a_reversed_interval() -> None:
    """A malformed interval is a programming error, not a class."""
    with pytest.raises(ValueError):
        classify_key(0.1, 0.05, 0.3, 0.2, 5)


def test_long_dwell_never_changes_the_error_classification() -> None:
    """Dwell is informational and never enters the Wilson rules."""
    short_dwell = SessionKeyStat(
        key_code="KeyA",
        attempts=20,
        errors=6,
        dwell_count=20,
        dwell_sum_ms=1_000.0,
    )
    long_dwell = SessionKeyStat(
        key_code="KeyA",
        attempts=20,
        errors=6,
        dwell_count=20,
        dwell_sum_ms=20_000.0,
    )

    short_result = classify_key_stat(short_dwell, 0.05)
    long_result = classify_key_stat(long_dwell, 0.05)

    assert short_result.classification == WEAK
    assert long_result.classification == WEAK
    assert short_result == long_result


def test_classify_observation_validates_counts() -> None:
    """Negative counts and more errors than attempts are rejected."""
    with pytest.raises(ValueError):
        classify_observation(-1, 0, 0.01)
    with pytest.raises(ValueError):
        classify_observation(10, -1, 0.01)
    with pytest.raises(ValueError):
        classify_observation(10, 11, 0.01)


# --- Merge into session_key_stats ----------------------------------------


def test_merge_fixture_a_blames_the_expected_character() -> None:
    """Fixture A's wrong ``x`` is blamed on the expected ``a``, not KeyX."""
    fixture = load_fixture("A")
    analysis = analyze_session(
        text=fixture["text"],
        mode=fixture["mode"],
        duration_limit_ms=fixture["duration_limit_ms"],
        events=fixture["events"],
    )
    rows = analysis.session_key_stats

    assert set(rows) == {"KeyA", "KeyC", "KeyT"}
    assert "KeyX" not in rows

    assert rows["KeyC"].attempts == 1
    assert rows["KeyC"].errors == 0
    assert rows["KeyA"].attempts == 2
    assert rows["KeyA"].errors == 1
    assert rows["KeyT"].attempts == 1
    assert rows["KeyT"].errors == 0

    assert rows["KeyA"].dwell_count == 0
    assert rows["KeyA"].iki_count == 0


def test_merge_sums_observations_and_dwell_on_one_physical_key() -> None:
    """Capital/lowercase and character/code sources merge onto one row."""
    events = [
        down(0, 0, "A", "KeyA"),
        up(1, 100, "KeyA"),
        down(2, 200, "a", "KeyA"),
        up(3, 350, "KeyA"),
        backspace(4, 400),
        up(5, 1000, "Backspace"),
    ]
    analysis = analyze_session(
        text="Aaa",
        mode="passage",
        duration_limit_ms=None,
        events=events,
    )
    rows = analysis.session_key_stats

    key_a = rows["KeyA"]
    assert key_a.attempts == 2
    assert key_a.errors == 0
    assert key_a.dwell_count == 2
    assert key_a.dwell_sum_ms == pytest.approx(250.0)
    assert key_a.iki_count == 1
    assert key_a.iki_sum_ms == pytest.approx(200.0)
    assert key_a.mean_dwell_ms == pytest.approx(125.0)
    assert key_a.mean_iki_ms == pytest.approx(200.0)

    backspace_row = rows["Backspace"]
    assert backspace_row.attempts == 0
    assert backspace_row.errors == 0
    assert backspace_row.dwell_count == 1
    assert backspace_row.dwell_sum_ms == pytest.approx(600.0)
    assert backspace_row.iki_count == 0


def test_merge_sums_characters_that_share_a_shifted_key() -> None:
    """``1`` and ``!`` both contribute to Digit1."""
    key_stats = KeyStats(
        observations_by_char={
            "1": KeyObservationStats(
                attempts=2,
                errors=1,
                iki_count=1,
                iki_sum_ms=100.0,
            ),
            "!": KeyObservationStats(
                attempts=2,
                errors=1,
                iki_count=1,
                iki_sum_ms=200.0,
            ),
        },
        dwell_by_code={
            "Digit1": KeyDwellStats(dwell_count=3, dwell_sum_ms=300.0),
        },
    )
    rows = merge_session_key_stats(key_stats)
    digit_one = rows["Digit1"]

    assert digit_one.attempts == 4
    assert digit_one.errors == 2
    assert digit_one.dwell_count == 3
    assert digit_one.dwell_sum_ms == pytest.approx(300.0)
    assert digit_one.iki_count == 2
    assert digit_one.iki_sum_ms == pytest.approx(300.0)


def test_merge_returns_sorted_keys_and_includes_dwell_only_codes() -> None:
    """Rows are ordered by key code and union both attribution sources."""
    key_stats = KeyStats(
        observations_by_char={
            "t": KeyObservationStats(attempts=1),
            "a": KeyObservationStats(attempts=1),
        },
        dwell_by_code={
            "KeyT": KeyDwellStats(dwell_count=1, dwell_sum_ms=90.0),
            "Backspace": KeyDwellStats(dwell_count=1, dwell_sum_ms=110.0),
        },
    )
    rows = merge_session_key_stats(key_stats)

    assert list(rows) == sorted(rows)
    assert list(rows) == ["Backspace", "KeyA", "KeyT"]
    assert rows["Backspace"].attempts == 0
    assert rows["Backspace"].dwell_sum_ms == pytest.approx(110.0)


def test_merge_of_an_empty_session_is_empty() -> None:
    """A session with no keystrokes produces no per-key rows."""
    replay = replay_events("a", "time", 1_000, [])
    assert merge_session_key_stats(compute_key_stats(replay)) == {}


def test_merge_raises_for_an_unmapped_expected_character() -> None:
    """The engine never silently drops a non-ASCII expected character."""
    key_stats = KeyStats(
        observations_by_char={
            "é": KeyObservationStats(attempts=1, errors=0),
        },
        dwell_by_code={},
    )

    with pytest.raises(ValueError):
        merge_session_key_stats(key_stats)


def test_session_key_stat_properties_handle_empty_samples() -> None:
    """Means are ``None`` rather than zero when there is no sample."""
    row = SessionKeyStat(key_code="KeyA")

    assert row.error_rate is None
    assert row.mean_dwell_ms is None
    assert row.mean_iki_ms is None


def test_analyze_session_exposes_raw_and_merged_key_stats() -> None:
    """The entry point keeps both the source maps and the merged rows."""
    fixture = load_fixture("D")
    analysis = analyze_session(
        text=fixture["text"],
        mode=fixture["mode"],
        duration_limit_ms=fixture["duration_limit_ms"],
        events=fixture["events"],
    )

    assert analysis.key_stats.observations_by_char["t"].attempts == 2
    assert analysis.session_key_stats["KeyT"].attempts == 2
    assert analysis.session_key_stats["KeyT"].errors == 1
