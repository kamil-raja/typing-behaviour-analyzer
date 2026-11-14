"""Metric-layer tests against the golden fixtures and the formula edge cases.

The fixtures are the hand-computed examples in ``docs/METRICS.md`` §13. Every
replayable fixture is checked against its expected speed, accuracy, interval and
pause values, and the global invariants. Focused tests cover the rules that the
fixtures do not exercise: interval boundaries, IKI sample-size gates, the
zero-mean CV guard, consistency at 29 vs 30 intervals, dwell validity, and
per-key clean transitions.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from app.engine import SessionAnalysis, analyze_session
from app.engine.metrics import (
    KeyStats,
    SessionMetrics,
    coefficient_of_variation,
    compute_intervals,
    compute_key_stats,
    compute_metrics,
    is_pause,
    is_valid_dwell,
    is_valid_interval,
    trailing_moving_average,
    valid_intervals,
)
from app.engine.replay import ReplayResult, replay_events

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REPLAYABLE_FIXTURES = tuple("ABCDFG")
ALL_FIXTURES = tuple("ABCDEFG")

# The fixture display value for 2/3 is 66.7 (one decimal place), while the
# stored value is the unrounded formula result. Accuracy comparisons therefore
# round to one decimal place for display, per the author's decision.
ACCURACY_DISPLAY_DP = 1


def load_fixture(fixture_id: str) -> dict[str, Any]:
    """Load one golden fixture by its letter identifier."""
    path = FIXTURE_DIR / f"golden_{fixture_id.lower()}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def replay_fixture(fixture_id: str) -> ReplayResult:
    """Replay one golden fixture through the engine."""
    fixture = load_fixture(fixture_id)
    return replay_events(
        text=fixture["text"],
        mode=fixture["mode"],
        duration_limit_ms=fixture["duration_limit_ms"],
        events=fixture["events"],
    )


def metrics_for(
    events: list[dict[str, Any]],
    *,
    text: str = "a" * 100,
    mode: str = "time",
    duration_limit_ms: float | None = 10_000,
) -> tuple[ReplayResult, SessionMetrics]:
    """Replay a synthetic event list and compute its metrics."""
    replay = replay_events(text, mode, duration_limit_ms, events)
    return replay, compute_metrics(replay)


def key_stats_for(
    events: list[dict[str, Any]],
    *,
    text: str = "a" * 100,
    mode: str = "time",
    duration_limit_ms: float | None = 10_000,
) -> KeyStats:
    """Replay a synthetic event list and compute its per-key sums."""
    replay = replay_events(text, mode, duration_limit_ms, events)
    return compute_key_stats(replay)


def down(seq: int, t: float, key: str = "a", code: str = "KeyA") -> dict[str, Any]:
    """Build a printable non-repeat keydown event."""
    return {
        "seq": seq,
        "type": "down",
        "t": t,
        "code": code,
        "key": key,
        "repeat": False,
    }


def up(seq: int, t: float, code: str = "KeyA") -> dict[str, Any]:
    """Build a keyup event (``key`` is always null)."""
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


def assert_metric_invariants(replay: ReplayResult, metrics: SessionMetrics) -> None:
    """Assert the invariants required on every fixture."""
    assert replay.E == replay.U + replay.Ec + replay.Eu
    assert replay.K == replay.C + replay.E
    assert replay.N <= replay.K
    assert metrics.incorrect_keystrokes == (
        metrics.uncorrected_errors
        + metrics.corrected_errors
        + metrics.erased_unresolved_errors
    )
    if metrics.gross_wpm is not None and metrics.net_wpm is not None:
        assert metrics.net_wpm <= metrics.gross_wpm


# Expected interval classifications, hand-computed from each fixture's timed
# actions (``docs/METRICS.md`` §13).
EXPECTED_INTERVALS: dict[str, dict[str, Any]] = {
    "A": {
        "intervals": [800, 800, 800, 3600],
        "valid": [800, 800, 800],
        "pause_count": 1,
        "total_pause_ms": 3600,
        "longest_pause_ms": 3600,
        "zero_interval_count": 0,
    },
    "B": {
        "intervals": [800, 800],
        "valid": [800, 800],
        "pause_count": 0,
        "total_pause_ms": 0,
        "longest_pause_ms": None,
        "zero_interval_count": 0,
    },
    "C": {
        "intervals": [800, 800],
        "valid": [800, 800],
        "pause_count": 0,
        "total_pause_ms": 0,
        "longest_pause_ms": None,
        "zero_interval_count": 0,
    },
    "D": {
        "intervals": [800, 800, 800, 800],
        "valid": [800, 800, 800, 800],
        "pause_count": 0,
        "total_pause_ms": 0,
        "longest_pause_ms": None,
        "zero_interval_count": 0,
    },
    "E": {
        "intervals": [800, 800],
        "valid": [800, 800],
        "pause_count": 0,
        "total_pause_ms": 0,
        "longest_pause_ms": None,
        "zero_interval_count": 0,
    },
    "F": {
        "intervals": [800, 800],
        "valid": [800, 800],
        "pause_count": 0,
        "total_pause_ms": 0,
        "longest_pause_ms": None,
        "zero_interval_count": 0,
    },
    "G": {
        "intervals": [100, 100, 800],
        "valid": [100, 100, 800],
        "pause_count": 0,
        "total_pause_ms": 0,
        "longest_pause_ms": None,
        "zero_interval_count": 0,
    },
}


@pytest.mark.parametrize("fixture_id", ALL_FIXTURES)
def test_fixtures_hold_the_required_metric_invariants(fixture_id: str) -> None:
    """Every golden fixture satisfies the global metric invariants."""
    replay = replay_fixture(fixture_id)
    assert_metric_invariants(replay, compute_metrics(replay))


@pytest.mark.parametrize("fixture_id", ALL_FIXTURES)
def test_net_wpm_never_exceeds_gross_wpm(fixture_id: str) -> None:
    """Net WPM <= Gross WPM on every fixture, including the incomplete run."""
    metrics = compute_metrics(replay_fixture(fixture_id))

    assert metrics.gross_wpm is not None
    assert metrics.net_wpm is not None
    assert metrics.net_wpm <= metrics.gross_wpm


@pytest.mark.parametrize("fixture_id", REPLAYABLE_FIXTURES)
def test_golden_fixture_metric_values(fixture_id: str) -> None:
    """Each replayable fixture matches its hand-computed metric values."""
    fixture = load_fixture(fixture_id)
    expected = fixture["expected"]
    replay = replay_fixture(fixture_id)
    metrics = compute_metrics(replay)

    assert metrics.total_keystrokes == expected["K"]
    assert metrics.correct_keystrokes == expected["C"]
    assert metrics.incorrect_keystrokes == expected["E"]
    assert metrics.final_length == expected["N"]
    assert metrics.uncorrected_errors == expected["U"]
    assert metrics.corrected_errors == expected["corrected_errors"]
    assert metrics.erased_unresolved_errors == expected["erased_unresolved_errors"]

    if "backspace_deletions" in expected:
        assert metrics.backspace_count == expected["backspace_deletions"]
    if "backspace_presses" in expected:
        assert metrics.backspace_presses == expected["backspace_presses"]

    if "gross_wpm" in expected:
        assert metrics.gross_wpm == pytest.approx(expected["gross_wpm"])
    if "net_wpm" in expected:
        assert metrics.net_wpm == pytest.approx(expected["net_wpm"])
    if "accuracy_pct" in expected:
        assert round(metrics.accuracy_pct, ACCURACY_DISPLAY_DP) == expected[
            "accuracy_pct"
        ]
    if "avg_iki_ms" in expected:
        if expected["avg_iki_ms"] is None:
            assert metrics.avg_iki_ms is None
        else:
            assert metrics.avg_iki_ms == pytest.approx(expected["avg_iki_ms"])
    if "iki_sd_ms" in expected:
        if expected["iki_sd_ms"] is None:
            assert metrics.iki_sd_ms is None
        else:
            assert metrics.iki_sd_ms == pytest.approx(expected["iki_sd_ms"])
    if "pause_count" in expected:
        assert metrics.pause_count == expected["pause_count"]
    if "total_pause_ms" in expected:
        assert metrics.total_pause_ms == pytest.approx(expected["total_pause_ms"])

    assert_metric_invariants(replay, metrics)


@pytest.mark.parametrize("fixture_id", ALL_FIXTURES)
def test_accuracy_formulas_follow_the_counts(fixture_id: str) -> None:
    """Accuracy, final accuracy and error rate follow docs/METRICS.md §4."""
    metrics = compute_metrics(replay_fixture(fixture_id))

    assert metrics.accuracy_pct == pytest.approx(
        100.0 * metrics.correct_keystrokes / metrics.total_keystrokes
    )
    assert metrics.error_rate == pytest.approx(
        100.0 * metrics.incorrect_keystrokes / metrics.total_keystrokes
    )

    if metrics.final_length == 0:
        assert metrics.final_accuracy_pct is None
    else:
        assert metrics.final_accuracy_pct == pytest.approx(
            100.0
            * (metrics.final_length - metrics.uncorrected_errors)
            / metrics.final_length
        )


def test_fixture_g_final_accuracy_is_null_for_an_empty_buffer() -> None:
    """The empty final buffer has no measurable final-text accuracy."""
    metrics = compute_metrics(replay_fixture("G"))

    assert metrics.final_length == 0
    assert metrics.final_accuracy_pct is None
    assert metrics.accuracy_pct == pytest.approx(0.0)


@pytest.mark.parametrize("fixture_id", REPLAYABLE_FIXTURES)
def test_interval_and_pause_values_are_hand_computed(fixture_id: str) -> None:
    """Intervals, V and pause statistics match the §13 hand calculations."""
    expected = EXPECTED_INTERVALS[fixture_id]
    replay = replay_fixture(fixture_id)
    metrics = compute_metrics(replay)

    intervals = compute_intervals(replay.timed_actions)
    assert intervals == expected["intervals"]
    assert valid_intervals(intervals) == expected["valid"]
    assert metrics.pause_count == expected["pause_count"]
    assert metrics.total_pause_ms == pytest.approx(expected["total_pause_ms"])
    if expected["longest_pause_ms"] is None:
        assert metrics.longest_pause_ms is None
    else:
        assert metrics.longest_pause_ms == pytest.approx(
            expected["longest_pause_ms"]
        )
    assert metrics.zero_interval_count == expected["zero_interval_count"]


@pytest.mark.parametrize("fixture_id", REPLAYABLE_FIXTURES)
def test_iki_statistics_are_null_below_the_minimum(fixture_id: str) -> None:
    """All fixtures have fewer than 5 valid intervals, so IKI stats are null."""
    metrics = compute_metrics(replay_fixture(fixture_id))

    assert metrics.iki_valid_count < 5
    assert metrics.avg_iki_ms is None
    assert metrics.median_iki_ms is None
    assert metrics.iki_sd_ms is None
    assert metrics.iki_cv is None
    assert metrics.consistency_score is None


def test_interval_classification_boundaries() -> None:
    """Zero, valid, and pause intervals are classified per METRICS §8."""
    events = [down(seq, t) for seq, t in enumerate([0, 0, 200, 1199, 2199, 3699])]
    replay, metrics = metrics_for(events)

    assert compute_intervals(replay.timed_actions) == [0, 200, 999, 1000, 1500]
    assert metrics.zero_interval_count == 1
    assert valid_intervals(compute_intervals(replay.timed_actions)) == [200, 999]
    assert metrics.iki_valid_count == 2
    assert metrics.pause_count == 2
    assert metrics.total_pause_ms == pytest.approx(2500)
    assert metrics.longest_pause_ms == pytest.approx(1500)

    assert is_valid_interval(200) is True
    assert is_valid_interval(0) is False
    assert is_valid_interval(1000) is False
    assert is_pause(999) is False
    assert is_pause(1000) is True


def test_iki_statistics_over_five_valid_intervals() -> None:
    """Mean, median, sample SD and CV are computed over V only."""
    # Intervals: 100, 200, 300, 400, 500 => mean 300, median 300,
    # sample variance ((200^2)+(100^2)+0+(100^2)+(200^2)) / 4 = 25 000.
    events = [
        down(seq, t)
        for seq, t in enumerate([0, 100, 300, 600, 1000, 1500])
    ]
    _, metrics = metrics_for(events)

    assert metrics.iki_valid_count == 5
    assert metrics.avg_iki_ms == pytest.approx(300.0)
    assert metrics.median_iki_ms == pytest.approx(300.0)
    assert metrics.iki_sd_ms == pytest.approx(math.sqrt(25_000))
    assert metrics.iki_cv == pytest.approx(math.sqrt(25_000) / 300.0)
    assert metrics.consistency_score is None


def test_iki_statistics_are_null_with_four_valid_intervals() -> None:
    """Four valid intervals is below IKI_STATS_MIN_V = 5."""
    events = [down(seq, t) for seq, t in enumerate([0, 100, 300, 600, 1000])]
    _, metrics = metrics_for(events)

    assert metrics.iki_valid_count == 4
    assert metrics.avg_iki_ms is None
    assert metrics.median_iki_ms is None
    assert metrics.iki_sd_ms is None
    assert metrics.iki_cv is None


def test_consistency_requires_thirty_valid_intervals() -> None:
    """29 intervals => null; 30 intervals => a score (METRICS §8.6)."""
    # Constant 100 ms intervals give mean 100, SD 0, CV 0, score 100.0.
    _, below = metrics_for(
        [down(seq, seq * 100) for seq in range(30)]
    )
    _, at_threshold = metrics_for(
        [down(seq, seq * 100) for seq in range(31)]
    )

    assert below.iki_valid_count == 29
    assert below.consistency_score is None

    assert at_threshold.iki_valid_count == 30
    assert at_threshold.avg_iki_ms == pytest.approx(100.0)
    assert at_threshold.iki_sd_ms == pytest.approx(0.0)
    assert at_threshold.iki_cv == pytest.approx(0.0)
    assert at_threshold.consistency_score == 100.0


def test_zero_mean_guard_for_coefficient_of_variation() -> None:
    """CV is null when the mean is zero, never a division by zero."""
    assert coefficient_of_variation(0.0, 0.0) is None
    assert coefficient_of_variation(0.0, 12.5) is None
    assert coefficient_of_variation(100.0, 25.0) == pytest.approx(0.25)


def test_backspace_only_difference_does_not_change_gross_wpm() -> None:
    """Backspaces are not printable, so they never enter K or Gross WPM."""
    _, plain = metrics_for([down(0, 0), down(1, 800)])
    _, deleted = metrics_for(
        [down(0, 0), down(1, 800), backspace(2, 1600)]
    )

    assert plain.total_keystrokes == deleted.total_keystrokes == 2
    assert plain.gross_wpm == pytest.approx(deleted.gross_wpm)
    assert deleted.backspace_count == 1
    assert deleted.final_length == plain.final_length - 1


def test_trailing_moving_average_skips_nulls_and_expands_early() -> None:
    """Early points use available values; nulls are skipped, not zeroed."""
    assert trailing_moving_average([], 5) == []
    assert trailing_moving_average([10.0, None, 30.0, 40.0, 50.0, 60.0, 70.0], 5) == [
        10.0,
        10.0,
        20.0,
        80.0 / 3.0,
        32.5,
        45.0,
        50.0,
    ]
    with pytest.raises(ValueError):
        trailing_moving_average([1.0], 0)


def test_accuracy_guards_when_there_are_no_keystrokes() -> None:
    """A session with no keystrokes has no accuracy ratio to report."""
    replay = replay_events("a" * 100, "time", 10_000, [])
    metrics = compute_metrics(replay)

    assert metrics.total_keystrokes == 0
    assert metrics.gross_wpm == pytest.approx(0.0)
    assert metrics.net_wpm == pytest.approx(0.0)
    assert metrics.accuracy_pct is None
    assert metrics.error_rate is None
    assert metrics.final_accuracy_pct is None


def test_zero_duration_returns_null_wpm() -> None:
    """T = 0 makes WPM not computable rather than dividing by zero."""
    replay = replay_events("a", "passage", None, [down(0, 0)])
    metrics = compute_metrics(replay)

    assert replay.end_reason == "completed"
    assert replay.active_duration_ms == 0
    assert metrics.gross_wpm is None
    assert metrics.net_wpm is None
    assert metrics.accuracy_pct == pytest.approx(100.0)
    assert metrics.final_accuracy_pct == pytest.approx(100.0)


def test_dwell_validity_and_backspace_exclusion() -> None:
    """Invalid dwells are dropped; Backspace is excluded from the overall."""
    events = [
        down(0, 0),
        up(1, 100),
        down(2, 200),
        up(3, 350),
        down(4, 400),
        up(5, 1400),
        down(6, 1500),
        up(7, 2501),
        down(8, 2600),
        up(9, 2600),
        backspace(10, 2700),
        up(11, 2800, code="Backspace"),
    ]
    replay, metrics = metrics_for(events)

    # Valid printable dwells: 100 and 150 and 1000. The 1001 and 0 samples are
    # dropped; the Backspace dwell of 100 is excluded from the overall figure.
    assert metrics.dwell_count == 3
    assert metrics.avg_dwell_ms == pytest.approx(1250.0 / 3.0)
    assert metrics.median_dwell_ms == pytest.approx(150.0)

    key_stats = compute_key_stats(replay)
    assert key_stats.dwell_by_code["KeyA"].dwell_count == 3
    assert key_stats.dwell_by_code["KeyA"].dwell_sum_ms == pytest.approx(1250.0)
    assert key_stats.dwell_by_code["Backspace"].dwell_count == 1
    assert key_stats.dwell_by_code["Backspace"].dwell_sum_ms == pytest.approx(100.0)

    assert is_valid_dwell(0) is False
    assert is_valid_dwell(1) is True
    assert is_valid_dwell(1000) is True
    assert is_valid_dwell(1001) is False


def test_fixture_g_backspace_dwell_is_only_in_per_key_stats() -> None:
    """Fixture G's single Backspace dwell is excluded from the overall figure."""
    replay = replay_fixture("G")
    metrics = compute_metrics(replay)
    key_stats = compute_key_stats(replay)

    assert metrics.dwell_count == 0
    assert metrics.avg_dwell_ms is None
    assert metrics.median_dwell_ms is None

    backspace_stats = key_stats.dwell_by_code["Backspace"]
    assert backspace_stats.dwell_count == 1
    assert backspace_stats.dwell_sum_ms == pytest.approx(600.0)


def test_per_key_clean_transition_iki() -> None:
    """IKI is attributed to the later expected character, clean pairs only."""
    # Typed: a, x, Backspace, a, a, a, a, a. The only clean transitions are the
    # four consecutive correct a -> a pairs of 100 ms each.
    events = [
        down(0, 0),
        down(1, 100, key="x", code="KeyX"),
        backspace(2, 200),
        down(3, 300),
        down(4, 400),
        down(5, 500),
        down(6, 600),
        down(7, 700),
    ]
    replay, metrics = metrics_for(events, text="a" * 6)
    key_stats = compute_key_stats(replay)
    a_stats = key_stats.observations_by_char["a"]

    assert a_stats.attempts == 7
    assert a_stats.errors == 1
    assert a_stats.error_rate == pytest.approx(1.0 / 7.0)
    assert a_stats.iki_count == 4
    assert a_stats.iki_sum_ms == pytest.approx(400.0)
    assert a_stats.mean_iki_ms == pytest.approx(100.0)

    # The deleted incorrect keystroke is still an observation error.
    assert metrics.incorrect_keystrokes == 1
    assert metrics.corrected_errors == 1


def test_per_key_iki_excludes_pauses_and_incorrect_neighbours() -> None:
    """Pauses and either incorrect neighbour break a clean transition."""
    # A pause-class interval: both actions are correct, but 1000 ms is not V.
    paused = key_stats_for([down(0, 0), down(1, 1000), down(2, 2000)])
    assert paused.observations_by_char["a"].iki_count == 0

    # The middle keystroke is incorrect, so neither adjacent pair is clean.
    incorrect = key_stats_for(
        [
            down(0, 0),
            down(1, 100, key="x", code="KeyX"),
            down(2, 200),
        ]
    )
    assert incorrect.observations_by_char["a"].iki_count == 0


def test_fixture_a_errors_are_attributed_to_the_expected_character() -> None:
    """A wrong key is blamed on the character the text expected, not the key."""
    key_stats = compute_key_stats(replay_fixture("A"))
    observations = key_stats.observations_by_char

    assert observations["c"].attempts == 1
    assert observations["c"].errors == 0
    assert observations["a"].attempts == 2
    assert observations["a"].errors == 1
    assert observations["t"].attempts == 1
    assert observations["t"].errors == 0


def test_fixture_d_per_key_iki() -> None:
    """Fixture D's c -> a transition supplies the only clean interval."""
    key_stats = compute_key_stats(replay_fixture("D"))
    a_stats = key_stats.observations_by_char["a"]

    assert a_stats.iki_count == 1
    assert a_stats.iki_sum_ms == pytest.approx(800.0)
    assert a_stats.mean_iki_ms == pytest.approx(800.0)


def test_fixture_f_per_key_iki() -> None:
    """Fixture F's two clean 800 ms transitions attribute to a and t."""
    key_stats = compute_key_stats(replay_fixture("F"))
    observations = key_stats.observations_by_char

    assert observations["a"].iki_count == 1
    assert observations["a"].iki_sum_ms == pytest.approx(800.0)
    assert observations["t"].iki_count == 1
    assert observations["t"].iki_sum_ms == pytest.approx(800.0)
    assert observations["c"].iki_count == 0


def test_fixture_g_observations_are_attributed_to_expected_characters() -> None:
    """Fixture G typed c, a, t where the text expected t, h, e."""
    observations = compute_key_stats(replay_fixture("G")).observations_by_char

    assert set(observations) == {"t", "h", "e"}
    for key in ("t", "h", "e"):
        assert observations[key].attempts == 1
        assert observations[key].errors == 1
        assert observations[key].iki_count == 0


def test_analyze_session_returns_metrics_and_key_stats() -> None:
    """The engine entry point exposes replay, metrics and per-key sums."""
    fixture = load_fixture("A")
    analysis = analyze_session(
        text=fixture["text"],
        mode=fixture["mode"],
        duration_limit_ms=fixture["duration_limit_ms"],
        events=fixture["events"],
    )

    assert isinstance(analysis, SessionAnalysis)
    assert isinstance(analysis.replay, ReplayResult)
    assert analysis.metrics.gross_wpm == pytest.approx(8.0)
    assert analysis.metrics.net_wpm == pytest.approx(6.0)
    assert analysis.key_stats.observations_by_char["a"].attempts == 2
