"""Engine entry point for the Typing Behaviour Analyzer.

The engine is pure Python: it performs no HTTP calls and no database access.
Replay is implemented in :mod:`app.engine.replay`; metric computation is added
in P0-D1-04.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.engine.replay import ReplayResult, replay_events


def analyze_session(
    text: str,
    mode: str,
    duration_limit_ms: float | None,
    events: Sequence[Mapping[str, Any]],
) -> ReplayResult:
    """Analyze one validated session.

    P0-D1-03 provides the replay stage only. P0-D1-04 will extend this entry
    point with metric and per-key computation; it currently returns the
    :class:`~app.engine.replay.ReplayResult`.
    """
    return replay_events(
        text=text,
        mode=mode,
        duration_limit_ms=duration_limit_ms,
        events=events,
    )
