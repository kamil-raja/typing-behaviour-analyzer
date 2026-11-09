"""SQLite connection management for the Typing Behaviour Analyzer.

Responsibility: create connections with the documented PRAGMAs, apply
``app/schema.sql`` on startup, and expose one connection per request through
Flask's ``g``. This module contains no SQL queries beyond schema
initialisation and no metric or HTTP logic. All application queries belong to
``app/repository.py`` (P0-D2-02).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask, current_app, g

# Schema identity tracked with PRAGMA user_version (blueprint §9).
SCHEMA_VERSION = 1

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(database: str) -> sqlite3.Connection:
    """Open ``database`` with row access by name and foreign keys enforced."""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def apply_schema(connection: sqlite3.Connection) -> None:
    """Create every table, index and constraint and record the schema version."""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, SCHEMA_VERSION):
        raise RuntimeError(
            f"database schema version {version} does not match expected "
            f"{SCHEMA_VERSION}; delete instance/typing.db during development"
        )

    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    # PRAGMA values cannot be parameterised; SCHEMA_VERSION is an internal int.
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    connection.commit()


def init_db(app: Flask) -> None:
    """Initialise the configured database and register request teardown."""
    database = app.config["DATABASE"]
    if database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)

    connection = connect(database)
    try:
        apply_schema(connection)
    finally:
        connection.close()

    app.teardown_appcontext(close_db)


def get_db() -> sqlite3.Connection:
    """Return this request's connection, opening it on first use."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exception: BaseException | None = None) -> None:
    """Close the request connection, if one was opened."""
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()
