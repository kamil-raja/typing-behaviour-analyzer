"""Hygiene and scope tests (blueprint §14.2 groups 5, 7 and 11).

These tests protect the documented wording and scope limits, not the
implementation: the heatmap stays a heuristic in user-facing copy, timing
claims stay honest, and the deferred P2 features stay absent from the API and
schema. Documentation such as ``METRICS.md`` is deliberately excluded from the
heatmap wording check (ADR-005).
"""

from __future__ import annotations

import re
from pathlib import Path

from flask import Flask

from app.db import connect

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"
SHIPPED_JS = ROOT / "app" / "static" / "js"

# ADR-005: the heatmap is a conservative heuristic, never a significance test.
SIGNIFICANCE_WORDS = ("significant", "statistically")

# Unsupported timing-resolution or precision claims (blueprint §14.2 group 7).
# "not laboratory-grade" is an honesty statement, so only the claim form is banned.
UNSUPPORTED_TIMING_CLAIMS = (
    re.compile(r"microseconds?"),
    re.compile(r"nanoseconds?"),
    re.compile(r"[µμ]s"),
    re.compile(r"(?:laboratory|lab)-grade precision"),
)

# Minimal extractor for single-, double- and backtick-quoted JavaScript strings.
_JS_STRING = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`'
)


def _template_sources() -> dict[str, str]:
    """Return every template's source text keyed by file name."""
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(TEMPLATES.glob("*.html"))
    }


def test_heatmap_copy_never_claims_statistical_significance() -> None:
    """Templates and shipped JS strings describe a heuristic, not a test."""
    sources = _template_sources()
    for path in sorted(SHIPPED_JS.glob("*.js")):
        literals = _JS_STRING.findall(path.read_text(encoding="utf-8"))
        sources[path.name] = "\n".join(literals)

    for name, text in sources.items():
        lowered = text.lower()
        for word in SIGNIFICANCE_WORDS:
            assert word not in lowered, f"{name} contains {word!r}"


def test_timing_copy_makes_no_unsupported_precision_claim() -> None:
    """User-facing copy never claims a timing resolution the browser cannot give."""
    files = sorted(TEMPLATES.glob("*.html"))
    readme = ROOT / "README.md"
    if readme.exists():
        files.append(readme)

    for path in files:
        lowered = path.read_text(encoding="utf-8").lower()
        for claim in UNSUPPORTED_TIMING_CLAIMS:
            match = claim.search(lowered)
            assert match is None, f"{path.name} claims {match.group(0)!r}"


def test_results_template_states_the_timing_limits() -> None:
    """The results page carries the documented timing-honesty note."""
    source = (TEMPLATES / "results.html").read_text(encoding="utf-8").lower()

    assert "about the measurements" in source
    assert "not laboratory-grade" in source
    assert "relative comparison" in source


def test_api_has_no_deferred_p2_routes(app: Flask) -> None:
    """No bigram, pause or recalculation endpoint exists (blueprint §14.2 group 11)."""
    routes = " ".join(
        f"{rule.rule} {rule.endpoint}" for rule in app.url_map.iter_rules()
    ).lower()

    assert "bigram" not in routes
    assert "pause" not in routes
    assert "recalculat" not in routes


def test_schema_has_no_bigram_table(app: Flask) -> None:
    """The initial schema holds only the four documented tables."""
    connection = connect(app.config["DATABASE"])
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        connection.close()

    assert tables == {
        "sessions",
        "session_metrics",
        "keystroke_events",
        "session_key_stats",
    }
