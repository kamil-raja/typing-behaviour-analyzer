"""Text resolution tests for passages, the word list and startup validation.

The cases follow ``docs/EVENT_SCHEMA.md`` §9 and the P0-D1-07 list in
``docs/TASKS.md``. They lock the content contract (ASCII-only, frozen ordering),
the documented deterministic generator, duration sizing, unknown-passage
handling and the startup guard wired into ``create_app()``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

import app as app_package
from app import texts
from app.config import (
    WORD_COUNT_MAX,
    WORD_COUNT_MIN,
    WORDS_FOR_DURATION_MS,
)
from app.engine import analyze_session
from app.errors import TEXT_NOT_FOUND
from app.texts import (
    Passage,
    TextNotFoundError,
    TextSourceError,
    generate_words,
    get_passage,
    get_passages,
    get_word_list,
    resolve_text,
    validate_text_sources,
    words_for_duration,
)

PRINTABLE_ASCII = re.compile(r"[\x20-\x7E]")


@pytest.fixture(autouse=True)
def clear_text_caches() -> Iterator[None]:
    """Keep the cached loaders isolated from path/monkeypatch changes."""
    get_passages.cache_clear()
    get_word_list.cache_clear()
    yield
    get_passages.cache_clear()
    get_word_list.cache_clear()


# --- Content contract -----------------------------------------------------


def test_passage_source_has_twelve_ordered_unique_ids() -> None:
    """The frozen source ships ~12 passages with stable sequential ids."""
    passages = get_passages()

    assert len(passages) == 12
    assert [passage.id for passage in passages] == [
        f"p_{index:03d}" for index in range(1, 13)
    ]
    assert len({passage.id for passage in passages}) == len(passages)


def test_every_passage_character_is_printable_ascii() -> None:
    """No newlines, tabs, control characters or non-ASCII glyphs are typeable."""
    for passage in get_passages():
        for index, character in enumerate(passage.text):
            assert PRINTABLE_ASCII.fullmatch(character) is not None, (
                f"{passage.id} index {index} is U+{ord(character):04X}"
            )


def test_passage_texts_are_reasonable_lengths() -> None:
    """Passages are long enough to type and short enough to display."""
    for passage in get_passages():
        assert 150 <= len(passage.text) <= 400, passage.id


def test_passage_texts_have_no_edge_whitespace() -> None:
    """Leading or trailing spaces would render as invisible typing targets."""
    for passage in get_passages():
        assert passage.text == passage.text.strip(), passage.id
        assert "  " not in passage.text, passage.id


def test_word_list_is_two_hundred_unique_words() -> None:
    """The frozen source has exactly 200 entries and no duplicates."""
    words = get_word_list()

    assert len(words) == 200
    assert len(set(words)) == len(words)


def test_word_list_entries_are_lowercase_ascii_letters() -> None:
    """Every word is a plain lowercase a-z token with no punctuation."""
    for word in get_word_list():
        assert re.fullmatch(r"[a-z]+", word) is not None, word


def test_startup_validation_accepts_the_real_sources() -> None:
    """The shipped content passes the guard installed in ``create_app()``."""
    validate_text_sources()


# --- Deterministic word generation ---------------------------------------


def test_generate_words_is_deterministic_for_a_seed() -> None:
    """The same seed always produces the same text."""
    first = generate_words(482_913, 120)
    second = generate_words(482_913, 120)

    assert first == second


def test_generated_first_ten_words_are_frozen() -> None:
    """Freeze the seed mapping; changing list order would break stored sessions."""
    assert generate_words(482_913, 10) == (
        "back kept enjoy held pass sat run two finish all"
    )


def test_generate_words_differs_between_seeds() -> None:
    """Different seeds produce different orderings."""
    assert generate_words(1, 120) != generate_words(2, 120)


@pytest.mark.parametrize(
    "count",
    [WORD_COUNT_MIN, 120, 200, 350, WORD_COUNT_MAX],
)
def test_generate_words_respects_the_requested_count(count: int) -> None:
    """The output contains exactly ``count`` tokens."""
    text = generate_words(7, count)

    assert len(text.split(" ")) == count


@pytest.mark.parametrize("count", [10, 200, 350, 400])
def test_generated_words_come_from_the_source_list(count: int) -> None:
    """Generation only reorders existing words, it never invents them."""
    source = set(get_word_list())

    assert set(generate_words(11, count).split(" ")) <= source


def test_generate_words_cycles_when_count_exceeds_the_list() -> None:
    """350- and 400-word texts extend beyond the 200-word source."""
    text = generate_words(3, 350)
    words = text.split(" ")

    assert len(words) == 350
    assert len(set(words)) < len(words)


def test_generate_words_uses_single_spaces_without_edges() -> None:
    """Word-mode text is a clean space-joined sequence."""
    text = generate_words(13, 120)

    assert text == text.strip()
    assert "  " not in text


def test_generation_is_stable_across_cache_clears() -> None:
    """Reloading the source does not change a seed mapping."""
    first = generate_words(99, 200)
    get_passages.cache_clear()
    get_word_list.cache_clear()

    assert generate_words(99, 200) == first


@pytest.mark.parametrize(
    "count",
    [WORD_COUNT_MIN - 1, WORD_COUNT_MAX + 1, None, "10", 10.0, True],
)
def test_generate_words_rejects_invalid_counts(count: object) -> None:
    """Counts outside 10..400 or of the wrong type are programming errors."""
    with pytest.raises(ValueError):
        generate_words(1, count)  # type: ignore[arg-type]


@pytest.mark.parametrize("seed", [None, "1", 1.0, True])
def test_generate_words_rejects_invalid_seeds(seed: object) -> None:
    """Seeds must be real integers, not booleans or numeric strings."""
    with pytest.raises(ValueError):
        generate_words(seed, 10)  # type: ignore[arg-type]


def test_generated_text_is_printable_ascii_for_every_seed() -> None:
    """Generated text is always typeable regardless of seed."""
    for seed in (0, 1, 42, 482_913, -7):
        text = generate_words(seed, WORD_COUNT_MAX)
        assert all(PRINTABLE_ASCII.fullmatch(char) for char in text)


# --- Duration sizing -----------------------------------------------------


@pytest.mark.parametrize(
    ("duration_limit_ms", "expected"),
    [(15_000, 120), (30_000, 200), (60_000, 350)],
)
def test_documented_duration_sizing(duration_limit_ms: int, expected: int) -> None:
    """The blueprint's time-mode word counts are honoured exactly."""
    assert words_for_duration(duration_limit_ms) == expected


def test_duration_sizing_covers_every_allowed_limit() -> None:
    """The sizing table and the validator's allowed limits stay in sync."""
    from app.config import ALLOWED_TIME_LIMITS_MS

    assert set(WORDS_FOR_DURATION_MS) == set(ALLOWED_TIME_LIMITS_MS)


@pytest.mark.parametrize("duration", [0, 20_000, None, "30000", True])
def test_unknown_durations_are_programming_errors(duration: object) -> None:
    """An unsupported duration never silently picks a default size."""
    with pytest.raises(ValueError):
        words_for_duration(duration)  # type: ignore[arg-type]


# --- text_ref resolution -------------------------------------------------


def test_resolve_text_returns_the_requested_passage() -> None:
    """Passage refs resolve by id."""
    passage = get_passages()[2]

    assert resolve_text({"type": "passage", "id": passage.id}) == passage.text


def test_every_passage_can_be_resolved_by_id() -> None:
    """Every shipped id is reachable through the public resolver."""
    for passage in get_passages():
        assert get_passage(passage.id) == passage.text


def test_resolve_text_generates_words_for_a_seed() -> None:
    """Word refs use the documented deterministic generator."""
    assert resolve_text(
        {"type": "words", "seed": 482_913, "count": 120}
    ) == generate_words(482_913, 120)


def test_unknown_passage_raises_text_not_found() -> None:
    """An unknown id is a 404 ``TEXT_NOT_FOUND``, not a 422 schema error."""
    with pytest.raises(TextNotFoundError) as info:
        resolve_text({"type": "passage", "id": "p_999"})

    error = info.value
    assert error.code == TEXT_NOT_FOUND
    assert error.status == 404
    assert "p_999" in error.message
    assert error.details[0]["field"] == "text_ref.id"


@pytest.mark.parametrize("passage_id", [None, 1, ""])
def test_invalid_passage_ids_raise_text_not_found(passage_id: object) -> None:
    """The resolver never coerces a malformed id into a lookup."""
    with pytest.raises(TextNotFoundError):
        resolve_text({"type": "passage", "id": passage_id})


def test_unknown_text_ref_type_is_a_programming_error() -> None:
    """Schema validation owns the enum; reaching here with another type is a bug."""
    with pytest.raises(ValueError):
        resolve_text({"type": "speech"})


# --- Startup guard -------------------------------------------------------


def test_startup_rejects_non_ascii_passage(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-ASCII passage character stops startup with its index."""
    monkeypatch.setattr(
        texts, "get_passages", lambda: (Passage("p_001", "caf\u00e9"),)
    )

    with pytest.raises(TextSourceError, match=r"U\+00E9"):
        validate_text_sources()


def test_startup_rejects_control_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Newlines and tabs are outside 32-126 and must fail."""
    monkeypatch.setattr(
        texts, "get_passages", lambda: (Passage("p_001", "line\nbreak"),)
    )

    with pytest.raises(TextSourceError, match=r"U\+000A"):
        validate_text_sources()


def test_startup_rejects_uppercase_words(monkeypatch: pytest.MonkeyPatch) -> None:
    """Word entries must be lowercase, even though uppercase is printable ASCII."""
    monkeypatch.setattr(texts, "get_word_list", lambda: ("the", "The"))

    with pytest.raises(TextSourceError, match="lowercase"):
        validate_text_sources()


def test_startup_rejects_non_ascii_words(monkeypatch: pytest.MonkeyPatch) -> None:
    """Word entries follow the same ASCII rule as passages."""
    monkeypatch.setattr(texts, "get_word_list", lambda: ("caf\u00e9",))

    with pytest.raises(TextSourceError, match=r"U\+00E9"):
        validate_text_sources()


def test_duplicate_passage_ids_are_rejected() -> None:
    """Duplicate ids would make resolution ambiguous."""
    with pytest.raises(TextSourceError, match="duplicate"):
        texts._parse_passages(
            [
                {"id": "p_001", "text": "first"},
                {"id": "p_001", "text": "second"},
            ]
        )


@pytest.mark.parametrize(
    "raw",
    [
        None,
        {},
        [],
        "passages",
        [1],
        [{"id": "", "text": "x"}],
        [{"id": "p_001"}],
        [{"id": "p_001", "text": 1}],
    ],
)
def test_malformed_passage_sources_are_rejected(raw: object) -> None:
    """The loader fails loudly on any structural deviation."""
    with pytest.raises(TextSourceError):
        texts._parse_passages(raw)


@pytest.mark.parametrize(
    "raw",
    [None, {}, [], "words", [1], [""]],
)
def test_malformed_word_sources_are_rejected(raw: object) -> None:
    """The word source must be a non-empty array of non-empty strings."""
    with pytest.raises(TextSourceError):
        texts._parse_words(raw)


def test_missing_source_file_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing file is a startup error naming the file."""
    monkeypatch.setattr(texts, "PASSAGES_PATH", tmp_path / "passages.json")
    get_passages.cache_clear()

    with pytest.raises(TextSourceError, match="cannot read passages.json"):
        get_passages()


def test_invalid_json_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A malformed JSON file is a startup error, not a traceback at request time."""
    path = tmp_path / "words_en.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(texts, "WORDS_PATH", path)
    get_word_list.cache_clear()

    with pytest.raises(TextSourceError, match="not valid JSON"):
        get_word_list()


def test_content_files_are_valid_json_on_disk() -> None:
    """The shipped files parse and match the in-memory loaders."""
    raw_passages = json.loads(texts.PASSAGES_PATH.read_text(encoding="utf-8"))
    raw_words = json.loads(texts.WORDS_PATH.read_text(encoding="utf-8"))

    assert [item["id"] for item in raw_passages] == [
        passage.id for passage in get_passages()
    ]
    assert tuple(raw_words) == get_word_list()


# --- Application startup wiring -----------------------------------------


def test_create_app_runs_the_text_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Creating the app calls the startup check."""
    calls: list[bool] = []
    monkeypatch.setattr(
        app_package, "validate_text_sources", lambda: calls.append(True)
    )

    app_package.create_app()

    assert calls == [True]


def test_create_app_propagates_text_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid content aborts startup instead of being swallowed."""

    def fail() -> None:
        raise TextSourceError("bad content")

    monkeypatch.setattr(app_package, "validate_text_sources", fail)

    with pytest.raises(TextSourceError):
        app_package.create_app()


# --- Engine integration --------------------------------------------------


def test_resolved_passage_can_be_replayed() -> None:
    """Resolved text flows straight into ``analyze_session``."""
    text = resolve_text({"type": "passage", "id": "p_001"})
    events = [
        {
            "seq": 0,
            "type": "down",
            "t": 0,
            "code": "KeyT",
            "key": text[0],
            "repeat": False,
        },
        {
            "seq": 1,
            "type": "up",
            "t": 90,
            "code": "KeyT",
            "key": None,
            "repeat": False,
        },
    ]

    analysis = analyze_session(
        text=text,
        mode="passage",
        duration_limit_ms=None,
        events=events,
    )

    assert analysis.replay.K == 1


def test_resolved_word_text_can_be_replayed() -> None:
    """Generated text is a valid engine reference text."""
    text = resolve_text({"type": "words", "seed": 5, "count": 10})
    events = [
        {
            "seq": 0,
            "type": "down",
            "t": 0,
            "code": "KeyA",
            "key": text[0],
            "repeat": False,
        },
        {
            "seq": 1,
            "type": "up",
            "t": 80,
            "code": "KeyA",
            "key": None,
            "repeat": False,
        },
    ]

    analysis = analyze_session(
        text=text,
        mode="time",
        duration_limit_ms=15_000,
        events=events,
    )

    assert analysis.replay.K == 1
    assert analysis.replay.dropped_after_end == 0
