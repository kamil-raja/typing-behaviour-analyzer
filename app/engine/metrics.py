"""Metric formulas for the Typing Behaviour Analyzer.

Responsibility: turn a :class:`~app.engine.replay.ReplayResult` into the stored
session metrics and the additive per-key sums defined in ``docs/METRICS.md``.
This module is pure Python: it performs no HTTP calls, no database access, and
no re-parsing of raw events.

Reference: ``docs/METRICS.md`` §2–§12 and ``TBA_BLUEPRINT_v3_FINAL.md`` §7.

Per-key attribution follows ``docs/METRICS.md``: observations, errors and IKI
are keyed by the **expected character** (§10, §12.1), while dwell is keyed by
the **physically pressed** ``event.code`` (§12.1). Mapping expected characters
to US-QWERTY key codes is the job of :mod:`app.engine.keys` (P0-D1-05).
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from app.config import (
    CONSISTENCY_MIN_V,
    DWELL_MAX_MS,
    IKI_MAX_MS,
    IKI_STATS_MIN_V,
    PAUSE_THRESHOLD_MS,
)
from app.engine.replay import PRINTABLE, ReplayResult, TimedAction

MS_PER_MINUTE: Final = 60_000.0
CHARS_PER_WORD: Final = 5.0


@dataclass(frozen=True)
class SessionMetrics:
    """All session-level metrics stored in ``session_metrics``.

    ``None`` means "not computable" (the database column is nullable), never a
    silent zero. Percentages are stored at full precision; only
    ``consistency_score`` is rounded, exactly as ``docs/METRICS.md`` §8.6
    specifies.
    """

    gross_wpm: float | None
    net_wpm: float | None
    accuracy_pct: float | None
    final_accuracy_pct: float | None
    error_rate: float | None

    total_keystrokes: int
    correct_keystrokes: int
    incorrect_keystrokes: int
    final_length: int
    uncorrected_errors: int
    corrected_errors: int
    erased_unresolved_errors: int
    backspace_count: int
    backspace_presses: int

    avg_dwell_ms: float | None
    median_dwell_ms: float | None
    dwell_count: int
    invalid_dwell_count: int

    avg_iki_ms: float | None
    median_iki_ms: float | None
    iki_sd_ms: float | None
    iki_valid_count: int
    iki_cv: float | None
    consistency_score: float | None

    pause_count: int
    total_pause_ms: float
    longest_pause_ms: float | None
    zero_interval_count: int


@dataclass(frozen=True)
class KeyObservationStats:
    """Per-key observation sums, keyed by expected character.

    ``attempts`` and ``errors`` describe accepted printable keystrokes that
    *expected* this character, even if the key was later deleted. ``iki_count``
    and ``iki_sum_ms`` only include clean transitions (both neighbours correct)
    into this character.
    """

    attempts: int = 0
    errors: int = 0
    iki_count: int = 0
    iki_sum_ms: float = 0.0

    @property
    def error_rate(self) -> float | None:
        """Per-key error rate ``x / n`` (a ratio in ``[0, 1]``)."""
        if self.attempts == 0:
            return None
        return self.errors / self.attempts

    @property
    def mean_iki_ms(self) -> float | None:
        """Mean clean-transition IKI into this character."""
        if self.iki_count == 0:
            return None
        return self.iki_sum_ms / self.iki_count


@dataclass(frozen=True)
class KeyDwellStats:
    """Per-key dwell sums, keyed by the physically pressed ``event.code``."""

    dwell_count: int = 0
    dwell_sum_ms: float = 0.0

    @property
    def mean_dwell_ms(self) -> float | None:
        """Mean valid dwell for this physical key."""
        if self.dwell_count == 0:
            return None
        return self.dwell_sum_ms / self.dwell_count


@dataclass(frozen=True)
class KeyStats:
    """Additive per-key sums produced by the metric layer.

    ``observations_by_char`` is keyed by expected character (``docs/METRICS.md``
    §10, §12.1). ``dwell_by_code`` is keyed by physical key code and includes
    Backspace (``docs/METRICS.md`` §7, §12.1). P0-D1-05 merges the two after
    applying ``CHAR_TO_CODE``.
    """

    observations_by_char: dict[str, KeyObservationStats]
    dwell_by_code: dict[str, KeyDwellStats]


def compute_intervals(timed_actions: Sequence[TimedAction]) -> list[float]:
    """Return ``I_i = t_i - t_(i-1)`` for consecutive timed actions.

    The first timed action has no preceding interval, so the result has one
    fewer item than the input.
    """
    return [
        current.t - previous.t
        for previous, current in zip(timed_actions, timed_actions[1:])
    ]


def is_pause(interval_ms: float) -> bool:
    """Return whether an interval is a pause (``I >= PAUSE_THRESHOLD_MS``)."""
    return interval_ms >= PAUSE_THRESHOLD_MS


def is_valid_interval(interval_ms: float) -> bool:
    """Return whether an interval belongs to ``V``: ``0 < I < IKI_MAX_MS``."""
    return 0 < interval_ms < IKI_MAX_MS


def is_valid_dwell(dwell_ms: float) -> bool:
    """Return whether a dwell sample is valid: ``0 < d <= DWELL_MAX_MS``."""
    return 0 < dwell_ms <= DWELL_MAX_MS


def valid_intervals(intervals: Sequence[float]) -> list[float]:
    """Return the valid interval list ``V`` used by every interval statistic."""
    return [interval for interval in intervals if is_valid_interval(interval)]


def coefficient_of_variation(mean: float, sd: float) -> float | None:
    """Return ``SD / mean``, or ``None`` when ``mean == 0``.

    The zero-mean guard (``docs/METRICS.md`` §8.5) prevents a division by zero.
    """
    if mean == 0:
        return None
    return sd / mean


def compute_metrics(replay: ReplayResult) -> SessionMetrics:
    """Compute every session-level metric from a replay.

    The replay already owns ``K``, ``C``, ``E``, ``N``, ``U``, ``Ec`` and ``Eu``;
    this function applies the formulas, interval classification and sample-size
    rules from ``docs/METRICS.md``. Metrics are still computed for an incomplete
    passage replay so the caller can report diagnostics, but the caller owns the
    ``INCOMPLETE_SESSION`` outcome check (ADR-020).
    """
    intervals = compute_intervals(replay.timed_actions)
    valid = valid_intervals(intervals)
    pauses = [interval for interval in intervals if is_pause(interval)]
    zero_interval_count = sum(1 for interval in intervals if interval == 0)

    gross_wpm: float | None = None
    net_wpm: float | None = None
    if replay.active_duration_ms > 0:
        t_min = replay.active_duration_ms / MS_PER_MINUTE
        gross_wpm = (replay.K / CHARS_PER_WORD) / t_min
        net_wpm = max(0.0, ((replay.N - replay.U) / CHARS_PER_WORD) / t_min)

    accuracy_pct = (
        100.0 * replay.C / replay.K if replay.K > 0 else None
    )
    final_accuracy_pct = (
        100.0 * (replay.N - replay.U) / replay.N if replay.N > 0 else None
    )
    error_rate = (
        100.0 * replay.E / replay.K if replay.K > 0 else None
    )

    # Overall dwell excludes Backspace (§7) and invalid samples (§7).
    printable_dwells = [
        sample.dwell_ms
        for sample in replay.dwell_samples
        if not sample.is_backspace and is_valid_dwell(sample.dwell_ms)
    ]
    invalid_dwell_count = sum(
        1
        for sample in replay.dwell_samples
        if not is_valid_dwell(sample.dwell_ms)
    )
    if printable_dwells:
        avg_dwell_ms = statistics.fmean(printable_dwells)
        median_dwell_ms = statistics.median(printable_dwells)
    else:
        avg_dwell_ms = None
        median_dwell_ms = None

    # IKI statistics use V only and are all null below IKI_STATS_MIN_V.
    if len(valid) >= IKI_STATS_MIN_V:
        avg_iki_ms = statistics.fmean(valid)
        median_iki_ms = statistics.median(valid)
        iki_sd_ms = statistics.stdev(valid)
        iki_cv = coefficient_of_variation(avg_iki_ms, iki_sd_ms)
    else:
        avg_iki_ms = None
        median_iki_ms = None
        iki_sd_ms = None
        iki_cv = None

    # Consistency requires at least CONSISTENCY_MIN_V valid intervals and a
    # positive mean. iki_cv is already None when the mean is zero.
    if len(valid) >= CONSISTENCY_MIN_V and iki_cv is not None:
        consistency_score = round(100.0 * max(0.0, 1.0 - iki_cv), 1)
    else:
        consistency_score = None

    return SessionMetrics(
        gross_wpm=gross_wpm,
        net_wpm=net_wpm,
        accuracy_pct=accuracy_pct,
        final_accuracy_pct=final_accuracy_pct,
        error_rate=error_rate,
        total_keystrokes=replay.K,
        correct_keystrokes=replay.C,
        incorrect_keystrokes=replay.E,
        final_length=replay.N,
        uncorrected_errors=replay.U,
        corrected_errors=replay.Ec,
        erased_unresolved_errors=replay.Eu,
        backspace_count=replay.backspace_deletions,
        backspace_presses=replay.backspace_presses,
        avg_dwell_ms=avg_dwell_ms,
        median_dwell_ms=median_dwell_ms,
        dwell_count=len(printable_dwells),
        invalid_dwell_count=invalid_dwell_count,
        avg_iki_ms=avg_iki_ms,
        median_iki_ms=median_iki_ms,
        iki_sd_ms=iki_sd_ms,
        iki_valid_count=len(valid),
        iki_cv=iki_cv,
        consistency_score=consistency_score,
        pause_count=len(pauses),
        total_pause_ms=float(sum(pauses)),
        longest_pause_ms=max(pauses) if pauses else None,
        zero_interval_count=zero_interval_count,
    )


def compute_key_stats(replay: ReplayResult) -> KeyStats:
    """Compute additive per-key sums from a replay.

    Observations, errors and clean-transition IKI are attributed to the expected
    character (``docs/METRICS.md`` §10, §12.1). Dwell is attributed to the
    physical ``event.code``, includes Backspace, and excludes invalid samples
    (§7, §12.1).
    """
    attempts: dict[str, int] = {}
    errors: dict[str, int] = {}
    iki_counts: dict[str, int] = {}
    iki_sums: dict[str, float] = {}

    for keystroke in replay.keystrokes:
        expected = keystroke.expected
        attempts[expected] = attempts.get(expected, 0) + 1
        if not keystroke.correct:
            errors[expected] = errors.get(expected, 0) + 1

    # A clean transition is two consecutive timed actions that are both
    # accepted printable keystrokes, both correct, and a valid interval.
    actions = replay.timed_actions
    for previous, current in zip(actions, actions[1:]):
        if previous.kind != PRINTABLE or current.kind != PRINTABLE:
            continue
        if not previous.correct or not current.correct:
            continue
        interval_ms = current.t - previous.t
        if not is_valid_interval(interval_ms):
            continue
        expected = current.expected
        assert expected is not None
        iki_counts[expected] = iki_counts.get(expected, 0) + 1
        iki_sums[expected] = iki_sums.get(expected, 0.0) + interval_ms

    observations_by_char = {
        expected: KeyObservationStats(
            attempts=attempts[expected],
            errors=errors.get(expected, 0),
            iki_count=iki_counts.get(expected, 0),
            iki_sum_ms=iki_sums.get(expected, 0.0),
        )
        for expected in sorted(set(attempts) | set(iki_counts))
    }

    dwell_counts: dict[str, int] = {}
    dwell_sums: dict[str, float] = {}
    for sample in replay.dwell_samples:
        dwell_ms = sample.dwell_ms
        if not is_valid_dwell(dwell_ms):
            continue
        dwell_counts[sample.code] = dwell_counts.get(sample.code, 0) + 1
        dwell_sums[sample.code] = dwell_sums.get(sample.code, 0.0) + dwell_ms

    dwell_by_code = {
        code: KeyDwellStats(
            dwell_count=dwell_counts[code],
            dwell_sum_ms=dwell_sums[code],
        )
        for code in sorted(dwell_counts)
    }

    return KeyStats(
        observations_by_char=observations_by_char,
        dwell_by_code=dwell_by_code,
    )
