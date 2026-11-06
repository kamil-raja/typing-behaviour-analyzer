"""HTML page routes.

Routes only render templates. Text content is fetched by the page modules from
the JSON API so the browser never receives data it cannot display explicitly.
"""

from flask import Blueprint, render_template

from ..config import WORDS_FOR_DURATION_MS

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def test_page() -> str:
    """Render the typing test screen."""
    return render_template("test.html", word_counts=WORDS_FOR_DURATION_MS)
