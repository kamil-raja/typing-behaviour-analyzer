"""CSV serialisation for stored session data.

Responsibility: turn repository read shapes into the documented download
bodies. This module contains no SQL, no HTTP and no metric math — every value
is passed through unchanged from ``app/repository.py``.

The sessions export follows blueprint §10 exactly: UTF-8 with a BOM, the fixed
column order below, NULL metrics as empty cells, and a leading ``'`` on any
cell that starts with ``= + - @`` so spreadsheet software never evaluates it
as a formula.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from app.repository import SessionExportRow

SESSIONS_FILENAME = "sessions.csv"
SESSIONS_COLUMNS: tuple[str, ...] = (
    "session_id",
    "created_at",
    "mode",
    "duration_limit_ms",
    "active_duration_ms",
    "end_reason",
    "gross_wpm",
    "net_wpm",
    "accuracy_pct",
    "final_accuracy_pct",
    "total_keystrokes",
    "correct_keystrokes",
    "incorrect_keystrokes",
    "backspace_count",
)

# RFC 4180 line endings; utf-8-sig writes the BOM spreadsheet apps expect.
_LINE_TERMINATOR = "\r\n"
_ENCODING = "utf-8-sig"
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _safe_cell(value: object) -> str:
    """Render one cell: NULL is empty, formula-like text is neutralised."""
    if value is None:
        return ""
    text = str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return f"'{text}"
    return text


def sessions_csv(rows: Sequence[SessionExportRow]) -> bytes:
    """Serialise stored sessions as a UTF-8 (BOM) CSV download body."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator=_LINE_TERMINATOR)
    writer.writerow(SESSIONS_COLUMNS)
    for row in rows:
        writer.writerow(
            [_safe_cell(getattr(row, column)) for column in SESSIONS_COLUMNS]
        )
    return buffer.getvalue().encode(_ENCODING)
