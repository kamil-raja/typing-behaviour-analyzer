"""Flask application factory for the Typing Behaviour Analyzer."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Flask

from . import config
from .db import init_db
from .repository import STORE_EXTENSION_KEY, SessionRepository
from .routes.api import api_bp
from .routes.exports import exports_bp
from .routes.pages import pages_bp
from .texts import validate_text_sources


def create_app(test_config: Mapping[str, Any] | None = None) -> Flask:
    """Create and configure the Flask application.

    Text sources are checked before the app is returned so invalid content
    fails startup loudly (``docs/EVENT_SCHEMA.md`` §9). The database defaults
    to ``instance/typing.db``; ``test_config`` lets tests point ``DATABASE`` at
    a temporary file. The repository owns every SQL statement (P0-D2-02).
    """
    app = Flask(__name__)
    app.config.from_object(config)
    app.config.setdefault(
        "DATABASE",
        str(Path(app.instance_path) / "typing.db"),
    )
    if test_config is not None:
        app.config.from_mapping(test_config)

    validate_text_sources()
    app.extensions[STORE_EXTENSION_KEY] = SessionRepository(app.config["DATABASE"])
    init_db(app)
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(exports_bp)
    return app
