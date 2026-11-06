"""Text resolution for the Typing Behaviour Analyzer.

Responsibility: turn a structurally validated ``text_ref`` into the exact text
the engine replays against. This module owns the two frozen data sources
(``app/data/passages.json`` and ``app/data/words_en.json``), the deterministic
word generator and the startup ASCII check. It performs no HTTP calls, no
database access and no metric calculations.

Unknown passage ids raise :class:`TextNotFoundError`, which routes translate to
the documented ``TEXT_NOT_FOUND`` response. Malformed JavaScript is never
accepted here: the validator owns payload shape, so an unsupported ``text_ref``
type is a programming error.
"""

from __future__ import annotations

import json
import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from app.config import WORD_COUNT_MAX, WORD_COUNT_MIN, WORDS_FOR_DURATION_MS
from app.errors import TEXT_NOT_FOUND

DATA_DIR: Final = Path(__file__).resolve().parent / "data"
PASSAGES_PATH: Final = DATA_DIR / "passages.json"
WORDS_PATH: Final = DATA_DIR / "words_en.json"

_PRINTABLE_ASCII: Final = re.compile(r"[\x20-\x7E]")
_LOWERCASE_WORD: Final = re.compile(r"[a-z]+")


class TextSourceError(RuntimeError):
    """A text source violates the documented structure or ASCII contract.

    Raised during ``create_app()`` so the application refuses to start with
    untypeable content, as required by ``docs/EVENT_SCHEMA.md`` §9.
    """


class TextNotFoundError(LookupError):
    """An unknown passage id, reported as the documented ``TEXT_NOT_FOUND``."""

    code = TEXT_NOT_FOUND
    status = 404

    def __init__(
        self,
        message: str,
        details: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = list(details or [])


@dataclass(frozen=True)
class Passage:
    """One frozen passage source entry."""

    id: str
    text: str


def _read_json(path: Path) -> object:
    """Read one JSON file, converting I/O and parse failures into startup errors."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TextSourceError(f"cannot read {path.name}: {error}") from error
    except json.JSONDecodeError as error:
        raise TextSourceError(f"{path.name} is not valid JSON: {error}") from error


def _parse_passages(raw: object) -> tuple[Passage, ...]:
    """Validate the passages JSON shape and return frozen entries."""
    if not isinstance(raw, list) or not raw:
        raise TextSourceError("passages.json must be a non-empty JSON array")

    passages: list[Passage] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise TextSourceError(
                f"passages.json[{index}] must be a JSON object"
            )
        passage_id = item.get("id")
        text = item.get("text")
        if not isinstance(passage_id, str) or not passage_id:
            raise TextSourceError(
                f"passages.json[{index}].id must be a non-empty string"
            )
        if not isinstance(text, str) or not text:
            raise TextSourceError(
                f"passages.json[{index}].text must be a non-empty string"
            )
        if passage_id in seen:
            raise TextSourceError(
                f"passages.json contains duplicate id {passage_id!r}"
            )
        seen.add(passage_id)
        passages.append(Passage(id=passage_id, text=text))
    return tuple(passages)


def _parse_words(raw: object) -> tuple[str, ...]:
    """Validate the word-list JSON shape and return a frozen tuple."""
    if not isinstance(raw, list) or not raw:
        raise TextSourceError("words_en.json must be a non-empty JSON array")

    words: list[str] = []
    for index, word in enumerate(raw):
        if not isinstance(word, str) or not word:
            raise TextSourceError(
                f"words_en.json[{index}] must be a non-empty string"
            )
        words.append(word)
    return tuple(words)


@lru_cache(maxsize=1)
def get_passages() -> tuple[Passage, ...]:
    """Return all passages in source order (cached)."""
    return _parse_passages(_read_json(PASSAGES_PATH))


@lru_cache(maxsize=1)
def get_word_list() -> tuple[str, ...]:
    """Return the frozen source word list in order (cached)."""
    return _parse_words(_read_json(WORDS_PATH))


def get_passage(passage_id: str) -> str:
    """Return the text for ``passage_id`` or raise :class:`TextNotFoundError`."""
    for passage in get_passages():
        if passage.id == passage_id:
            return passage.text
    raise TextNotFoundError(
        f"Passage {passage_id!r} was not found.",
        [{"field": "text_ref.id", "problem": "does not match a known passage"}],
    )


def generate_words(seed: int, count: int) -> str:
    """Generate a deterministic word-mode text.

    The algorithm is frozen for reproducibility (ADR-027): shuffle a copy of the
    source word list with ``random.Random(seed)``, take the first ``count``
    words, and if ``count`` exceeds the list length, shuffle the same list again
    and append until enough words exist. Words are joined by one space.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("count must be an integer")
    if not WORD_COUNT_MIN <= count <= WORD_COUNT_MAX:
        raise ValueError(
            f"count must be between {WORD_COUNT_MIN} and {WORD_COUNT_MAX}"
        )

    words = list(get_word_list())
    rng = random.Random(seed)
    selected: list[str] = []
    while len(selected) < count:
        rng.shuffle(words)
        selected.extend(words)
    return " ".join(selected[:count])


def words_for_duration(duration_limit_ms: int) -> int:
    """Return the documented default word count for a time-mode duration."""
    if isinstance(duration_limit_ms, bool) or not isinstance(
        duration_limit_ms, int
    ):
        raise ValueError("duration_limit_ms must be an integer")
    try:
        return WORDS_FOR_DURATION_MS[duration_limit_ms]
    except KeyError:
        raise ValueError(
            f"unsupported duration_limit_ms: {duration_limit_ms}"
        ) from None


def resolve_text(text_ref: Mapping[str, Any]) -> str:
    """Resolve a validated ``text_ref`` mapping to the exact engine text."""
    ref_type = text_ref.get("type")
    if ref_type == "passage":
        passage_id = text_ref.get("id")
        if not isinstance(passage_id, str) or not passage_id:
            raise TextNotFoundError(
                "Passage id is invalid.",
                [{"field": "text_ref.id", "problem": "must be a known passage"}],
            )
        return get_passage(passage_id)
    if ref_type == "words":
        return generate_words(text_ref.get("seed"), text_ref.get("count"))
    raise ValueError(f"unsupported text_ref type: {ref_type!r}")


def _assert_printable_ascii(text: str, *, source: str) -> None:
    """Raise :class:`TextSourceError` on the first character outside 32-126."""
    for index, character in enumerate(text):
        if _PRINTABLE_ASCII.fullmatch(character) is None:
            raise TextSourceError(
                f"{source}: character U+{ord(character):04X} at index "
                f"{index} is outside ASCII 32-126"
            )


def validate_text_sources() -> None:
    """Assert every passage and word is typeable; called from ``create_app()``.

    This is a startup guard, not a request-time validator: it fails loudly so
    the application never serves content containing control characters or
    non-ASCII glyphs (``docs/EVENT_SCHEMA.md`` §9).
    """
    passages = get_passages()
    for passage in passages:
        _assert_printable_ascii(
            passage.text, source=f"passages.json[{passage.id}]"
        )

    words = get_word_list()
    for index, word in enumerate(words):
        _assert_printable_ascii(word, source=f"words_en.json[{index}]")
        if _LOWERCASE_WORD.fullmatch(word) is None:
            raise TextSourceError(
                f"words_en.json[{index}] must contain lowercase a-z only"
            )
