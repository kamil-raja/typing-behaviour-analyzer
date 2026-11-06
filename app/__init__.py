"""Flask application factory for the Typing Behaviour Analyzer."""

from flask import Flask

from . import config


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config)
    return app
