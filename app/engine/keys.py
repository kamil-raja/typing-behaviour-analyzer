"""Keyboard identity, Wilson intervals and heatmap classification.

Responsibility: map the expected character of a keystroke to the physical
US-QWERTY key that would type it, merge the two attribution maps produced by
:mod:`app.engine.metrics` into the additive ``session_key_stats`` rows, and
apply the conservative Wilson heuristic from ``docs/METRICS.md`` §12.

This module is pure Python: no HTTP calls, no database access and no reading of
raw events. The static table covers all printable ASCII characters 32–126.
Capital and lowercase letters share a letter key; shifted symbols share their
base key.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from app.config import (
    HEATMAP_BASELINE_FLOOR,
    HEATMAP_MIN_N,
    HEATMAP_WEAK_MARGIN,
    HEATMAP_WEAK_MIN_X,
    HEATMAP_Z,
)
from app.engine.metrics import KeyStats

WEAK: Final = "weak"
AVERAGE: Final = "average"
STRONG: Final = "strong"
INSUFFICIENT: Final = "insufficient"

BACKSPACE_CODE: Final = "Backspace"
HEATMAP_METHOD: Final = "wilson_vs_pooled_baseline_heuristic"

# A binary floating-point margin can turn an exact decimal boundary such as
# 0.12 - 0.10 into 0.019999999999999997. The tolerance only protects the
# documented >= comparison; it does not change any threshold.
_FLOAT_TOLERANCE: Final = 1e-12


# ``event.code`` values for a US-QWERTY layout. Shifted symbols deliberately
# map to the same physical key as their unshifted base character.
CHAR_TO_CODE: Final[dict[str, str]] = {
    # Spacebar.
    " ": "Space",
    # Digit row: unshifted digits and their shifted symbols.
    "1": "Digit1", "!": "Digit1",
    "2": "Digit2", "@": "Digit2",
    "3": "Digit3", "#": "Digit3",
    "4": "Digit4", "$": "Digit4",
    "5": "Digit5", "%": "Digit5",
    "6": "Digit6", "^": "Digit6",
    "7": "Digit7", "&": "Digit7",
    "8": "Digit8", "*": "Digit8",
    "9": "Digit9", "(": "Digit9",
    "0": "Digit0", ")": "Digit0",
    # Top row and its shifted symbols.
    "`": "Backquote", "~": "Backquote",
    "-": "Minus", "_": "Minus",
    "=": "Equal", "+": "Equal",
    # QWERTY letter rows.
    "q": "KeyQ", "Q": "KeyQ",
    "w": "KeyW", "W": "KeyW",
    "e": "KeyE", "E": "KeyE",
    "r": "KeyR", "R": "KeyR",
    "t": "KeyT", "T": "KeyT",
    "y": "KeyY", "Y": "KeyY",
    "u": "KeyU", "U": "KeyU",
    "i": "KeyI", "I": "KeyI",
    "o": "KeyO", "O": "KeyO",
    "p": "KeyP", "P": "KeyP",
    "a": "KeyA", "A": "KeyA",
    "s": "KeyS", "S": "KeyS",
    "d": "KeyD", "D": "KeyD",
    "f": "KeyF", "F": "KeyF",
    "g": "KeyG", "G": "KeyG",
    "h": "KeyH", "H": "KeyH",
    "j": "KeyJ", "J": "KeyJ",
    "k": "KeyK", "K": "KeyK",
    "l": "KeyL", "L": "KeyL",
    "z": "KeyZ", "Z": "KeyZ",
    "x": "KeyX", "X": "KeyX",
    "c": "KeyC", "C": "KeyC",
    "v": "KeyV", "V": "KeyV",
    "b": "KeyB", "B": "KeyB",
    "n": "KeyN", "N": "KeyN",
    "m": "KeyM", "M": "KeyM",
    # Punctuation and its shifted symbols.
    "[": "BracketLeft", "{": "BracketLeft",
    "]": "BracketRight", "}": "BracketRight",
    "\\": "Backslash", "|": "Backslash",
    ";": "Semicolon", ":": "Semicolon",
    "'": "Quote", '"': "Quote",
    ",": "Comma", "<": "Comma",
    ".": "Period", ">": "Period",
    "/": "Slash", "?": "Slash",
}

# Display labels for the drawn US-QWERTY keys, keyed by ``event.code``. Every
# code in ``CHAR_TO_CODE`` plus Backspace is covered; the heatmap API returns
# all of them so a key with no recorded attempts is still renderable.
KEY_CODE_LABELS: Final[dict[str, str]] = {
    "Backquote": "`",
    "Digit1": "1",
    "Digit2": "2",
    "Digit3": "3",
    "Digit4": "4",
    "Digit5": "5",
    "Digit6": "6",
    "Digit7": "7",
    "Digit8": "8",
    "Digit9": "9",
    "Digit0": "0",
    "Minus": "-",
    "Equal": "=",
    "KeyQ": "Q",
    "KeyW": "W",
    "KeyE": "E",
    "KeyR": "R",
    "KeyT": "T",
    "KeyY": "Y",
    "KeyU": "U",
    "KeyI": "I",
    "KeyO": "O",
    "KeyP": "P",
    "BracketLeft": "[",
    "BracketRight": "]",
    "Backslash": "\\",
    "KeyA": "A",
    "KeyS": "S",
    "KeyD": "D",
    "KeyF": "F",
    "KeyG": "G",
    "KeyH": "H",
    "KeyJ": "J",
    "KeyK": "K",
    "KeyL": "L",
    "Semicolon": ";",
    "Quote": "'",
    "KeyZ": "Z",
    "KeyX": "X",
    "KeyC": "C",
    "KeyV": "V",
    "KeyB": "B",
    "KeyN": "N",
    "KeyM": "M",
    "Comma": ",",
    "Period": ".",
    "Slash": "/",
    "Space": "Space",
    "Backspace": "Backspace",
}


@dataclass(frozen=True)
class SessionKeyStat:
    """One additive ``session_key_stats`` row.

    The field names match the database columns exactly. ``attempts``, ``errors``
    and the IKI sums are attributed through the expected character's key;
    ``dwell_count`` and ``dwell_sum_ms`` are attributed to the physical key that
    was pressed. ``Backspace`` rows have observations of zero.
    """

    key_code: str
    attempts: int = 0
    errors: int = 0
    dwell_count: int = 0
    dwell_sum_ms: float = 0.0
    iki_count: int = 0
    iki_sum_ms: float = 0.0

    @property
    def error_rate(self) -> float | None:
        """Per-key error ratio ``x / n``, or ``None`` with no observations."""
        if self.attempts == 0:
            return None
        return self.errors / self.attempts

    @property
    def mean_dwell_ms(self) -> float | None:
        """Mean valid dwell for this physical key."""
        if self.dwell_count == 0:
            return None
        return self.dwell_sum_ms / self.dwell_count

    @property
    def mean_iki_ms(self) -> float | None:
        """Mean clean-transition IKI into this key."""
        if self.iki_count == 0:
            return None
        return self.iki_sum_ms / self.iki_count


@dataclass(frozen=True)
class KeyClassification:
    """The Wilson-heuristic result for one key.

    ``error_rate`` is a ratio in ``[0, 1]``. The confidence bounds are ``None``
    when the key has fewer than ``HEATMAP_MIN_N`` observations.
    """

    attempts: int
    errors: int
    error_rate: float | None
    ci_low: float | None
    ci_high: float | None
    classification: str


def code_for_char(char: str) -> str:
    """Return the US-QWERTY ``event.code`` for one printable character.

    Raises:
        ValueError: if ``char`` is not one of the 95 printable ASCII
            characters. The engine never silently drops an unmapped character.
    """
    try:
        return CHAR_TO_CODE[char]
    except KeyError as exc:
        raise ValueError(
            f"no US-QWERTY key code for character {char!r}"
        ) from exc


def wilson_ci(x: int, n: int, z: float = HEATMAP_Z) -> tuple[float, float]:
    """Return the Wilson score interval for ``x`` errors in ``n`` observations.

    The formula is exactly ``docs/METRICS.md`` §12.2 with ``e = x / n``. The
    result is clamped to ``[0, 1]`` to remove floating-point overshoot at the
    boundaries; the mathematical interval already lies inside that range.

    Raises:
        ValueError: if ``n`` is not positive, ``x`` is outside ``0..n``, or
            ``z`` is not positive.
    """
    if n <= 0:
        raise ValueError("n must be a positive number of observations")
    if x < 0 or x > n:
        raise ValueError("x must satisfy 0 <= x <= n")
    if z <= 0:
        raise ValueError("z must be positive")

    error_rate = x / n
    z_squared = z * z
    denominator = 1.0 + z_squared / n
    centre = (error_rate + z_squared / (2.0 * n)) / denominator
    half = (
        z
        * math.sqrt(
            error_rate * (1.0 - error_rate) / n
            + z_squared / (4.0 * n * n)
        )
        / denominator
    )
    return max(0.0, centre - half), min(1.0, centre + half)


def pooled_baseline_error_rate(
    total_errors: int, total_attempts: int
) -> float | None:
    """Return ``max(Σx / Σn, 0.01)`` over the keys in scope.

    ``None`` means the scope has no observations to pool, so there is no
    baseline yet. Invalid totals raise :class:`ValueError`.
    """
    if total_attempts < 0 or total_errors < 0:
        raise ValueError("totals must not be negative")
    if total_errors > total_attempts:
        raise ValueError("total_errors must not exceed total_attempts")
    if total_attempts == 0:
        return None
    return max(total_errors / total_attempts, HEATMAP_BASELINE_FLOOR)


def classify_key(
    e: float,
    b: float,
    lo: float | None,
    hi: float | None,
    x: int,
) -> str:
    """Classify one key from its error rate, baseline and Wilson bounds.

    ``e`` is ``x / n`` and ``b`` is the pooled baseline (already floored).
    ``lo`` and ``hi`` are the Wilson bounds. Passing ``None`` for the bounds
    represents the grey ``n < HEATMAP_MIN_N`` state and returns
    :data:`INSUFFICIENT`; :func:`classify_observation` applies that gate.

    The rules are copied from ``docs/METRICS.md`` §12.2:

    * weak: ``lo > b`` **and** ``e - b >= 0.02`` **and** ``x >= 3``;
    * strong: not weak and ``e <= b``;
    * average: otherwise.
    """
    if lo is None or hi is None:
        return INSUFFICIENT
    if hi < lo:
        raise ValueError("hi must not be below lo")

    if (
        lo > b
        and e - b >= HEATMAP_WEAK_MARGIN - _FLOAT_TOLERANCE
        and x >= HEATMAP_WEAK_MIN_X
    ):
        return WEAK
    if e <= b:
        return STRONG
    return AVERAGE


def classify_observation(
    attempts: int,
    errors: int,
    baseline: float,
    *,
    z: float = HEATMAP_Z,
) -> KeyClassification:
    """Classify one key from its observation and error counts.

    The ``attempts >= HEATMAP_MIN_N`` gate is the grey state. Below it, no
    Wilson interval is computed and the class is :data:`INSUFFICIENT`.
    """
    if attempts < 0 or errors < 0:
        raise ValueError("attempts and errors must not be negative")
    if errors > attempts:
        raise ValueError("errors must not exceed attempts")

    error_rate = errors / attempts if attempts > 0 else None
    if attempts < HEATMAP_MIN_N:
        return KeyClassification(
            attempts=attempts,
            errors=errors,
            error_rate=error_rate,
            ci_low=None,
            ci_high=None,
            classification=INSUFFICIENT,
        )

    assert error_rate is not None
    lo, hi = wilson_ci(errors, attempts, z)
    return KeyClassification(
        attempts=attempts,
        errors=errors,
        error_rate=error_rate,
        ci_low=lo,
        ci_high=hi,
        classification=classify_key(error_rate, baseline, lo, hi, errors),
    )


def classify_key_stat(
    stat: SessionKeyStat,
    baseline: float,
    *,
    z: float = HEATMAP_Z,
) -> KeyClassification:
    """Classify one stored row; dwell never affects the error class."""
    return classify_observation(
        stat.attempts,
        stat.errors,
        baseline,
        z=z,
    )


def merge_session_key_stats(key_stats: KeyStats) -> dict[str, SessionKeyStat]:
    """Merge the metric layer's two attribution maps into stored rows.

    Observations, errors and IKI arrive keyed by the expected character and are
    mapped through :data:`CHAR_TO_CODE`; several characters can share one
    physical key, so the values are summed. Dwell already arrives keyed by the
    physical ``event.code`` and is merged onto the same row. ``Backspace`` and
    any other dwell-only code appear with zero observations.

    Returns:
        A dict keyed by ``key_code`` and sorted by key code.

    Raises:
        ValueError: if an expected character is outside printable ASCII.
    """
    attempts: dict[str, int] = {}
    errors: dict[str, int] = {}
    iki_counts: dict[str, int] = {}
    iki_sums: dict[str, float] = {}

    for expected, observation in key_stats.observations_by_char.items():
        code = code_for_char(expected)
        attempts[code] = attempts.get(code, 0) + observation.attempts
        errors[code] = errors.get(code, 0) + observation.errors
        iki_counts[code] = iki_counts.get(code, 0) + observation.iki_count
        iki_sums[code] = iki_sums.get(code, 0.0) + observation.iki_sum_ms

    dwell_counts: dict[str, int] = {}
    dwell_sums: dict[str, float] = {}
    for code, dwell in key_stats.dwell_by_code.items():
        dwell_counts[code] = dwell_counts.get(code, 0) + dwell.dwell_count
        dwell_sums[code] = dwell_sums.get(code, 0.0) + dwell.dwell_sum_ms

    codes = set(attempts) | set(dwell_counts)
    return {
        code: SessionKeyStat(
            key_code=code,
            attempts=attempts.get(code, 0),
            errors=errors.get(code, 0),
            dwell_count=dwell_counts.get(code, 0),
            dwell_sum_ms=dwell_sums.get(code, 0.0),
            iki_count=iki_counts.get(code, 0),
            iki_sum_ms=iki_sums.get(code, 0.0),
        )
        for code in sorted(codes)
    }


@dataclass(frozen=True)
class KeyStatObservation:
    """One stored ``session_key_stats`` row tagged with its session."""

    session_id: str
    stat: SessionKeyStat


@dataclass(frozen=True)
class AggregatedKeyStat:
    """Additive per-key sums across every session in scope.

    ``attempts``, ``errors`` and the IKI sums are sums of per-session sums, so
    the error rate is ``Σerrors / Σattempts`` rather than a mean of per-session
    rates. ``session_count`` is the number of distinct sessions that stored a
    row for this key.
    """

    key_code: str
    attempts: int = 0
    errors: int = 0
    dwell_count: int = 0
    dwell_sum_ms: float = 0.0
    iki_count: int = 0
    iki_sum_ms: float = 0.0
    session_count: int = 0

    @property
    def error_rate(self) -> float | None:
        """Aggregated error ratio ``Σx / Σn``, or ``None`` with no attempts."""
        if self.attempts == 0:
            return None
        return self.errors / self.attempts

    @property
    def mean_dwell_ms(self) -> float | None:
        """Mean valid dwell across sessions for this physical key."""
        if self.dwell_count == 0:
            return None
        return self.dwell_sum_ms / self.dwell_count

    @property
    def mean_iki_ms(self) -> float | None:
        """Mean clean-transition IKI into this key across sessions."""
        if self.iki_count == 0:
            return None
        return self.iki_sum_ms / self.iki_count


@dataclass(frozen=True)
class HeatmapKey:
    """One key in the historical heatmap response (blueprint §10)."""

    key_code: str
    label: str
    attempts: int
    errors: int
    error_rate: float | None
    ci_low: float | None
    ci_high: float | None
    dwell_count: int
    mean_dwell_ms: float | None
    iki_count: int
    mean_iki_ms: float | None
    classification: str
    dwell_flag: str | None
    reason: str
    session_count: int
    # Only the Backspace entry carries this; every other key is ``None``.
    backspace_presses: int | None = None


@dataclass(frozen=True)
class KeyHeatmap:
    """Historical per-key statistics plus the classification inputs.

    ``baseline_error_rate`` is ``None`` when the scope holds no observations.
    ``overall_mean_dwell_ms`` excludes Backspace (``docs/METRICS.md`` §12.3).
    ``scoped_session_count`` counts every session in scope; each key's
    ``session_count`` counts only sessions that stored a row for that key.
    """

    method: str
    baseline_error_rate: float | None
    min_observations: int
    overall_mean_dwell_ms: float | None
    scoped_session_count: int
    keys: tuple[HeatmapKey, ...]


def aggregate_key_stats(
    observations: Iterable[KeyStatObservation],
) -> list[AggregatedKeyStat]:
    """Sum stored per-session key rows by ``key_code``.

    Only keys that appear in at least one session are returned, ordered by key
    code. Missing keys are therefore absent here; :func:`build_key_heatmap`
    adds the unattempted keys from :data:`KEY_CODE_LABELS`.
    """
    totals: dict[str, list[float]] = {}
    sessions: dict[str, set[str]] = {}

    for observation in observations:
        stat = observation.stat
        if stat.attempts < 0 or stat.errors < 0:
            raise ValueError("attempts and errors must not be negative")
        if stat.errors > stat.attempts:
            raise ValueError("errors must not exceed attempts")
        if stat.dwell_count < 0 or stat.iki_count < 0:
            raise ValueError("counts must not be negative")

        sums = totals.setdefault(
            stat.key_code,
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        sums[0] += stat.attempts
        sums[1] += stat.errors
        sums[2] += stat.dwell_count
        sums[3] += stat.dwell_sum_ms
        sums[4] += stat.iki_count
        sums[5] += stat.iki_sum_ms
        sessions.setdefault(stat.key_code, set()).add(observation.session_id)

    return [
        AggregatedKeyStat(
            key_code=code,
            attempts=int(totals[code][0]),
            errors=int(totals[code][1]),
            dwell_count=int(totals[code][2]),
            dwell_sum_ms=totals[code][3],
            iki_count=int(totals[code][4]),
            iki_sum_ms=totals[code][5],
            session_count=len(sessions[code]),
        )
        for code in sorted(totals)
    ]


def _classification_reason(
    classification: KeyClassification,
    session_count: int,
) -> str:
    """Explain one class in plain words without any significance claim."""
    if classification.classification == INSUFFICIENT:
        if classification.attempts == 0 and session_count == 0:
            return "no recorded attempts"
        return (
            f"insufficient data: {classification.attempts} of "
            f"{HEATMAP_MIN_N} observations"
        )
    if classification.classification == WEAK:
        return (
            "weak: the confidence interval is above the pooled baseline "
            f"with at least a {HEATMAP_WEAK_MARGIN:.0%} margin and at least "
            f"{HEATMAP_WEAK_MIN_X} errors"
        )
    if classification.classification == STRONG:
        return "strong: the error rate is at or below the pooled baseline"
    return "average: above the baseline but not classified weak"


def build_key_heatmap(
    aggregated: Iterable[AggregatedKeyStat],
    *,
    scoped_session_count: int = 0,
    backspace_presses: int = 0,
    z: float = HEATMAP_Z,
) -> KeyHeatmap:
    """Classify the aggregated keys and add every unattempted key.

    The pooled baseline and the overall mean dwell exclude Backspace
    (``docs/METRICS.md`` §12.1, §12.3). Only codes in :data:`KEY_CODE_LABELS`
    are returned; dwell recorded for any other physical code still counts
    toward ``overall_mean_dwell_ms`` but never becomes a heatmap entry. Every
    tracked key is returned, so a key with no recorded attempts is
    distinguishable by ``attempts == 0`` and ``session_count == 0``.

    ``backspace_presses`` is the scope's stored ``session_metrics`` sum. It is
    kept separate from Backspace's ``dwell_count`` because a press without a
    valid keyup has no dwell sample.
    """
    if scoped_session_count < 0:
        raise ValueError("scoped_session_count must not be negative")
    if backspace_presses < 0:
        raise ValueError("backspace_presses must not be negative")

    rows = list(aggregated)
    by_code = {row.key_code: row for row in rows}
    printable = [row for row in rows if row.key_code != BACKSPACE_CODE]

    baseline = pooled_baseline_error_rate(
        sum(row.errors for row in printable),
        sum(row.attempts for row in printable),
    )

    dwell_count = sum(row.dwell_count for row in printable)
    overall_mean_dwell = (
        sum(row.dwell_sum_ms for row in printable) / dwell_count
        if dwell_count > 0
        else None
    )

    keys: list[HeatmapKey] = []
    for code in sorted(KEY_CODE_LABELS):
        row = by_code.get(code)
        if row is None:
            row = AggregatedKeyStat(key_code=code)
        if baseline is None:
            classification = KeyClassification(
                attempts=row.attempts,
                errors=row.errors,
                error_rate=row.error_rate,
                ci_low=None,
                ci_high=None,
                classification=INSUFFICIENT,
            )
        else:
            classification = classify_observation(
                row.attempts,
                row.errors,
                baseline,
                z=z,
            )
        keys.append(
            HeatmapKey(
                key_code=code,
                label=KEY_CODE_LABELS[code],
                attempts=row.attempts,
                errors=row.errors,
                error_rate=classification.error_rate,
                ci_low=classification.ci_low,
                ci_high=classification.ci_high,
                dwell_count=row.dwell_count,
                mean_dwell_ms=row.mean_dwell_ms,
                iki_count=row.iki_count,
                mean_iki_ms=row.mean_iki_ms,
                classification=classification.classification,
                dwell_flag=None,
                reason=(
                    "not classified: Backspace reports press count and dwell"
                    if code == BACKSPACE_CODE
                    else _classification_reason(
                        classification,
                        row.session_count,
                    )
                ),
                session_count=row.session_count,
                backspace_presses=(
                    backspace_presses if code == BACKSPACE_CODE else None
                ),
            )
        )

    return KeyHeatmap(
        method=HEATMAP_METHOD,
        baseline_error_rate=baseline,
        min_observations=HEATMAP_MIN_N,
        overall_mean_dwell_ms=overall_mean_dwell,
        scoped_session_count=scoped_session_count,
        keys=tuple(keys),
    )
