"""Flask application factory for the Typing Behaviour Analyzer."""

from flask import Flask

from . import config
from .texts import validate_text_sources


def create_app() -> Flask:
    """Create and configure the Flask application.

    Text sources are checked before the app is returned so invalid content
    fails startup loudly (``docs/EVENT_SCHEMA.md`` §9).
    """
    app = Flask(__name__)
    app.config.from_object(config)
    validate_text_sources()
    return app
