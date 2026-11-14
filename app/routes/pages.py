"""HTML page routes.

Routes only render templates. Text content is fetched by the page modules from
the JSON API; the results page reads the persisted session record created by
``POST /api/sessions`` through ``app.repository``.
"""

from flask import Blueprint, abort, current_app, render_template

from ..config import HISTORY_PAGE_SIZE, WORDS_FOR_DURATION_MS
from ..repository import STORE_EXTENSION_KEY, SessionRecord, SessionRepository

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def test_page() -> str:
    """Render the typing test screen."""
    return render_template("test.html", word_counts=WORDS_FOR_DURATION_MS)


@pages_bp.get("/history")
def history_page() -> str:
    """Render the paginated session history screen."""
    return render_template("history.html", page_size=HISTORY_PAGE_SIZE)


@pages_bp.get("/results/<session_id>")
def results_page(session_id: str) -> str:
    """Render the persisted server-computed results for one session."""
    repository: SessionRepository = current_app.extensions[STORE_EXTENSION_KEY]
    session = repository.get(session_id)
    if session is None:
        abort(404)

    return render_template(
        "results.html",
        session=session,
        metrics=session.metrics,
        warnings=session.warnings,
        analysis_version=session.analysis_version,
    )
