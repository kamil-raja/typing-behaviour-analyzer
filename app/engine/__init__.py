"""Engine entry point for the Typing Behaviour Analyzer.

The engine is pure Python: it performs no HTTP calls and no database access.
Replay reconstructs the buffer in :mod:`app.engine.replay`; the metric formulas
live in :mod:`app.engine.metrics`.

``analyze_session()`` also reports the tolerated data-quality conditions listed
in ``TBA_BLUEPRINT_v3_FINAL.md`` §6.3 as explicit warnings. They are diagnostic
statements about the submitted event stream, never metric calculations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.engine.keys import SessionKeyStat, merge_session_key_stats
from app.engine.metrics import (
    KeyStats,
    SessionMetrics,
    compute_key_stats,
    compute_metrics,
)
from app.engine.replay import ReplayResult, replay_events


@dataclass(frozen=True)
class DataQualityWarning:
    """One tolerated data-quality condition with its occurrence count."""

    code: str
    count: int
    message: str


@dataclass(frozen=True)
class SessionAnalysis:
    """The full engine result for one validated session.

    ``replay`` retains the derived buffers and event-level detail; ``metrics``
    holds the stored session-level figures; ``key_stats`` holds the raw additive
    maps (expected character plus physical dwell code); ``session_key_stats``
    holds the merged, ``key_code``-keyed rows ready for persistence. Outcome
    checks such as ``INCOMPLETE_SESSION`` remain with the caller (ADR-020).
    """

    replay: ReplayResult
    metrics: SessionMetrics
    key_stats: KeyStats
    session_key_stats: dict[str, SessionKeyStat]
    warnings: tuple[DataQualityWarning, ...]


def _data_quality_warnings(
    replay: ReplayResult,
    metrics: SessionMetrics,
) -> tuple[DataQualityWarning, ...]:
    """Describe the tolerated replay conditions that actually occurred."""
    conditions = (
        (
            "orphan_up",
            replay.orphan_up,
            "Key releases without a matching keypress were ignored.",
        ),
        (
            "missing_up",
            replay.missing_up,
            "Keypresses without a matching key release were recorded.",
        ),
        (
            "open_at_end",
            replay.open_at_end,
            "Keys were still held when the test ended.",
        ),
        (
            "invalid_dwell",
            metrics.invalid_dwell_count,
            "Dwell times outside 0-1000 ms were excluded.",
        ),
        (
            "dropped_after_end",
            replay.dropped_after_end,
            "Events after the test ended were ignored.",
        ),
    )
    return tuple(
        DataQualityWarning(code=code, count=count, message=message)
        for code, count, message in conditions
        if count > 0
    )


def analyze_session(
    text: str,
    mode: str,
    duration_limit_ms: float | None,
    events: Sequence[Mapping[str, Any]],
) -> SessionAnalysis:
    """Replay one validated session and compute its metrics and key stats."""
    replay = replay_events(
        text=text,
        mode=mode,
        duration_limit_ms=duration_limit_ms,
        events=events,
    )
    key_stats = compute_key_stats(replay)
    metrics = compute_metrics(replay)
    return SessionAnalysis(
        replay=replay,
        metrics=metrics,
        key_stats=key_stats,
        session_key_stats=merge_session_key_stats(key_stats),
        warnings=_data_quality_warnings(replay, metrics),
    )
