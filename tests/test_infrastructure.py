"""Checks for the shared fixtures and the frontend foundation."""

import sqlite3

import pytest
from flask import Flask, render_template
from flask.testing import FlaskClient


def test_app_and_client_fixtures(app: Flask, client: FlaskClient) -> None:
    """The app fixture is in testing mode and the client can call it."""
    assert app.config["TESTING"] is True
    response = client.get("/")
    assert response.status_code == 200
    assert b'id="passage-viewport"' in response.data


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


def test_base_template_renders_theme_foundation(app: Flask) -> None:
    """base.html renders the shell with theme bootstrapping before CSS."""
    with app.test_request_context("/"):
        html = render_template("base.html")

    assert '<html lang="en" data-theme="light">' in html
    assert 'class="skip-link"' in html
    assert 'aria-label="Primary"' in html
    assert "data-theme-toggle" in html
    assert 'href="/analytics"' in html
    assert 'href="/keyboard"' in html
    assert 'href="/history"' in html

    script_index = html.index('localStorage.getItem("tba-theme")')
    tokens_index = html.index("css/tokens.css")
    base_index = html.index("css/base.css")
    assert script_index < tokens_index < base_index

    assert "http://" not in html
    assert "https://" not in html


def test_frontend_assets_resolve(client: FlaskClient) -> None:
    """Every vendored frontend asset is served locally."""
    text_assets = [
        "/static/css/tokens.css",
        "/static/css/base.css",
        "/static/css/test.css",
        "/static/css/components.css",
        "/static/css/keyboard.css",
        "/static/js/theme.js",
        "/static/js/capture.js",
        "/static/js/typing-engine.js",
        "/static/js/test-page.js",
        "/static/js/results-page.js",
        "/static/js/history-page.js",
        "/static/js/analytics-page.js",
        "/static/js/charts.js",
        "/static/js/keyboard-heatmap.js",
        "/static/fonts/OFL-Lexend.txt",
        "/static/fonts/OFL-JetBrainsMono.txt",
    ]
    for path in text_assets:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.data, path

    font_assets = [
        "/static/fonts/lexend-latin-variable.woff2",
        "/static/fonts/jetbrains-mono-latin-variable.woff2",
    ]
    for path in font_assets:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.data[:4] == b"wOF2", path

    chart = client.get("/static/vendor/chart.umd.min.js")
    assert chart.status_code == 200
    assert chart.data.startswith(b"/*!")
    assert b"Chart.js v4" in chart.data[:200]
