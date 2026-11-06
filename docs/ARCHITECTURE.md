# ARCHITECTURE.md — Typing Behaviour Analyzer

> Reference: `TBA_BLUEPRINT_v3_FINAL.md` §2, §9, §10, §12

---

## 1. High-Level Architecture

```
BROWSER
  capture.js          ──► events array in memory
  typing-engine.js    ──► UI state, provisional live stats
  charts.js           ──► Chart.js, theme-aware rendering
        │
        │  ONE POST at test end  (events only; no end time, no metric math)
        ▼
FLASK ROUTES  (app/routes/)
  api.py              ──► parse → validate → call engine + repo → shape JSON
  pages.py            ──► Jinja template rendering
  exports.py          ──► CSV responses
        │
        ├──► validators.py         schema + ASCII + event-sequence checks
        ├──► texts.py              text resolution (passages.json, words_en.json)
        │
        ▼
ENGINE  (app/engine/)  — pure Python, no HTTP, no DB
  replay.py           ──► event replay → buffer state → K, C, E, N, U, Ec, Eu
  metrics.py          ──► all metric formulas (WPM, accuracy, IKI, dwell, etc.)
  keys.py             ──► CHAR_TO_CODE table, Wilson interval, key classification
  __init__.py         ──► analyze_session() — the single entry point
        │
        ▼
REPOSITORY  (app/repository.py)  — all SQL, no metric math
        │
        ▼
SQLite  (instance/typing.db)
```

---

## 2. Layer Responsibilities

| Layer | Does | Must NOT |
|---|---|---|
| **Browser JS** | Capture events; show provisional live WPM/accuracy; submit the event array once at test end | Compute stored or final statistics; send `ended_at_ms` or `end_reason`; send the passage text |
| **Routes** | Parse request, call validators → engine → repository, shape JSON responses | Contain metric math or SQL |
| **Engine** | Replay events, classify keystrokes, compute all metrics, classify heatmap keys | Make HTTP calls or touch the database |
| **Repository** | Execute all SQL (reads, writes, aggregations) | Compute metrics |
| **Validators** | Validate schema, ASCII constraints, event-sequence integrity | Contain metric math or business logic |

---

## 3. Data Flow: Submitting a Test Session

```
1. User types → JS collects keydown/keyup events in memory
2. Test ends (completion or timer) → capture listeners removed
3. JS POSTs: { schema_version, mode, duration_limit_ms, text_ref, started_at,
              client, ignored, events[] }
   — text_ref only (no text body); no end time; no metrics
4. Flask route receives POST /api/sessions
5. validators.py: schema check → event-field checks → sequence integrity
6. texts.py: resolve text_ref → rebuild passage text
7. engine.analyze_session(): replay → metrics → key_stats
8. repository.py: single transaction →
      INSERT sessions
      INSERT session_metrics
      INSERT keystroke_events (executemany)
      INSERT session_key_stats (executemany)
9. Route returns 201 { session_id, metrics, warnings, links }
10. Browser redirects to /results/<session_id>
```

---

## 4. Data Flow: Viewing Analytics / Heatmap

```
GET /api/analytics/keys?scope=all
  → repository: SELECT SUM(attempts), SUM(errors), SUM(dwell_sum_ms), ...
                FROM session_key_stats GROUP BY key_code
  → engine/keys.py: Wilson interval + classification per key
  → route: shape JSON { method, baseline_error_rate, keys: [...] }
  → keyboard-heatmap.js: render <button> keyboard, colour by class
```

---

## 5. Database Design

> Full schema in `TBA_BLUEPRINT_v3_FINAL.md` §9. Summary below.

```
sessions ──1:1── session_metrics
    ├──1:N── keystroke_events
    └──1:N── session_key_stats
```

| Table | Purpose |
|---|---|
| `sessions` | One row per test: mode, text reference, passage snapshot, typed text, timing, client info |
| `session_metrics` | Derived metrics for the session (WPM, accuracy, IKI stats, dwell, error breakdown, etc.) |
| `keystroke_events` | Raw immutable event log — only validated events up to derived end |
| `session_key_stats` | Per-key sums (`attempts`, `errors`, `dwell_sum_ms`, `iki_sum_ms`, etc.) — additive for cross-session aggregation |

Key schema rules:
- `PRAGMA foreign_keys = ON` on every connection.
- Schema version tracked with `PRAGMA user_version`.
- One `app/schema.sql` file — delete the DB if schema changes during development.
- `analysis_version = 1` for the initial metric definition set; increment when metric semantics change.
- All writes for one session in a single transaction (`executemany` for events).
- `keystroke_events.session_id` has `ON DELETE CASCADE`.
- Index on `sessions(created_at)` and `session_key_stats(key_code)`.

---

## 6. API Surface

> Full specification in `TBA_BLUEPRINT_v3_FINAL.md` §10.

| Priority | Endpoint | Purpose |
|---|---|---|
| P0 | `GET /api/texts/passages` | List passage text refs |
| P0 | `GET /api/texts/passages/<id>` | Get one passage |
| P0 | `GET /api/texts/words?count=` | Generate word-mode text with seed |
| P0 | `POST /api/sessions` | Submit session; returns metrics |
| P0 | `GET /api/sessions?limit=&offset=` | History list |
| P0 | `GET /api/sessions/<id>` | Full session detail |
| P0 | `GET /api/analytics/progress?scope=` | WPM/accuracy over time |
| P0 | `GET /api/analytics/keys?scope=` | Key heatmap data |
| P0 | `GET /api/export/sessions.csv` | Sessions export |
| P0 | `GET /api/health` | Health check |
| P1 | `GET /api/analytics/iki-histogram?scope=` | IKI distribution |
| P1 | `GET /api/export/events.csv?session_id=` | Raw events export |
| P1 | `DELETE /api/sessions/<id>` | Delete session |

Error response shape (all endpoints):
```json
{ "error": { "code": "VALIDATION_ERROR", "message": "...", "details": [ {"field": "...", "problem": "..."} ] } }
```

---

## 7. Frontend Architecture

- **No bundler.** Each page template loads one ES-module entry script.
- **Jinja2 templates** extend `base.html`. Pages: `test.html`, `results.html`, `analytics.html`, `keyboard.html`, `history.html`.
- **JS modules** (one per page): `test-page.js`, `results-page.js`, `analytics-page.js`, `keyboard-heatmap.js`, `history-page.js`.
- Shared modules: `api.js` (fetch wrapper), `theme.js` (theme toggle + event dispatch), `capture.js` (event capture), `typing-engine.js` (UI state machine), `charts.js` (Chart.js wrappers).
- Chart.js is vendored at `static/vendor/chart.umd.min.js` — no CDN.
- Fonts vendored in `static/fonts/`.

---

## 8. Folder Structure

```
typing-behaviour-analyzer/
├── run.py
├── requirements.txt              (Flask, pytest)
├── README.md
├── AGENTS.md
├── .gitignore
├── TBA_BLUEPRINT_v3_FINAL.md
├── docs/
│   ├── PROJECT_BRIEF.md
│   ├── ARCHITECTURE.md           (this file)
│   ├── UI_DESIGN.md
│   ├── METRICS.md
│   ├── EVENT_SCHEMA.md
│   ├── TASKS.md
│   ├── DECISIONS.md
│   ├── PROGRESS.md
│   └── HANDOFF.md
├── app/
│   ├── __init__.py               create_app()
│   ├── config.py                 named constants (thresholds, limits)
│   ├── db.py                     connection management, PRAGMA setup
│   ├── schema.sql                DDL for all four tables
│   ├── errors.py                 error code constants + response helpers
│   ├── validators.py             schema + ASCII + sequence validation
│   ├── texts.py                  text resolution + startup ASCII assertion
│   ├── repository.py             all SQL (no metric math)
│   ├── exporters.py              CSV generation
│   ├── engine/
│   │   ├── __init__.py           analyze_session() entry point
│   │   ├── replay.py             event replay → buffer state
│   │   ├── metrics.py            all metric formulas
│   │   └── keys.py               CHAR_TO_CODE, Wilson CI, key classification
│   ├── routes/
│   │   ├── pages.py              Jinja page routes
│   │   ├── api.py                JSON API routes
│   │   └── exports.py            CSV export routes
│   ├── data/
│   │   ├── passages.json         ~12 original/public-domain ASCII passages
│   │   └── words_en.json         ~200 common English words
│   ├── templates/
│   │   ├── base.html
│   │   ├── test.html
│   │   ├── results.html
│   │   ├── analytics.html
│   │   ├── keyboard.html
│   │   └── history.html
│   └── static/
│       ├── css/
│       │   ├── tokens.css        CSS custom properties (design tokens)
│       │   ├── base.css
│       │   ├── test.css
│       │   ├── components.css
│       │   ├── keyboard.css
│       │   └── print.css         (P1)
│       ├── fonts/                Lexend + JetBrains Mono (self-hosted, OFL)
│       ├── vendor/
│       │   └── chart.umd.min.js
│       └── js/
│           ├── theme.js
│           ├── api.js
│           ├── capture.js
│           ├── typing-engine.js
│           ├── test-page.js
│           ├── results-page.js
│           ├── analytics-page.js
│           ├── keyboard-heatmap.js
│           ├── history-page.js
│           └── charts.js
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   ├── test_replay.py
│   ├── test_metrics.py
│   ├── test_keys.py
│   ├── test_validators.py
│   ├── test_repository.py
│   ├── test_api.py
│   ├── test_exports.py
│   └── test_hygiene.py
└── instance/
    └── typing.db                 (git-ignored)
```

---

## 9. Theme Architecture

- CSS tokens on `:root` (light — "Cheesecake") and `:root[data-theme="dark"]`.
- No hex literals in component CSS; only token references.
- Inline blocking `<script>` in `<head>`, before the stylesheet link, reads `localStorage["tba-theme"]` (try/catch, falls back to `prefers-color-scheme`) and sets `data-theme` on `<html>`.
- A `.no-transition` class is applied during load and removed after, preventing FOUC.
- Theme toggle dispatches `tba:themechange` event; charts listen and call `chart.update("none")` to recolour.
- Print media query always uses light tokens.
