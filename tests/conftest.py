"""Shared pytest fixtures for the Typing Behaviour Analyzer test suite."""

import sqlite3
from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app


@pytest.fixture()
def app() -> Iterator[Flask]:
    """Create a Flask application configured for testing."""
    application = create_app()
    application.config.update(TESTING=True)
    yield application


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    """Return a Flask test client bound to the test application."""
    return app.test_client()


@pytest.fixture()
def db_conn() -> Iterator[sqlite3.Connection]:
    """Yield an in-memory SQLite connection for tests.

    P0-D1-02 establishes only the fixture. The schema and the application
    connection factory belong to P0-D2-01, so this fixture creates no tables.
    """
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()
