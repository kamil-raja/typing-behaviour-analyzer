"""Route tests for the page and text-resolution API endpoints.

The contracts are fixed by ADR-029: the passage list carries a text_ref and a
short display label, single passages carry their text body, and the words
endpoint picks the seed and returns deterministic text.
"""

from __future__ import annotations

import re

import pytest
from flask.testing import FlaskClient

from app.texts import generate_words, get_passage, get_passages

PRINTABLE_ASCII = re.compile(r"[\x20-\x7E]")
LABEL_LENGTH = 40


def _expected_label(text: str) -> str:
    label = text[:LABEL_LENGTH].rstrip()
    if len(text) > LABEL_LENGTH:
        label = f"{label}..."
    return label


def test_home_page_serves_typing_screen(client: FlaskClient) -> None:
    """GET / renders the typing test page and its module entry points."""
    response = client.get("/")

    assert response.status_code == 200
    assert response.content_type.startswith("text/html")
    html = response.get_data(as_text=True)
    assert 'id="passage-viewport"' in html
    assert 'aria-label="Typing area. Start typing to begin. Press Escape to restart."' in html
    assert "js/test-page.js" in html
    assert "css/test.css" in html
    assert "data-word-counts" in html


def test_passage_list_returns_frozen_order_and_labels(
    client: FlaskClient,
) -> None:
    """The list endpoint returns text_refs and labels without text bodies."""
    response = client.get("/api/texts/passages")

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    passages = payload["passages"]
    stored = get_passages()

    assert len(passages) == len(stored)
    assert [item["text_ref"]["id"] for item in passages] == [
        passage.id for passage in stored
    ]

    for item, passage in zip(passages, stored):
        assert item["text_ref"] == {"type": "passage", "id": passage.id}
        assert item["label"] == _expected_label(passage.text)
        assert "text" not in item


def test_single_passage_returns_text_ref_and_body(client: FlaskClient) -> None:
    """A known passage id resolves to its reference and full text."""
    response = client.get("/api/texts/passages/p_001")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["text_ref"] == {"type": "passage", "id": "p_001"}
    assert payload["text"] == get_passage("p_001")
    assert all(PRINTABLE_ASCII.fullmatch(character) for character in payload["text"])


def test_unknown_passage_returns_documented_error(client: FlaskClient) -> None:
    """An unknown passage id is a 404 TEXT_NOT_FOUND error."""
    response = client.get("/api/texts/passages/p_999")

    assert response.status_code == 404
    payload = response.get_json()
    assert payload["error"]["code"] == "TEXT_NOT_FOUND"
    assert payload["error"]["message"]
    assert payload["error"]["details"][0]["field"] == "text_ref.id"


def test_words_endpoint_returns_seed_and_deterministic_text(
    client: FlaskClient,
) -> None:
    """The words endpoint picks the seed and returns its generated text."""
    response = client.get("/api/texts/words?count=10")

    assert response.status_code == 200
    payload = response.get_json()
    text_ref = payload["text_ref"]

    assert text_ref["type"] == "words"
    assert isinstance(text_ref["seed"], int)
    assert text_ref["seed"] >= 0
    assert text_ref["count"] == 10
    assert payload["text"] == generate_words(text_ref["seed"], 10)
    assert len(payload["text"].split(" ")) == 10
    assert all(PRINTABLE_ASCII.fullmatch(character) for character in payload["text"])


@pytest.mark.parametrize("count", [10, 200, 400])
def test_words_endpoint_accepts_documented_bounds(
    client: FlaskClient,
    count: int,
) -> None:
    """Counts inside the documented 10–400 range are accepted."""
    response = client.get(f"/api/texts/words?count={count}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["text_ref"]["count"] == count
    assert len(payload["text"].split(" ")) == count


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?count=",
        "?count=9",
        "?count=0",
        "?count=401",
        "?count=1000",
        "?count=ten",
        "?count=10.5",
        "?count=-10",
        "?count=%2010",
    ],
)
def test_words_endpoint_rejects_invalid_counts(
    client: FlaskClient,
    query: str,
) -> None:
    """Invalid or missing counts are 422 VALIDATION_ERROR with a count field."""
    response = client.get(f"/api/texts/words{query}")

    assert response.status_code == 422
    payload = response.get_json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["details"][0]["field"] == "count"
