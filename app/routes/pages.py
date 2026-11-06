"""HTML page routes.

Routes only render templates. Text content is fetched by the page modules from
the JSON API; the results page reads the authoritative analysis from the
in-memory session store created by ``POST /api/sessions``.

P0-D2-03 replaces the store lookup with the persisted session repository.
"""

from flask import Blueprint, abort, current_app, render_template

from ..config import ANALYSIS_VERSION, WORDS_FOR_DURATION_MS
from ..session_store import STORE_EXTENSION_KEY, InMemorySessionStore

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def test_page() -> str:
    """Render the typing test screen."""
    return render_template("test.html", word_counts=WORDS_FOR_DURATION_MS)


@pages_bp.get("/results/<session_id>")
def results_page(session_id: str) -> str:
    """Render the server-computed results for one stored session."""
    store: InMemorySessionStore = current_app.extensions[STORE_EXTENSION_KEY]
    session = store.get(session_id)
    if session is None:
        abort(404)

    return render_template(
        "results.html",
        session=session,
        metrics=session.analysis.metrics,
        replay=session.analysis.replay,
        warnings=session.analysis.warnings,
        analysis_version=ANALYSIS_VERSION,
    )
