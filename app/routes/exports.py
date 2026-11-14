"""CSV download routes.

The route reads stored rows through the repository, hands them to
``app.exporters`` for serialisation, and sets the download headers. It contains
no SQL and no CSV formatting.
"""

from __future__ import annotations

from flask import Blueprint, Response, current_app

from ..exporters import SESSIONS_FILENAME, sessions_csv
from ..repository import STORE_EXTENSION_KEY, SessionRepository

exports_bp = Blueprint("exports", __name__, url_prefix="/api/export")


@exports_bp.get("/sessions.csv")
def export_sessions_csv() -> Response:
    """Return every stored session as a UTF-8 (BOM) CSV attachment."""
    repository: SessionRepository = current_app.extensions[STORE_EXTENSION_KEY]
    return Response(
        sessions_csv(repository.list_export_rows()),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{SESSIONS_FILENAME}"'
        },
    )
