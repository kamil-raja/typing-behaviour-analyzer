"""JSON API routes for text resolution.

The endpoint contracts are fixed by ADR-029. Routes delegate to ``app.texts``
for every stored passage and generated word text; they contain no metric math.
"""

from __future__ import annotations

import re
import secrets

from flask import Blueprint, Response, jsonify, request

from ..config import WORD_COUNT_MAX, WORD_COUNT_MIN
from ..errors import VALIDATION_ERROR, json_error
from ..texts import TextNotFoundError, generate_words, get_passage, get_passages

api_bp = Blueprint("api", __name__, url_prefix="/api")

PASSAGE_LABEL_LENGTH = 40
_COUNT_PATTERN = re.compile(r"[0-9]{1,3}")
_SEED_LIMIT = 2**31


def _passage_text_ref(passage_id: str) -> dict[str, str]:
    """Return the canonical text_ref object for a passage."""
    return {"type": "passage", "id": passage_id}


def _passage_label(text: str) -> str:
    """Return the first 40 characters of a passage as ASCII UI label text."""
    label = text[:PASSAGE_LABEL_LENGTH].rstrip()
    if len(text) > PASSAGE_LABEL_LENGTH:
        label = f"{label}..."
    return label


def _invalid_count(problem: str) -> tuple[Response, int]:
    """Return the documented validation error for the words endpoint."""
    return json_error(
        VALIDATION_ERROR,
        "The count query parameter is invalid.",
        [{"field": "count", "problem": problem}],
        status=422,
    )


@api_bp.get("/texts/passages")
def list_passages() -> Response:
    """List every passage in frozen source order with a display label."""
    passages = get_passages()
    return jsonify(
        {
            "passages": [
                {
                    "text_ref": _passage_text_ref(passage.id),
                    "label": _passage_label(passage.text),
                }
                for passage in passages
            ]
        }
    )


@api_bp.get("/texts/passages/<passage_id>")
def get_passage_text(passage_id: str) -> Response | tuple[Response, int]:
    """Return one passage's text_ref and text body."""
    try:
        text = get_passage(passage_id)
    except TextNotFoundError as error:
        return json_error(
            error.code,
            error.message,
            error.details,
            status=error.status,
        )
    return jsonify(
        {
            "text_ref": _passage_text_ref(passage_id),
            "text": text,
        }
    )


@api_bp.get("/texts/words")
def get_word_text() -> Response | tuple[Response, int]:
    """Generate deterministic word-mode text and return the chosen seed."""
    raw_count = request.args.get("count")
    if raw_count is None:
        return _invalid_count("is required")

    if _COUNT_PATTERN.fullmatch(raw_count) is None:
        return _invalid_count(
            f"must be an integer between {WORD_COUNT_MIN} and {WORD_COUNT_MAX}"
        )

    count = int(raw_count)
    if not WORD_COUNT_MIN <= count <= WORD_COUNT_MAX:
        return _invalid_count(
            f"must be an integer between {WORD_COUNT_MIN} and {WORD_COUNT_MAX}"
        )

    seed = secrets.randbelow(_SEED_LIMIT)
    return jsonify(
        {
            "text_ref": {"type": "words", "seed": seed, "count": count},
            "text": generate_words(seed, count),
        }
    )
