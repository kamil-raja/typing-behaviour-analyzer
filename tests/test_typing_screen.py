"""Typing-screen polish contracts from `docs/UI_DESIGN.md` §4.

The browser layer has no JavaScript test runner because Node.js is banned
(AGENTS.md §2), so these tests pin the rendered markup and the shipped CSS/JS
contracts that the manual P0-D2-05 check depends on. They reach the real page
route and the real static files, not private helpers.
"""

from __future__ import annotations

import re
from pathlib import Path

from flask.testing import FlaskClient

ROOT = Path(__file__).resolve().parents[1]
HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _home(client: FlaskClient) -> str:
    response = client.get("/")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_config_strip_offers_the_documented_controls(
    client: FlaskClient,
) -> None:
    """Mode toggle, the three time options and the passage selector render."""
    html = _home(client)

    assert 'aria-label="Test configuration"' in html
    assert 'data-mode="time"' in html
    assert 'data-mode="passage"' in html
    for duration in ("15", "30", "60"):
        assert f'data-duration="{duration}"' in html
    assert 'id="passage-select"' in html
    assert "<select" in html
    assert 'id="duration-group"' in html
    assert 'id="passage-group"' in html


def test_live_row_starts_hidden_and_is_labelled_provisional(
    client: FlaskClient,
) -> None:
    """The live row is hidden until the first keystroke and says provisional."""
    html = _home(client)
    live_row = html[html.index('id="live-row"') : html.index('id="passage-viewport"')]

    assert "hidden" in live_row
    assert "provisional" in live_row
    assert 'id="timer-value"' in live_row
    assert 'id="wpm-value"' in live_row
    assert 'id="accuracy-value"' in live_row


def test_passage_viewport_is_focusable_with_three_visible_lines(
    client: FlaskClient,
) -> None:
    """The viewport is a three-line, focusable region with the restart hint."""
    html = _home(client)
    viewport = html[html.index('id="passage-viewport"') : html.index('id="test-status"')]
    css = _read("app/static/css/test.css")

    assert 'tabindex="0"' in viewport
    assert 'aria-label="Typing area. Start typing to begin. Press Escape to restart."' in viewport
    assert "<kbd>esc</kbd> restart" in html

    assert (
        "height: calc(var(--font-size-passage) * var(--line-height-passage) * 3)"
        in css
    )
    assert "max-width: var(--passage-max-width)" in css
    assert "overflow: hidden" in css


def test_character_and_caret_states_use_design_tokens() -> None:
    """Untyped, correct, incorrect and caret each have a distinct token state."""
    css = _read("app/static/css/test.css")

    assert ".char {" in css
    assert "color: var(--text-muted)" in css
    assert ".char.is-correct" in css
    assert "color: var(--text)" in css
    assert ".char.is-incorrect" in css
    assert "background: var(--error-bg)" in css
    assert "color: var(--error)" in css
    assert "text-decoration: underline" in css

    assert ".caret {" in css
    assert "background: var(--accent)" in css
    assert "width: var(--caret-width)" in css
    assert "animation: tba-caret-blink" in css

    running_caret = re.search(
        r'\.passage-viewport\[data-state="running"\] \.caret \{(?P<body>[^}]*)\}',
        css,
    )
    assert running_caret is not None
    assert "animation: none" in running_caret.group("body")

    finished_caret = re.search(
        r'\.passage-viewport\[data-state="finished"\] \.caret \{(?P<body>[^}]*)\}',
        css,
    )
    assert finished_caret is not None
    assert "display: none" in finished_caret.group("body")

    assert not HEX_COLOUR.search(css), "test.css must use tokens, not hex colours"


def test_typing_engine_renders_states_and_unhides_the_live_row() -> None:
    """The engine owns state classes, the provisional row and the fix message."""
    source = _read("app/static/js/typing-engine.js")

    assert 'span.className = "char"' in source
    assert '"is-correct"' in source
    assert '"is-incorrect"' in source
    assert "liveRow.hidden = true" in source
    assert "liveRow.hidden = false" in source
    assert 'FIX_MESSAGE = "Fix the highlighted characters to finish"' in source
    assert "setMessage(FIX_MESSAGE" in source


def test_caret_is_anchored_to_the_second_visible_line() -> None:
    """The caret follows the text line box and the track keeps it on line 2."""
    source = _read("app/static/js/typing-engine.js")

    assert "Math.round((top - spans[0].offsetTop) / safeLineHeight)" in source
    assert "const lineTop = lineIndex * safeLineHeight;" in source
    assert "Math.max(0, lineIndex - 1) * safeLineHeight" in source
    assert "track.style.transform = `translateY(-${shift}px)`" in source


def test_focus_is_taken_on_load_and_after_config_changes() -> None:
    """loadCurrentText focuses the viewport by default and every config path
    calls it again."""
    source = _read("app/static/js/test-page.js")

    assert "async function loadCurrentText({ focus = true } = {})" in source
    assert "function focusViewport()" in source
    assert "focusViewport();" in source
    assert source.count("loadCurrentText();") >= 4
    assert "setStatus(\"Test cancelled. The window lost focus.\", \"warning\")" in source
