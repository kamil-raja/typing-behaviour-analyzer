"""SQLite repository for the Typing Behaviour Analyzer.

Responsibility: every application SQL statement. The repository writes one
submitted session — its row, derived metrics, event log and per-key sums — in a
single transaction, and reads records back without recomputing any engine
value from raw events.

Reference: ``TBA_BLUEPRINT_v3_FINAL.md`` §9, ``docs/ARCHITECTURE.md`` §5,
``docs/EVENT_SCHEMA.md`` §10, ADR-034.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import ANALYSIS_VERSION
from app.db import connect
from app.engine import SessionAnalysis
from app.engine.keys import SessionKeyStat
from app.engine.metrics import SessionMetrics
from app.validators import ValidatedSessionPayload

# The repository replaces the in-memory store behind the same extension key so
# routes and tests keep a single service-locator surface (ADR-034).
STORE_EXTENSION_KEY = "tba_session_store"

# The engine's two non-column fields (ADR-033) are excluded from the insert and
# restored on read-back: error_rate is the documented identity, and
# invalid_dwell_count travels inside data_quality_json.
_METRIC_COLUMNS: tuple[str, ...] = (
    "gross_wpm",
    "net_wpm",
    "accuracy_pct",
    "final_accuracy_pct",
    "total_keystrokes",
    "correct_keystrokes",
    "incorrect_keystrokes",
    "final_length",
    "uncorrected_errors",
    "corrected_errors",
    "erased_unresolved_errors",
    "backspace_count",
    "backspace_presses",
    "avg_dwell_ms",
    "median_dwell_ms",
    "dwell_count",
    "avg_iki_ms",
    "median_iki_ms",
    "iki_sd_ms",
    "iki_valid_count",
    "iki_cv",
    "consistency_score",
    "pause_count",
    "total_pause_ms",
    "longest_pause_ms",
    "zero_interval_count",
    "iki_hist_json",
    "data_quality_json",
)

_INSERT_SESSION = """
INSERT INTO sessions (
    id, created_at, mode, duration_limit_ms, text_ref_json,
    passage_text, typed_text, active_duration_ms, end_reason,
    client_json, layout_hint, schema_version, analysis_version
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# Column order matches _METRIC_COLUMNS; session_id leads.
_INSERT_METRICS = """
INSERT INTO session_metrics (
    session_id,
    gross_wpm, net_wpm, accuracy_pct, final_accuracy_pct,
    total_keystrokes, correct_keystrokes, incorrect_keystrokes, final_length,
    uncorrected_errors, corrected_errors, erased_unresolved_errors,
    backspace_count, backspace_presses,
    avg_dwell_ms, median_dwell_ms, dwell_count,
    avg_iki_ms, median_iki_ms, iki_sd_ms, iki_valid_count, iki_cv,
    consistency_score,
    pause_count, total_pause_ms, longest_pause_ms, zero_interval_count,
    iki_hist_json, data_quality_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


@dataclass(frozen=True)
class StoredWarning:
    """One tolerated data-quality condition restored from persisted data."""

    code: str
    count: int
    message: str


@dataclass(frozen=True)
class SessionRecord:
    """One persisted session, read back from the database.

    Field names mirror the ``sessions`` row; ``metrics`` is reconstructed from
    ``session_metrics`` (plus the derived ``error_rate`` identity and the
    ``data_quality_json`` contents). ``warnings`` holds the persisted
    non-zero tolerated conditions.
    """

    session_id: str
    created_at: str
    schema_version: int
    mode: str
    duration_limit_ms: int | None
    text_ref: Mapping[str, Any]
    passage_text: str
    typed_text: str
    active_duration_ms: float
    end_reason: str
    client: Mapping[str, Any]
    layout_hint: str
    analysis_version: int
    metrics: SessionMetrics
    warnings: tuple[StoredWarning, ...]


@dataclass(frozen=True)
class SessionSummary:
    """One row of the paginated session list (newest first)."""

    session_id: str
    created_at: str
    mode: str
    duration_limit_ms: int | None
    active_duration_ms: float
    end_reason: str
    net_wpm: float | None
    accuracy_pct: float | None
    consistency_score: float | None


@dataclass(frozen=True)
class SessionExportRow:
    """One session in the ``sessions.csv`` column order (blueprint §10)."""

    session_id: str
    created_at: str
    mode: str
    duration_limit_ms: int | None
    active_duration_ms: float
    end_reason: str
    gross_wpm: float | None
    net_wpm: float | None
    accuracy_pct: float | None
    final_accuracy_pct: float | None
    total_keystrokes: int
    correct_keystrokes: int
    incorrect_keystrokes: int
    backspace_count: int


@dataclass(frozen=True)
class ProgressPoint:
    """One chronological point of the progress series (oldest first)."""

    session_id: str
    created_at: str
    mode: str
    duration_limit_ms: int | None
    net_wpm: float | None
    accuracy_pct: float | None


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a ``Z`` suffix."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _stored_warnings(
    analysis: SessionAnalysis,
) -> tuple[StoredWarning, ...]:
    """Serialise the engine's non-zero tolerated conditions."""
    return tuple(
        StoredWarning(code=warning.code, count=warning.count, message=warning.message)
        for warning in analysis.warnings
    )


def parse_stored_warnings(data_quality_json: str | None) -> tuple[StoredWarning, ...]:
    """Parse ``data_quality_json`` into warning objects; NULL means none."""
    if data_quality_json is None:
        return ()
    return tuple(
        StoredWarning(
            code=entry["code"],
            count=int(entry["count"]),
            message=entry["message"],
        )
        for entry in json.loads(data_quality_json)
    )


def _retained_events(
    events: Sequence[Mapping[str, Any]],
    dropped_after_end: int,
) -> Sequence[Mapping[str, Any]]:
    """Return the events replay actually processed (EVENT_SCHEMA §10).

    Replay drops a trailing suffix once an end is derived: the boundary event
    itself and everything after it. The completing keystroke is processed and
    therefore retained.
    """
    if dropped_after_end <= 0:
        return events
    return events[: len(events) - dropped_after_end]


def _reconstruct_metrics(
    row: Mapping[str, Any],
    warnings: tuple[StoredWarning, ...],
) -> SessionMetrics:
    """Rebuild ``SessionMetrics`` from a stored ``session_metrics`` row.

    ``error_rate`` applies the documented identity ``error_rate = 100 -``
    ``accuracy_pct`` (``docs/METRICS.md`` §4.4); the blueprint defines no
    ``error_rate`` column. ``invalid_dwell_count`` is restored from the
    persisted ``invalid_dwell`` warning count (0 when absent).
    """
    accuracy_pct: float | None = row["accuracy_pct"]
    invalid_dwell_warning = next(
        (warning for warning in warnings if warning.code == "invalid_dwell"),
        None,
    )
    return SessionMetrics(
        gross_wpm=row["gross_wpm"],
        net_wpm=row["net_wpm"],
        accuracy_pct=accuracy_pct,
        final_accuracy_pct=row["final_accuracy_pct"],
        error_rate=None if accuracy_pct is None else 100.0 - accuracy_pct,
        total_keystrokes=row["total_keystrokes"],
        correct_keystrokes=row["correct_keystrokes"],
        incorrect_keystrokes=row["incorrect_keystrokes"],
        final_length=row["final_length"],
        uncorrected_errors=row["uncorrected_errors"],
        corrected_errors=row["corrected_errors"],
        erased_unresolved_errors=row["erased_unresolved_errors"],
        backspace_count=row["backspace_count"],
        backspace_presses=row["backspace_presses"],
        avg_dwell_ms=row["avg_dwell_ms"],
        median_dwell_ms=row["median_dwell_ms"],
        dwell_count=row["dwell_count"],
        invalid_dwell_count=(
            invalid_dwell_warning.count if invalid_dwell_warning else 0
        ),
        avg_iki_ms=row["avg_iki_ms"],
        median_iki_ms=row["median_iki_ms"],
        iki_sd_ms=row["iki_sd_ms"],
        iki_valid_count=row["iki_valid_count"],
        iki_cv=row["iki_cv"],
        consistency_score=row["consistency_score"],
        pause_count=row["pause_count"],
        total_pause_ms=row["total_pause_ms"],
        longest_pause_ms=row["longest_pause_ms"],
        zero_interval_count=row["zero_interval_count"],
    )


def _metric_values(
    metrics: SessionMetrics,
    warnings_json: str | None,
) -> tuple[Any, ...]:
    """Column names (``_METRIC_COLUMNS``) paired positionally with values."""
    return (
        metrics.gross_wpm,
        metrics.net_wpm,
        metrics.accuracy_pct,
        metrics.final_accuracy_pct,
        metrics.total_keystrokes,
        metrics.correct_keystrokes,
        metrics.incorrect_keystrokes,
        metrics.final_length,
        metrics.uncorrected_errors,
        metrics.corrected_errors,
        metrics.erased_unresolved_errors,
        metrics.backspace_count,
        metrics.backspace_presses,
        metrics.avg_dwell_ms,
        metrics.median_dwell_ms,
        metrics.dwell_count,
        metrics.avg_iki_ms,
        metrics.median_iki_ms,
        metrics.iki_sd_ms,
        metrics.iki_valid_count,
        metrics.iki_cv,
        metrics.consistency_score,
        metrics.pause_count,
        metrics.total_pause_ms,
        metrics.longest_pause_ms,
        metrics.zero_interval_count,
        None,  # iki_hist_json: reserved for the P1 histogram
        warnings_json,
    )


class SessionRepository:
    """All SQL for storing and retrieving typing sessions.

    One SQLite connection per method call keeps transactions short and the
    repository independent of the Flask request cycle. Writes for one session
    happen inside a single transaction that is rolled back completely on any
    failure.
    """

    def __init__(self, database: str) -> None:
        self._database = database

    def _connect(self) -> sqlite3.Connection:
        return connect(self._database)

    def create(
        self,
        payload: ValidatedSessionPayload,
        analysis: SessionAnalysis,
    ) -> SessionRecord:
        """Persist one validated, analysed session in a single transaction."""
        session_id = uuid4().hex
        created_at = _utc_now_iso()
        replay = analysis.replay
        preserved_warnings = _stored_warnings(analysis)
        warnings_json = (
            json.dumps(
                [
                    {"code": warning.code, "count": warning.count, "message": warning.message}
                    for warning in preserved_warnings
                ]
            )
            if preserved_warnings
            else None
        )
        retained_events = _retained_events(
            payload.events,
            replay.dropped_after_end,
        )

        connection = self._connect()
        try:
            connection.execute(
                _INSERT_SESSION,
                (
                    session_id,
                    created_at,
                    payload.mode,
                    payload.duration_limit_ms,
                    json.dumps(dict(payload.text_ref)),
                    replay.text,
                    replay.typed_final,
                    replay.active_duration_ms,
                    replay.end_reason,
                    json.dumps(dict(payload.client)),
                    payload.client["layout_hint"],
                    payload.schema_version,
                    ANALYSIS_VERSION,
                ),
            )
            connection.execute(_INSERT_METRICS, (session_id, *_metric_values(analysis.metrics, warnings_json)))
            connection.executemany(
                "INSERT INTO keystroke_events "
                "(session_id, seq, type, t_ms, code, key, repeat) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        session_id,
                        int(event["seq"]),
                        str(event["type"]),
                        float(event["t"]),
                        str(event["code"]),
                        event["key"],
                        int(bool(event["repeat"])),
                    )
                    for event in retained_events
                ],
            )
            connection.executemany(
                "INSERT INTO session_key_stats "
                "(session_id, key_code, attempts, errors, dwell_count, "
                "dwell_sum_ms, iki_count, iki_sum_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        session_id,
                        stat.key_code,
                        stat.attempts,
                        stat.errors,
                        stat.dwell_count,
                        stat.dwell_sum_ms,
                        stat.iki_count,
                        stat.iki_sum_ms,
                    )
                    for stat in analysis.session_key_stats.values()
                ],
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

        record = self.get(session_id)
        if record is None:  # pragma: no cover - the insert just committed
            raise RuntimeError(f"session {session_id} vanished after insert")
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        """Load one session with its metrics, or ``None`` when unknown."""
        connection = self._connect()
        try:
            created = connection.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if created is None:
                return None
            metrics_row = connection.execute(
                "SELECT * FROM session_metrics WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            assert metrics_row is not None  # the FK guarantees a metrics row
            warnings = parse_stored_warnings(metrics_row["data_quality_json"])
            return SessionRecord(
                session_id=created["id"],
                created_at=created["created_at"],
                schema_version=created["schema_version"],
                mode=created["mode"],
                duration_limit_ms=created["duration_limit_ms"],
                text_ref=json.loads(created["text_ref_json"]),
                passage_text=created["passage_text"],
                typed_text=created["typed_text"],
                active_duration_ms=created["active_duration_ms"],
                end_reason=created["end_reason"],
                client=json.loads(created["client_json"]),
                layout_hint=created["layout_hint"],
                analysis_version=created["analysis_version"],
                metrics=_reconstruct_metrics(metrics_row, warnings),
                warnings=warnings,
            )
        finally:
            connection.close()

    def count(self) -> int:
        """Return the number of stored sessions."""
        connection = self._connect()
        try:
            return connection.execute(
                "SELECT COUNT(*) FROM sessions"
            ).fetchone()[0]
        finally:
            connection.close()

    def list_sessions(
        self,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[SessionSummary], int]:
        """Return a newest-first page of sessions with the exact total.

        The total reflects the whole stored set, independent of pagination.
        """
        connection = self._connect()
        try:
            total = connection.execute(
                "SELECT COUNT(*) FROM sessions"
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT s.id, s.created_at, s.mode, s.duration_limit_ms, "
                "s.active_duration_ms, s.end_reason, m.net_wpm, m.accuracy_pct, "
                "m.consistency_score "
                "FROM sessions s "
                "JOIN session_metrics m ON m.session_id = s.id "
                "ORDER BY s.created_at DESC, s.id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            summaries = [
                SessionSummary(
                    session_id=row["id"],
                    created_at=row["created_at"],
                    mode=row["mode"],
                    duration_limit_ms=row["duration_limit_ms"],
                    active_duration_ms=row["active_duration_ms"],
                    end_reason=row["end_reason"],
                    net_wpm=row["net_wpm"],
                    accuracy_pct=row["accuracy_pct"],
                    consistency_score=row["consistency_score"],
                )
                for row in rows
            ]
            return summaries, total
        finally:
            connection.close()

    def list_progress(self, limit: int | None) -> list[ProgressPoint]:
        """Return the most recent ``limit`` sessions for the progress charts.

        Rows come back oldest first so the chart's x axis runs forward in time.
        The newest rows are selected in SQL, then reversed; ``None`` means all
        sessions (SQLite's ``LIMIT -1``).
        """
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT s.id, s.created_at, s.mode, s.duration_limit_ms, "
                "m.net_wpm, m.accuracy_pct "
                "FROM sessions s "
                "JOIN session_metrics m ON m.session_id = s.id "
                "ORDER BY s.created_at DESC, s.id DESC LIMIT ?",
                (-1 if limit is None else limit,),
            ).fetchall()
            return [
                ProgressPoint(
                    session_id=row["id"],
                    created_at=row["created_at"],
                    mode=row["mode"],
                    duration_limit_ms=row["duration_limit_ms"],
                    net_wpm=row["net_wpm"],
                    accuracy_pct=row["accuracy_pct"],
                )
                for row in reversed(rows)
            ]
        finally:
            connection.close()

    def list_export_rows(self) -> list[SessionExportRow]:
        """Return every stored session in the ``sessions.csv`` export shape.

        Newest first, matching the history list, so the download reads in the
        same order as the UI. The export covers the whole set (no paging).
        """
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT s.id AS session_id, s.created_at, s.mode, "
                "s.duration_limit_ms, s.active_duration_ms, s.end_reason, "
                "m.gross_wpm, m.net_wpm, m.accuracy_pct, m.final_accuracy_pct, "
                "m.total_keystrokes, m.correct_keystrokes, "
                "m.incorrect_keystrokes, m.backspace_count "
                "FROM sessions s "
                "JOIN session_metrics m ON m.session_id = s.id "
                "ORDER BY s.created_at DESC, s.id DESC"
            ).fetchall()
            return [
                SessionExportRow(
                    session_id=row["session_id"],
                    created_at=row["created_at"],
                    mode=row["mode"],
                    duration_limit_ms=row["duration_limit_ms"],
                    active_duration_ms=row["active_duration_ms"],
                    end_reason=row["end_reason"],
                    gross_wpm=row["gross_wpm"],
                    net_wpm=row["net_wpm"],
                    accuracy_pct=row["accuracy_pct"],
                    final_accuracy_pct=row["final_accuracy_pct"],
                    total_keystrokes=row["total_keystrokes"],
                    correct_keystrokes=row["correct_keystrokes"],
                    incorrect_keystrokes=row["incorrect_keystrokes"],
                    backspace_count=row["backspace_count"],
                )
                for row in rows
            ]
        finally:
            connection.close()

    def get_key_stats(self, session_id: str) -> list[SessionKeyStat]:
        """Return one session's additive per-key sums, ordered by key code."""
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT key_code, attempts, errors, dwell_count, "
                "dwell_sum_ms, iki_count, iki_sum_ms "
                "FROM session_key_stats WHERE session_id = ? "
                "ORDER BY key_code",
                (session_id,),
            ).fetchall()
            return [
                SessionKeyStat(
                    key_code=row["key_code"],
                    attempts=row["attempts"],
                    errors=row["errors"],
                    dwell_count=row["dwell_count"],
                    dwell_sum_ms=row["dwell_sum_ms"],
                    iki_count=row["iki_count"],
                    iki_sum_ms=row["iki_sum_ms"],
                )
                for row in rows
            ]
        finally:
            connection.close()
