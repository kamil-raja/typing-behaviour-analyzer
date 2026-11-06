"""In-memory session storage for the first vertical slice.

Responsibility: retain one analysed session so ``POST /api/sessions`` can return
a session id and the results page can render the server-computed numbers. This
module is a temporary stand-in for ``app/repository.py`` (P0-D2-02). It contains
no metric math, no SQL and no HTTP handling.

The store is attached to the Flask application as
``app.extensions["tba_session_store"]`` so every application instance owns an
isolated store, which keeps tests independent and avoids module-level global
state. Records live only for the life of the process (ADR-032).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from app.engine import SessionAnalysis
from app.validators import ValidatedSessionPayload

STORE_EXTENSION_KEY = "tba_session_store"


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a ``Z`` suffix."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class StoredSession:
    """One submitted session and its authoritative analysis.

    The field names mirror the eventual ``sessions`` row plus the in-memory
    ``analysis`` object. Raw events remain inside ``analysis.replay``; the
    in-memory store keeps them unmodified for this milestone.
    """

    session_id: str
    created_at: str
    schema_version: int
    mode: str
    duration_limit_ms: int | None
    text_ref: Mapping[str, Any]
    started_at: str
    client: Mapping[str, Any]
    ignored: Mapping[str, int]
    analysis: SessionAnalysis


class InMemorySessionStore:
    """A thread-safe, process-local session store.

    P0-D2-02 replaces this class with the SQLite repository. Until then the
    interface is intentionally small: ``create``, ``get``, ``count`` and
    ``clear``.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, StoredSession] = {}
        self._lock = Lock()

    def create(
        self,
        payload: ValidatedSessionPayload,
        analysis: SessionAnalysis,
    ) -> StoredSession:
        """Store one analysed payload and return the stored record."""
        session = StoredSession(
            session_id=uuid4().hex,
            created_at=_utc_now_iso(),
            schema_version=payload.schema_version,
            mode=payload.mode,
            duration_limit_ms=payload.duration_limit_ms,
            text_ref=payload.text_ref,
            started_at=payload.started_at,
            client=payload.client,
            ignored=payload.ignored,
            analysis=analysis,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> StoredSession | None:
        """Return the stored session for ``session_id``, or ``None``."""
        with self._lock:
            return self._sessions.get(session_id)

    def count(self) -> int:
        """Return the number of stored sessions."""
        with self._lock:
            return len(self._sessions)

    def clear(self) -> None:
        """Remove every stored session (used by tests)."""
        with self._lock:
            self._sessions.clear()
