# PROGRESS.md — Project Status

> Updated: 2026-11-14
> Branch: `database-version`

---

## Current Status

**Phase: Implementation in progress — P0-D1-01 through P0-D1-10 and P0-D2-01 through P0-D2-07 complete.**

Documentation, the minimum Flask application foundation, the pytest infrastructure, the replay engine, the metric layer, the key map, the Wilson heatmap heuristic, the session-payload validator, text resolution, the frontend theme foundation, keyboard capture and the live typing screen now exist. All seven golden examples pass through replay, and every replayable fixture matches its hand-computed speed, accuracy, interval, pause, dwell and error-accounting values. Character-keyed observations/IKI and physical-code dwell are merged into `key_code`-keyed `SessionKeyStat` rows. `app/validators.py` enforces the payload schema, ASCII key/code rules, sequence integrity, request limits and the forbidden server-derived end fields. `app/texts.py` resolves passages and deterministic word-mode text and guards all content at startup. The test screen is reachable at `GET /`, loads time-mode words or a passage through the documented text API, and shows clearly-labelled provisional stats. Esc restarts, Tab is never intercepted, focus loss cancels, and a full buffer with errors blocks completion. A finished attempt now submits the complete accepted event sequence to `POST /api/sessions`, which validates it, resolves the text, replays it in the pure engine and returns the authoritative metrics plus a results link. `GET /results/<session_id>` renders those server-computed numbers from the SQLite repository. `GET /api/sessions?limit=&offset=` and `/history` list saved sessions newest first, 25 per page, with row navigation to the results page. The typing screen matches `docs/UI_DESIGN.md` §4: token-based character states, a caret anchored to the second visible line with scroll-follows-caret, a provisional live row that stays hidden until the first keystroke, the full config strip, the documented state messages and focus handling. `GET /api/analytics/progress?scope=` and `/analytics` now show stored net WPM and accuracy as a stacked pair with a server-computed 5-session moving average, a scope toggle, theme-aware Chart.js rendering and an explicit empty state. `GET /api/export/sessions.csv` now downloads every stored session as a UTF-8 BOM CSV in the fixed blueprint column order, with empty cells for unavailable metrics and a leading `'` on formula-like cells. The keyboard heatmap remains.

---

## Completed Work

### Documentation (2026-11-06)
- [x] Read and fully understood `TBA_BLUEPRINT_v3_FINAL.md` (all 546 lines, all 22 revision entries)
- [x] Inspected repository: `feature/project-foundation` branch, clean working tree
- [x] Created `AGENTS.md` (root) — persistent agent instructions
- [x] Created `docs/PROJECT_BRIEF.md`
- [x] Created `docs/ARCHITECTURE.md`
- [x] Created `docs/UI_DESIGN.md`
- [x] Created `docs/METRICS.md`
- [x] Created `docs/EVENT_SCHEMA.md`
- [x] Created `docs/TASKS.md`
- [x] Created `docs/DECISIONS.md`
- [x] Created `docs/PROGRESS.md` (this file)
- [x] Created `docs/HANDOFF.md`

### Application scaffold (2026-11-06)
- [x] P0-D1-01: Created `run.py`, `requirements.txt`, `app/__init__.py`, `app/config.py`, `app/errors.py`
- [x] Added all 15 named metric threshold constants from `docs/METRICS.md` §14 to `app/config.py`
- [x] Added the nine documented API error codes and `json_error()` helper to `app/errors.py`
- [x] Created `.venv` and installed Flask 3.1.3 and pytest 9.2.0 (Python 3.14.7)
- [x] Verified Flask imports, `create_app()` returns a Flask application, and `python run.py` serves `http://127.0.0.1:5000` (`GET /` returns 404 as expected with no routes)
- [x] Corrected P0-D1-01 acceptance criteria in `docs/TASKS.md`: test infrastructure belongs to P0-D1-02
- [x] Corrected `.gitignore` to ignore `instance/`

### Test infrastructure (2026-11-06)
- [x] P0-D1-02: Created `tests/conftest.py` with `app`, `client`, and `db_conn` fixtures
- [x] Added `db_conn` as an in-memory `sqlite3` connection with `PRAGMA foreign_keys = ON`; no schema or `app/db.py` (ADR-018)
- [x] Created golden fixtures `tests/fixtures/golden_a.json` through `golden_g.json`
- [x] Added `tests/test_fixtures.py` for structural integrity only; no replay or metric logic
- [x] Added `tests/test_infrastructure.py` to verify the `app`, `client`, and `db_conn` fixtures
- [x] Committed externally as `147ec1e test: add test infrastructure and golden fixtures`
- [x] `pytest tests/ -v`: **10 passed** at P0-D1-02 completion

### Replay engine (2026-11-06)
- [x] P0-D1-03: Created `app/engine/replay.py` with the buffer state machine and pending-key map
- [x] Implemented printable, repeat-printable discard, non-repeat/repeat Backspace, keyup pairing, orphan up, missing up, full-buffer rejection, timer boundary, and dropped-after-end
- [x] Created `app/engine/__init__.py` with the `analyze_session()` replay-stage entry point
- [x] Created `tests/test_replay.py`: golden fixtures A–G plus focused pending-key and boundary tests
- [x] Asserted `E = U + Ec + Eu`, `K = C + E`, and `N ≤ K` on every fixture
- [x] Resolved AMB-005 with the approved fixture G text, 2000 ms limit, `timer_expiry` fixture label, and `T = 2000` (ADR-019)
- [x] `pytest tests/ -v`: **34 passed**

### Metric engine (2026-11-06)
- [x] P0-D1-04: Created `app/engine/metrics.py` with every formula from `docs/METRICS.md`
- [x] Implemented Gross WPM, Net WPM, primary accuracy, final-text accuracy, error rate, dwell statistics, interval classification (`V`, zero intervals, pauses), IKI mean/median/sample SD/CV, consistency, pause totals, and error accounting
- [x] Added the zero-mean guard for CV (`coefficient_of_variation`)
- [x] Extended `analyze_session()` to return `SessionAnalysis` (replay + metrics + per-key sums)
- [x] Implemented per-key clean-transition IKI keyed by expected character and valid dwell keyed by physical code
- [x] Created `tests/test_metrics.py`: golden fixtures A–G plus interval boundaries, IKI gates, consistency 29/30, zero-mean CV, dwell validity, and per-key clean transitions
- [x] Asserted `Net ≤ Gross` on every fixture, including incomplete fixture E
- [x] Resolved the fixture-A IKI conflict in favour of the §8.5 sample-size rule (ADR-023)
- [x] `pytest tests/ -v`: **91 passed**

### Key statistics and heatmap classification (2026-11-06)
- [x] P0-D1-05: Created `app/engine/keys.py`
- [x] Added `CHAR_TO_CODE` for all 95 printable ASCII characters (32–126) with US-QWERTY `event.code` values; capitals share letter keys and shifted symbols share their base keys
- [x] Implemented `wilson_ci()` exactly per `docs/METRICS.md` §12.2, including the reference Wilson(3, 20) ≈ [0.052, 0.360]
- [x] Implemented `classify_key()`, `classify_observation()`, `classify_key_stat()` and `pooled_baseline_error_rate()` with the `HEATMAP_MIN_N = 20` grey gate, all three weak-key conditions, the 1 % baseline floor and the strong/average fallbacks
- [x] Merged expected-character observations/IKI with physical-code dwell into `SessionKeyStat` rows matching the `session_key_stats` columns; `Backspace` appears as a dwell-only row and unmapped characters raise
- [x] Added `session_key_stats` to `SessionAnalysis` while retaining the raw `key_stats` intermediate
- [x] Created `tests/test_keys.py`: full ASCII coverage, shifted-key sharing, Wilson values and boundaries, n = 19 / n = 20, each weak condition, strong/average, dwell invariance, merge unions and ASCII failure
- [x] Recorded ADR-024 for the merge shape, classification gate and floating-point margin tolerance
- [x] `pytest tests/ -v`: **124 passed** (91 previous + 33 key tests)

### Session payload validation (2026-11-06)
- [x] P0-D1-06: Created `app/validators.py` with `validate_session_payload()` and typed `ValidatedSessionPayload`
- [x] Implemented `ValidationError` (422 `VALIDATION_ERROR`) and `PayloadTooLargeError` (413 `PAYLOAD_TOO_LARGE`) with aggregated `{field, problem}` details
- [x] Enforced required top-level fields, field types, modes, duration limits, text-ref shapes and word-count bounds, client fields, and all five ignored counters
- [x] Enforced the 2 MiB body limit and the 2–10 000 event-count bounds
- [x] Enforced per-event seq/index contiguity, finite non-negative non-decreasing `t`, `down`/`up` enums, code regex, printable-ASCII/Backspace key rules, null keyup keys, boolean `repeat`, and no repeat-printable keydowns
- [x] Rejected client-supplied `ended_at_ms` and `end_reason` (ADR-025) and documented the validator contract and timer-boundary ownership (ADR-026)
- [x] Kept timer-boundary handling in replay: events at `t >= duration_limit_ms` validate structurally, are excluded by replay, and end the session with `time_up`
- [x] Added the validation limits to `app/config.py` (`SUPPORTED_SCHEMA_VERSION`, `MIN/MAX_SESSION_EVENTS`, `MAX_SESSION_BODY_BYTES`, `ALLOWED_TIME_LIMITS_MS`, `WORD_COUNT_MIN/MAX`)
- [x] Created `tests/test_validators.py`: 57 test functions (190 cases) covering Unicode keys/codes, space/tilde acceptance, enums, seq gaps, oversized lists/event lists, forbidden end fields and both halves of the timer-boundary contract
- [x] `pytest tests/ -v`: **314 passed** (124 previous + 190 new validator cases)

### Text resolution (2026-11-06)
- [x] P0-D1-07: Created `app/data/passages.json` with 12 original ASCII passages (`p_001`–`p_012`, 222–260 characters each)
- [x] Created `app/data/words_en.json` with 200 unique lowercase `a-z` words in a frozen order
- [x] Created `app/texts.py`: cached loaders, `get_passage()`, `resolve_text()`, `generate_words()`, `words_for_duration()`, `validate_text_sources()` and `TextNotFoundError`/`TextSourceError`
- [x] Froze the documented `random.Random(seed).shuffle()` generator, including repeat-cycling when `count` exceeds the 200-word source (ADR-027)
- [x] Added `WORDS_FOR_DURATION_MS = {15000: 120, 30000: 200, 60000: 350}` to `app/config.py`
- [x] Wired the startup ASCII/lowercase guard into `create_app()`; invalid content aborts startup
- [x] Added `tests/test_texts.py`: 76 cases covering content contract, frozen seed mapping, count/duration boundaries, resolution, `TEXT_NOT_FOUND`, malformed sources and application wiring
- [x] Resolved `AMB-001` and `AMB-002` under ADR-027 (author-approved original content)
- [x] `pytest tests/ -v`: **390 passed** (314 previous + 76 text-resolution cases)

### Frontend foundation (2026-11-06)
- [x] P0-D1-08: Created `app/static/css/tokens.css` with the approved light and dark palettes, typography, 8-pt spacing, layout, shape, motion and focus tokens
- [x] Created `app/static/css/base.css` with the reset, self-hosted `@font-face` rules, global typography, application shell, nav, theme toggle, focus rings, reduced-motion handling and print-safe tokens
- [x] Created `app/templates/base.html` with the shared shell, primary nav, skip link, theme toggle, CSS imports, font preloads and JS blocks
- [x] Added the inline blocking theme initialisation script before the stylesheets; it reads `localStorage["tba-theme"]`, falls back to `prefers-color-scheme`, and removes `.no-transition` after load
- [x] Created `app/static/js/theme.js` to persist toggle changes, keep the accessible label in sync, and dispatch `tba:themechange`
- [x] Vendored Lexend and JetBrains Mono variable WOFF2 fonts (latin subset) with their OFL licence files
- [x] Vendored Chart.js 4.4.7 UMD as `app/static/vendor/chart.umd.min.js` with its MIT licence; no runtime CDN use
- [x] Added frontend smoke checks to `tests/test_infrastructure.py`: base-template rendering, script-before-stylesheet ordering, local static asset resolution, WOFF2 magic bytes and the vendored Chart.js header
- [x] Verified in Chromium: dark fallback from the OS, toggle to light and back, persistence across reload, `.no-transition` removal, Lexend/JetBrains Mono loading, tabular figures, and zero console errors
- [x] Recorded ADR-028 for asset provenance and the frontend foundation decisions
- [x] `pytest tests/ -v`: **392 passed** (390 previous + 2 frontend checks)

### Typing screen (2026-11-06)
- [x] P0-D1-09: Created `app/static/js/capture.js` with the documented printable/Backspace rules, pending-key map, repeat handling, AltGr treatment, timestamp fallback logging, keyup pairing, focus/window/visibility cancellation and listener cleanup
- [x] Created `app/static/js/typing-engine.js`: idle → running → finished attempt state, character-state rendering, caret tracking and scroll-follows-caret, provisional time/WPM/accuracy, completion, timer expiry, cancellation and full-buffer messaging
- [x] Created `app/templates/test.html` and `app/static/css/test.css` using only design tokens, with the config strip, provisional live row, three-line passage viewport, caret and Esc hint
- [x] Created `app/static/js/test-page.js`: time/passage configuration, aborted/token-guarded text fetch, passage selector population, Esc restart, focus handling and capture/engine wiring
- [x] Pulled forward `GET /` and the three P0 text endpoints from P0-D1-10 (ADR-030): `app/routes/__init__.py`, `app/routes/pages.py`, `app/routes/api.py`, blueprint registration in `app/__init__.py`
- [x] Frozen the text API response shapes and passage label rule; resolved `AMB-003` (ADR-029)
- [x] Added `tests/test_api.py` for the page and text endpoints and updated `tests/test_infrastructure.py` for the 200 page response and new static assets
- [x] Verified in Chromium: text loads from the API, live provisional stats update, correct/incorrect character states, Backspace, completion, timer expiry at the boundary, full-buffer blocking, Tab not prevented, focus-loss cancellation, Esc restart, caret line scrolling and light/dark persistence; zero console errors
- [x] `pytest tests/ -v`: **410 passed** (392 previous + 18 route/pulled-forward cases)

### First vertical slice (2026-11-06)
- [x] P0-D1-10: Added accepted-event accumulation and `getEvents()` to `app/static/js/capture.js` (contiguous `seq`, accepted events only)
- [x] Added one-shot payload construction and `POST /api/sessions` submission to `app/static/js/test-page.js`; the client never sends the text body, `ended_at_ms` or `end_reason`
- [x] Deferred submission with `queueMicrotask` so the completing keydown is recorded before the payload is built (ADR-031)
- [x] Implemented `POST /api/sessions` in `app/routes/api.py`: body limit, JSON parsing, validator delegation, text resolution, authoritative replay/metrics and 201 response
- [x] Added `app/session_store.py` with a process-local, thread-safe `InMemorySessionStore` attached through `app.extensions` (ADR-032)
- [x] Added `invalid_dwell_count` to `SessionMetrics`; added `DataQualityWarning` and `warnings` to `SessionAnalysis` for `orphan_up`, `missing_up`, `open_at_end`, `invalid_dwell` and `dropped_after_end`
- [x] Added `GET /results/<session_id>` and `app/templates/results.html` with Tier 1/2/3 metrics, `—` for unavailable values, conditional `Eu`, data-quality section, timing-honesty note and New test links
- [x] Added `app/static/css/components.css` using design tokens only
- [x] Added `tests/test_sessions.py`: 24 API, integration, results-rendering and frontend-contract tests, including engine-metric equality, timer boundary, passage completion, invalid submissions and the final-event deferral regression
- [x] Verified in Chromium: 15 s time flow (Start → Type → Finish → Submit → Results → New test) and passage completion (242 characters, 100% accuracy, `completed`); zero console errors
- [x] `pytest tests/ -v`: **434 passed** (410 previous + 24 vertical-slice cases)

### Database schema and connection (2026-11-09)
- [x] P0-D2-01: Created `app/schema.sql` transcribing blueprint §9: the `sessions`, `session_metrics`, `keystroke_events` and `session_key_stats` tables with foreign keys (`ON DELETE CASCADE`), the documented `sessions(created_at)` and `session_key_stats(key_code)` indexes, and CHECK constraints for mode/end-reason enums, the time/passage duration pairing, event `type`/`key`/`repeat` rules and non-negative `seq`/`t_ms`
- [x] Created `app/db.py`: `connect()` with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`, `apply_schema()` with idempotent `CREATE TABLE IF NOT EXISTS` and `PRAGMA user_version = 1`, `init_db()`, and the per-request `g.db` connection closed at app-context teardown
- [x] Wired `init_db()` into `create_app()`; `DATABASE` defaults to `instance/typing.db`, and `create_app(test_config)` lets tests point it at a temporary file
- [x] Updated `tests/conftest.py` so the `app` fixture isolates the database in `tmp_path`; added `tests/test_db.py` with 25 schema/connection cases (column fidelity, indexes, cascade, constraint rejections, `g.db` lifecycle, schema-version guard)
- [x] Recorded ADR-033 (types, CHECKs, index names, `user_version` semantics, test isolation, and the decision to keep blueprint columns exactly — `error_rate`/`invalid_dwell_count` are not columns; they live in the API layer / `data_quality_json`, which P0-D2-02 populates)
- [x] Verified first-run behaviour: `create_app()` created `instance/typing.db` (git-ignored) with the four tables and `user_version = 1`
- [x] `pytest tests/ -q`: **459 passed** (434 previous + 25 new)

### Repository and persistence (2026-11-09)
- [x] P0-D2-02: Created `app/repository.py` with every application SQL statement: `SessionRepository` writing sessions → session_metrics → `executemany` keystroke_events → `executemany` session_key_stats in a single transaction with full rollback on failure; `get(id)`, `count()`, `list_sessions(limit, offset)` (newest first, exact total) and `get_key_stats(id)`
- [x] Attached the repository behind the historical `app.extensions["tba_session_store"]` key so routes and tests keep one service-locator surface; deleted `app/session_store.py`
- [x] Only validated events up to the derived end are stored (EVENT_SCHEMA §10): replay drops a trailing suffix, so the repository retains `validated.events[:len(events) - dropped_after_end]`
- [x] `data_quality_json` stores the non-zero `{code, count, message}` warnings (NULL when none); read-back reconstructs a full `SessionMetrics` from stored columns — `invalid_dwell_count` recovered from the stored warning, `error_rate` derived as `100 − accuracy_pct` per `docs/METRICS.md` §4.4 (logged in ADR-034 together with the non-persistence of `started_at`/`ignored`, which blueprint §9 defines no columns for)
- [x] Rebuilt `POST /api/sessions` (persist, then respond from the stored record) and `GET /results/<id>` (renders the persisted record; template reads `session.active_duration_ms`)
- [x] Added `tests/test_repository.py`: round-trip fidelity, events-up-to-derived-end, restart persistence across repository instances, FK cascade, mid-save rollback with no partial data, paginated list, key-stats round-trip; updated `tests/test_sessions.py` for the repository
- [x] `pytest tests/ -q`: **469 passed** (459 previous + 10 new)

### Session retrieval API (2026-11-10)
- [x] P0-D2-03 (API portion): added `GET /api/sessions/<id>` returning `{ session, metrics, key_stats }` from `SessionRepository.get()` and `get_key_stats()`; unknown ids return `404 NOT_FOUND`; the route contains no SQL or metric math
- [x] Added three endpoint tests in `tests/test_sessions.py`: full envelope/session/metric/key-stat fidelity, the dwell-only Backspace row, and the unknown-id 404
- [x] Recorded ADR-035 for the nested response shape (blueprint §10 fixes only the top-level envelope)
- [x] `pytest tests/ -q`: **472 passed** (469 previous + 3 new)

### Results page UI (2026-11-10)
- [x] P0-D2-03 (UI portion): `app/templates/results.html` now carries the full three-tier layout (hero Net WPM/Accuracy, Supporting metrics, Detail and timing, More detail), each metric label with a `?` definition tooltip
- [x] Replaced the native `title`-only help spans with accessible markup: a `<button data-metric-help>` plus an adjacent `role="tooltip"` span; `title` remains as a no-JS fallback until the module removes it
- [x] Added `app/static/js/results-page.js`: assigns tooltip ids/`aria-describedby`, toggles `aria-expanded`, closes on blur, Escape and outside click; it never fetches or computes metrics
- [x] Added tooltip styles to `app/static/css/components.css` using existing design tokens only; hover, `:focus-visible` and `aria-expanded` all show the definition
- [x] Data quality renders only when warnings exist or `zero_interval_count > 0`; `Eu` renders only when non-zero; unavailable values stay `—` (never `None`)
- [x] Added tests: tooltip markup/JS contracts, data-quality absence on clean sessions, zero-length interval reporting, and the new static asset; updated `tests/test_infrastructure.py`
- [x] Verified in Chromium against a persisted session (`053d6adeee02460ead0559dfda2b7204`): 25 tooltips, hover/click/focus show, Escape and outside click dismiss, `Eu` and data quality visible, only console error is the pre-existing `/favicon.ico` 404
- [x] `pytest tests/ -q`: **474 passed** (472 previous + 2 new)

### History page (2026-11-14)
- [x] P0-D2-04: added `GET /api/sessions?limit=&offset=` returning `{ items, total }`; `limit` defaults to 25 and is capped at 100, `offset` defaults to 0, and invalid values return `422 VALIDATION_ERROR` with the offending field
- [x] Extended `SessionSummary` (and the repository list query) with `consistency_score` so the documented six-column table can be rendered; the repository remains the only SQL owner
- [x] Added `app/templates/history.html` (column headers, empty state, pagination controls, `data-page-size`) and `GET /history` in `app/routes/pages.py`
- [x] Added `app/static/js/history-page.js`: fetches one page at a time, formats stored values only, drives Previous/Next, shows the documented empty state, and navigates a row to `/results/<id>` (real anchor in the first cell plus a row click listener)
- [x] Added history table/pagination styles to `app/static/css/components.css` using design tokens only, and switched the `history` nav entry to `url_for` (ADR-028, ADR-036)
- [x] Added tests: empty list, newest-first summaries with exact total, limit/offset paging, default page size with 26 sessions, invalid pagination values, page markup, script contract, and the new static asset
- [x] Verified in Chromium against 30 seeded sessions: 25 rows on page 1, page 2 shows 5 rows, Previous/Next disable correctly, a row opens `/results/<id>`, and the only console error is the pre-existing `/favicon.ico` 404
- [x] Recorded ADR-036 (list item shape, pagination defaults/limits, client-rendered page, row navigation)
- [x] `pytest tests/ -q`: **486 passed** (474 previous + 12 new)

### Typing screen polish (2026-11-14)
- [x] P0-D2-05: verified every `docs/UI_DESIGN.md` §4 state against the live page before changing code
- [x] Fixed the caret alignment in `app/static/js/typing-engine.js`: the caret is now anchored to the line box (line index derived from the first span's `offsetTop`) instead of the inline content box, so it no longer overhangs the following line; the track still keeps the caret on visible line 2
- [x] Confirmed untyped/correct/incorrect character states and the 2 px accent caret use tokens only; untyped = muted, correct = text, incorrect = error + underline + `--error-bg`, caret blinking only when idle
- [x] Confirmed the live row stays hidden until the first keystroke, carries the `provisional` badge, and shows timer/WPM/accuracy
- [x] Confirmed the config strip (mode toggle, 15/30/60, passage selector), the documented fix-highlighted and focus-loss messages, and Esc-returns-to-idle
- [x] Aligned the too-short copy with `docs/UI_DESIGN.md` §4: `SESSION_TOO_SHORT` now says "Too short to save."
- [x] Confirmed auto-focus on load and re-focus after every config change (including the passage selector)
- [x] Added `tests/test_typing_screen.py` (7 contracts: config strip, hidden provisional live row, three-line focusable viewport, token character/caret states, engine state classes and fix message, caret line anchoring, focus defaults) and tightened the existing too-short test to assert the documented message
- [x] Browser verification of the rendered states, config strip, caret line position (with the transition disabled to measure the final layout), provisional row, fix message, too-short message, Esc reset and the focus-loss cancellation handler; the desktop window could not receive native keystrokes, so input was dispatched through DOM keyboard events
- [x] `pytest tests/ -q`: **493 passed** (486 previous + 7 new)

### Progress endpoint and analytics charts (2026-11-14)
- [x] P0-D2-06: added `GET /api/analytics/progress?scope=`; scope defaults to `all` and accepts only `last_10`, `last_30` and `all`, with `422 VALIDATION_ERROR` (`field: "scope"`) for anything else
- [x] Added `SessionRepository.list_progress(limit)` (the only SQL) selecting the newest 10/30/all rows by `created_at DESC, id DESC` and returning them oldest first for a forward-running x axis
- [x] Added `engine.metrics.trailing_moving_average()`: trailing 5-point window, expanding for the first 1–4 points, skipping `None` instead of treating it as zero; resolves AMB-004
- [x] Response is `{ scope, window, sessions }`; each session carries `session_id`, `created_at`, `mode`, `duration_limit_ms`, `net_wpm`, `accuracy_pct` and both server-computed moving averages
- [x] Added `/analytics` (`pages.analytics_page`), `app/templates/analytics.html`, `app/static/js/analytics-page.js` and `app/static/js/charts.js`; the nav entry now uses `url_for`
- [x] Two stacked charts share the session labels: stored series plus the dashed 5-session moving average; nulls stay gaps, accuracy is fixed to 0–100, and each chart has one "what to look for" line
- [x] Charts re-read CSS tokens and `chart.update("none")` on `tba:themechange`; scope changes destroy the previous instances before rendering, and empty history creates no chart at all
- [x] Empty state uses the documented "No sessions yet." copy plus a Take a test link; styling in `components.css` uses tokens only
- [x] Added `tests/test_analytics.py` (12 cases: empty history, five invalid scopes, chronological series with hand-computed averages, scope limits/default, null metrics, newly persisted session, page markup/nav, asset/JS contracts), a repository progress-series test and a moving-average unit test
- [x] Verified in Chromium against 7 stored sessions: both charts render all 7 points with the server averages, `last 10` switches and leaves exactly two chart instances, the theme toggle recolours the series from `#e28ab2` to `#8e2949` without reloading, the empty database shows the empty state with no chart, nav reaches `/analytics`, and the console has no errors (only the pre-existing `/favicon.ico` 404)
- [x] Recorded ADR-037 (series shape, scope validation/default, ordering, null handling, page ownership, AMB-004 resolution)
- [x] `pytest tests/ -q`: **507 passed** (493 previous + 14 new)

### Sessions CSV export (2026-11-14)
- [x] P0-D2-07: added `app/exporters.py` with the blueprint §10 column tuple, RFC 4180 CRLF rows, UTF-8 BOM output and the `= + - @` formula-injection guard; NULL values become empty cells
- [x] Added `SessionExportRow` and `SessionRepository.list_export_rows()` (the only SQL), returning every stored session newest first with `gross_wpm`, `final_accuracy_pct` and the four keystroke counts
- [x] Added `app/routes/exports.py` (`exports` blueprint): `GET /api/export/sessions.csv` returns `text/csv; charset=utf-8` with `Content-Disposition: attachment; filename="sessions.csv"`; an empty database returns the BOM plus the header row
- [x] Registered the blueprint in `create_app()`; the route holds no SQL and the exporter holds no HTTP or database access
- [x] Added `tests/test_exports.py` (9 cases: exact column order, empty-database CSV, one persisted session, multiple sessions newest first, NULL cells, injection guard, quoting/Unicode round trip, repeatable read-only download, layer separation)
- [x] Recorded ADR-038 (row order, line endings, filename/content type, rendering, layer ownership)
- [x] Verified with a real HTTP request against an isolated server and temporary database: `201` submit, then `200` download with `text/csv; charset=utf-8`, `attachment; filename="sessions.csv"`, BOM, header plus the persisted row matching the stored metrics
- [x] `pytest tests/ -q`: **516 passed** (507 previous + 9 new)

### Application code
- [x] P0-D1-01 scaffold, P0-D1-02 test infrastructure, P0-D1-03 replay, P0-D1-04 metrics, P0-D1-05 key statistics, P0-D1-06 validators, P0-D1-07 text resolution, P0-D1-08 frontend foundation, P0-D1-09 typing screen, P0-D1-10 session submission, P0-D2-01 schema, P0-D2-02 persistence, P0-D2-03 session retrieval API and the three-tier results page, P0-D2-04 history list and page, P0-D2-05 typing-screen polish, P0-D2-06 progress endpoint and analytics charts, P0-D2-07 sessions CSV export; the heatmap pages are still pending

---

## Remaining Work (P0, in order)

| Task | Status |
|---|---|
| P0-D1-01: Repository scaffold | ✅ Complete (2026-11-06) |
| P0-D1-02: Tests infrastructure | ✅ Complete (2026-11-06) |
| P0-D1-03: Engine — replay | ✅ Complete (2026-11-06) |
| P0-D1-04: Engine — metrics | ✅ Complete (2026-11-06) |
| P0-D1-05: Engine — key stats / heatmap | ✅ Complete (2026-11-06) |
| P0-D1-06: Validators | ✅ Complete (2026-11-06) |
| P0-D1-07: Text resolution | ✅ Complete (2026-11-06) |
| P0-D1-08: Frontend — themes / CSS | ✅ Complete (2026-11-06) |
| P0-D1-09: Frontend — capture / typing engine | ✅ Complete (2026-11-06) |
| P0-D1-10: First vertical slice | ✅ Complete (2026-11-06) — `POST /api/sessions` + in-memory results (ADR-031, ADR-032) |
| P0-D2-01: DB schema and connection | ✅ Complete (2026-11-09) — `app/schema.sql` + `app/db.py`, ADR-033 |
| P0-D2-02: Repository and persistence | ✅ Complete (2026-11-09) — `app/repository.py` + repository-backed routes (ADR-034) |
| P0-D2-03: Results page (full) | ✅ Complete (2026-11-10) — API (ADR-035) + three-tier UI with tooltips |
| P0-D2-04: History page | ✅ Complete (2026-11-14) — list API (ADR-036) + paginated `/history` page |
| P0-D2-05: Typing screen polish | ✅ Complete (2026-11-14) — caret line anchoring + documented state messages |
| P0-D2-06: Progress endpoint and analytics charts | ✅ Complete (2026-11-14) — progress API (ADR-037) + theme-aware `/analytics` charts |
| P0-D2-07: sessions.csv export | ✅ Complete (2026-11-14) — BOM CSV exporter (ADR-038) + `GET /api/export/sessions.csv` |
| P0-D3-01: Key stats aggregation and heatmap API | ✅ Complete (2026-11-21) — historical aggregation in the engine (ADR-039) + `GET /api/analytics/keys?scope=` |
| P0-D3-02: Heatmap UI | ⬜ Not started |
| P0-D3-03: Hygiene tests | ⬜ Not started |
| P0-D3-04: Manual test pass | ⬜ Not started |
| P0-D3-05: README and delivery | ⬜ Not started |

---

## Next Milestone

**Day 2:** database-backed persistence, the full results page, the history page, the typing-screen polish pass, the progress charts and the CSV export are complete.

**Day 3 (started):** the historical key aggregation and heatmap API is complete (`GET /api/analytics/keys?scope=`, ADR-039; Backspace press totals and tracked-layout filtering included; `pytest tests/ -q`: **545 passed**).

Exact next task: **P0-D3-02** — heatmap UI (`/keyboard`, `app/templates/keyboard.html`, `app/static/js/keyboard-heatmap.js`, `app/static/css/keyboard.css`) consuming the new endpoint, then hygiene tests, manual pass and release.

---

## Blockers / Ambiguities

See `docs/DECISIONS.md` for open ambiguities:
- **AMB-001:** ✅ Resolved by ADR-027 (200-word list frozen; author editorial review pending before release)
- **AMB-002:** ✅ Resolved by ADR-027 (12 original ASCII passages; author editorial review pending before release)
- **AMB-003:** Passage selector label format (minor; use first ~40 characters per ADR-027)
- **AMB-004:** ✅ Resolved by ADR-037 (trailing 5-session window, expanding for the first 1–4 points, nulls skipped)

### Known issues carried forward
- Per-key attribution is resolved: `metrics.py` still returns the two raw maps (ADR-022), and `keys.merge_session_key_stats()` now produces the `key_code`-keyed rows (ADR-024). `SessionAnalysis` exposes both forms.
- The fixture-A IKI contradiction is closed under ADR-023; `golden_a.json` now expects null IKI statistics because `|V| = 3 < 5`.
- Passage and word content now exists; changing either file's content or ordering requires a new ADR because seed→text mappings must stay reproducible (ADR-027). The authored passages still need the author's editorial review before release.
- The timer boundary is resolved under ADR-026: the validator accepts events at `t >= duration_limit_ms`; replay excludes them and ends with `time_up`. Tests cover both halves.
- Client-supplied `ended_at_ms`/`end_reason` are rejected under ADR-025; a conforming client never sends them.
- Application limits outside `docs/METRICS.md` §14 are now centralised in `app/config.py` (schema version, event counts, 2 MiB body, allowed durations, word-count range, duration→word sizing).
- `docs/UI_DESIGN.md` §7 references `docs/METRICS.md` §6 for the Wilson heuristic; correct during UI documentation cleanup.
- `README.md` is not yet present; leave for P0-D3-05.
- `app/routes/` now holds `pages.py`, `api.py` and `exports.py`; all three blueprints are registered in `create_app()`. The CSV export route is the only one that does not return JSON.
- Base-template nav links for `analytics` and `keyboard` used to 404; `analytics` now resolves to `/analytics` and `history` to `/history`, while `keyboard` remains deliberate until P0-D3-02 (ADR-028).
- Chart.js is vendored and loaded only by `analytics.html`; no other page carries it.
- Only the latin font subsets are vendored, matching the ASCII-only application content (ADR-028).
