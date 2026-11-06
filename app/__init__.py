"""Flask application factory for the Typing Behaviour Analyzer."""

from flask import Flask

from . import config
from .routes.api import api_bp
from .routes.pages import pages_bp
from .texts import validate_text_sources


def create_app() -> Flask:
    """Create and configure the Flask application.

    Text sources are checked before the app is returned so invalid content
    fails startup loudly (``docs/EVENT_SCHEMA.md`` §9).
    """
    app = Flask(__name__)
    app.config.from_object(config)
    validate_text_sources()
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)
    return app
