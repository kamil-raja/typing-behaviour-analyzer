"""Engine entry point for the Typing Behaviour Analyzer.

The engine is pure Python: it performs no HTTP calls and no database access.
Replay reconstructs the buffer in :mod:`app.engine.replay`; the metric formulas
live in :mod:`app.engine.metrics`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.engine.metrics import (
    KeyStats,
    SessionMetrics,
    compute_key_stats,
    compute_metrics,
)
from app.engine.replay import ReplayResult, replay_events


@dataclass(frozen=True)
class SessionAnalysis:
    """The full engine result for one validated session.

    ``replay`` retains the derived buffers and event-level detail; ``metrics``
    holds the stored session-level figures; ``key_stats`` holds the additive
    per-key sums. Outcome checks such as ``INCOMPLETE_SESSION`` remain with the
    caller (ADR-020).
    """

    replay: ReplayResult
    metrics: SessionMetrics
    key_stats: KeyStats


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
    return SessionAnalysis(
        replay=replay,
        metrics=compute_metrics(replay),
        key_stats=compute_key_stats(replay),
    )
