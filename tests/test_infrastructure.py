"""Checks for the shared pytest fixtures in ``conftest.py``."""

import sqlite3

import pytest
from flask import Flask
from flask.testing import FlaskClient


def test_app_and_client_fixtures(app: Flask, client: FlaskClient) -> None:
    """The app fixture is in testing mode and the client can call it."""
    assert app.config["TESTING"] is True
    response = client.get("/")
    assert response.status_code == 404


def test_db_conn_fixture_enables_foreign_keys(db_conn: sqlite3.Connection) -> None:
    """The in-memory connection is usable and enforces foreign keys."""
    assert db_conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    db_conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
    db_conn.execute(
        "CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))"
    )
    db_conn.execute("INSERT INTO parent (id) VALUES (1)")
    db_conn.execute("INSERT INTO child (parent_id) VALUES (1)")
    assert db_conn.execute("SELECT COUNT(*) FROM child").fetchone()[0] == 1

    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute("INSERT INTO child (parent_id) VALUES (99)")
