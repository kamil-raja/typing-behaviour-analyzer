# TASKS.md — Development Task List

> Reference: `TBA_BLUEPRINT_v3_FINAL.md` §13 (three-day roadmap), §14 (testing)
> **Rules:**
> - Work only on the **first unchecked P0 task**. Never start P1 while any P0 is broken.
> - Mark a task `[x]` only when its acceptance criteria are met AND `pytest` passes.
> - Commit after every green milestone.

---

## Day 1 — Engine and Core Loop

### P0-D1-01: Repository and project scaffold
- [x] Create `run.py` (entry point: `app = create_app(); app.run(debug=True)`)
- [x] Create `requirements.txt` with `Flask` and `pytest`
- [x] Create `app/__init__.py` with `create_app()` factory (empty Flask app for now)
- [x] Create `app/config.py` with all named constants (thresholds from `docs/METRICS.md` §14)
- [x] Create `app/errors.py` with error code constants and JSON error response helper
- [x] Create virtual environment (`.venv`); install dependencies from `requirements.txt`
- [x] Verify Flask imports and `create_app()` returns a Flask application
- [x] Verify `python run.py` starts the development server on `http://127.0.0.1:5000` without error
- [x] **Acceptance:** dependencies install successfully; Flask imports; `create_app()` succeeds; `python run.py` starts the local development server. Automated test infrastructure and tests belong to P0-D1-02; this task does not require `pytest tests/` to pass.
- [x] **Files touched:** `run.py`, `requirements.txt`, `app/__init__.py`, `app/config.py`, `app/errors.py`, `.gitignore`
- **Commit:** `9c02975 chore: add project foundation scaffold` — committed before P0-D1-02 began.

### P0-D1-02: Tests infrastructure and conftest
- [x] Create `tests/conftest.py` with Flask test client fixture and in-memory DB fixture
- [x] Create `tests/fixtures/` directory
- [x] Create golden fixture files for examples A–G (from `docs/METRICS.md` §13)
- [x] Add fixture-integrity checks in `tests/test_fixtures.py` (structure only; no replay or metric logic)
- [x] Add conftest fixture checks in `tests/test_infrastructure.py`
- [x] **Acceptance:** `pytest tests/` runs with 0 errors; **10 tests pass** (7 fixture-structure checks, 1 fixture-G check, 2 conftest fixture checks).
- [x] **Files touched:** `tests/conftest.py`, `tests/test_fixtures.py`, `tests/test_infrastructure.py`, `tests/fixtures/golden_a.json` … `golden_g.json`, `docs/DECISIONS.md`
- **Commit:** `147ec1e test: add test infrastructure and golden fixtures` — committed externally; no commit was made by this agent.

### P0-D1-03: Engine — replay
- [x] Implement `app/engine/replay.py`: buffer state machine, `pending` map, all event-handling rules per `docs/EVENT_SCHEMA.md` §4
- [x] Handle: accepted printable, repeat printable (discard), Backspace (non-repeat, repeat), `up` pairing, orphan up, missing up, full-buffer rule, timer boundary rule, dropped-after-end
- [x] Implement `app/engine/__init__.py` with `analyze_session()` stub
- [x] Write `tests/test_replay.py`: golden fixtures A–G against expected K, C, E, N, U, Ec, Eu, deletions, presses, dropped_after_end, end_reason, T
- [x] Assert invariants on every fixture: `E = U + Ec + Eu`, `K = C + E`, `N ≤ K`
- [x] **Acceptance:** all fixture tests pass; **34 tests pass** in the full suite.
- [x] **Files touched:** `app/engine/__init__.py`, `app/engine/replay.py`, `tests/test_replay.py`, `tests/test_fixtures.py`, `tests/fixtures/golden_f.json`, `tests/fixtures/golden_g.json`
- **Commit:** `e9e2215 feat(engine): implement event replay` — committed externally; no commit was made by the agent that wrote the handoff.

### P0-D1-04: Engine — metrics
- [x] Implement `app/engine/metrics.py`: all formulas from `docs/METRICS.md` (gross WPM, net WPM, accuracy, final-text accuracy, dwell, IKI stats, consistency, pause stats, per-key IKI, error accounting)
- [x] Include zero-mean guard for CV calculation
- [x] Write `tests/test_metrics.py`: verify exact expected values from fixtures A–G (Gross, Net, accuracy, intervals, pauses)
- [x] Assert `Net ≤ Gross` on every fixture
- [x] **Acceptance:** all metric tests pass with hand-computed values
- [x] **Files touched:** `app/engine/metrics.py`, `app/engine/__init__.py`, `tests/test_metrics.py`, `tests/test_replay.py`, `tests/fixtures/golden_a.json`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`
- **Commit (deferred):** `feat(engine): metrics — green on all fixtures` — not performed; commits require explicit approval.

### P0-D1-05: Engine — key stats and heatmap classification
- [x] Implement `app/engine/keys.py`:
  - `CHAR_TO_CODE` table: all ASCII 32–126 mapped to US-QWERTY key codes
  - `wilson_ci(x, n, z=1.96)` function
  - `classify_key(e, b, lo, hi, x)` → `"weak"` / `"average"` / `"strong"` / `"insufficient"`
- [x] Write `tests/test_keys.py`:
  - Wilson(3, 20) ≈ [0.052, 0.360]
  - `n < 20` → grey/insufficient
  - `n = 20` → classified
  - Weak requires `lo > b` AND `e - b ≥ 0.02` AND `x ≥ 3`
  - Long dwell never changes classification
  - `CHAR_TO_CODE` covers all 95 printable ASCII characters
- [x] Merge character-keyed observations/IKI with code-keyed dwell into `key_code`-keyed `SessionKeyStat` rows and expose them as `SessionAnalysis.session_key_stats`
- [x] Add `pooled_baseline_error_rate()`, `classify_observation()` and `classify_key_stat()` helpers for the P0-D3-01 aggregation endpoint
- [x] **Acceptance:** all key tests pass; **124 tests pass** in the full suite
- [x] **Files touched:** `app/engine/keys.py`, `app/engine/__init__.py`, `tests/test_keys.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`
- **Commit (deferred):** `feat(engine): keys — CHAR_TO_CODE and Wilson heuristic` — not performed; commits require explicit approval (ADR-024 explains the merge/classification shape).

### P0-D1-06: Validators
- [x] Implement `app/validators.py`: full payload schema validation per `docs/EVENT_SCHEMA.md` §6–§7
  - Use `re.fullmatch()` only (never `re.match`, `isalnum`, `isprintable`, `\w`, `isascii`)
  - Check: required fields, field types, event count (2–10 000), body ≤ 2 MB, non-decreasing `t`, first event is non-repeat printable `down`, no repeat-printable, no `up` with non-null `key`, code regex, key regex
- [x] Write `tests/test_validators.py`:
  - Reject: `key="é"`, `key="ß"`, `key="\u00a0"`, `key="😀"`, `key="\n"`, `key="\x7f"`, `key="Dead"`, `code="KeyÉ"`, `code="KeyA\n"`, `code="٣"` (Unicode digit)
  - Accept: `key=" "` (space, ASCII 32), `key="~"` (ASCII 126)
  - Reject: non-monotonic `t`, gap in `seq`, bad enums, oversized list, wrong `schema_version`
  - Reject: `up` with non-null `key`
  - Reject: payload that includes `ended_at_ms` or `end_reason` fields (blueprint §4.3, regression group 2 — these must not be accepted as inputs; they are server-derived only)
  - Timer boundary: events at `t >= duration_limit_ms` remain structurally valid and are excluded by replay, which sets `time_up` (ADR-026). Validator tests assert both halves of this contract (regression group 2).
- [x] **Acceptance:** all validator tests pass; **314 tests pass** in the full suite
- [x] **Files touched:** `app/validators.py`, `tests/test_validators.py`, `app/config.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`
- [x] **Commit (deferred):** `feat(validators): full schema and ASCII validation` — not performed; commits require explicit approval

### P0-D1-07: Text resolution
- [x] Create `app/data/passages.json` (~12 passages, original or public-domain, ASCII 32–126 only)
- [x] Create `app/data/words_en.json` (~200 common English words, lowercase ASCII)
- [x] Implement `app/texts.py`:
  - Passage loader + getter
  - Deterministic word generator: `random.Random(seed).shuffle()` over fixed word list
  - Word count sizing: 15 s → 120 words, 30 s → 200 words, 60 s → 350 words
  - Startup ASCII assertion (fail loudly if any char outside 32–126)
- [x] Add startup assertion to `create_app()`
- [x] **Acceptance:** startup assertion fires; `texts.py` returns correct text for given `text_ref`; deterministic across calls with same seed; **390 tests pass** in the full suite
- [x] **Files touched:** `app/texts.py`, `app/data/passages.json`, `app/data/words_en.json`, `app/__init__.py`, `app/config.py`, `tests/test_texts.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`
- [x] **Commit (deferred):** `feat(texts): text resolution and startup ASCII assertion` — not performed; commits require explicit approval

### P0-D1-08: Frontend — themes and CSS tokens
- [x] Create `app/static/css/tokens.css` with all design tokens (light + dark) per `docs/UI_DESIGN.md` §3
- [x] Create `app/static/css/base.css` (reset, body, nav, typography)
- [x] Create inline blocking theme script (read `docs/UI_DESIGN.md` §9)
- [x] Create `app/templates/base.html` with nav, theme toggle, font links, CSS imports
- [x] Download/vendor Lexend and JetBrains Mono fonts to `app/static/fonts/`
- [x] Download Chart.js UMD build to `app/static/vendor/chart.umd.min.js`
- [x] Add `app/static/js/theme.js` for toggle persistence and `tba:themechange` dispatch
- [x] **Acceptance:** no FOUC; theme persists across reload; both light and dark render correctly; **392 tests pass** in the full suite
- [x] **Files touched:** `app/static/css/tokens.css`, `app/static/css/base.css`, `app/static/js/theme.js`, `app/templates/base.html`, `app/static/fonts/` (two WOFF2 files + two OFL licences), `app/static/vendor/chart.umd.min.js` + licence, `tests/test_infrastructure.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`

### P0-D1-09: Frontend — capture and typing engine
- [x] Implement `app/static/js/capture.js` per `docs/EVENT_SCHEMA.md`:
  - Keydown/keyup listeners on the passage viewport
  - Pending map, repeat handling, orphan up tracking
  - `t` calculation from first accepted keydown
  - Timestamp fallback with diagnostic logging
  - Focus/blur/visibilitychange handlers
  - Full-buffer enforcement
- [x] Implement `app/static/js/typing-engine.js`: UI state machine (idle → running → finished/cancelled), live WPM/accuracy display (provisional), caret movement, character state rendering
- [x] Implement `app/templates/test.html` and `app/static/css/test.css`
- [x] Implement `app/static/js/test-page.js` (config strip, text fetch, test orchestration)
- [x] Pulled forward from P0-D1-10 (ADR-030): `app/routes/__init__.py`, `app/routes/pages.py` with `GET /`, `app/routes/api.py` with the three text GET endpoints, and blueprint registration in `create_app()`
- [x] Added `tests/test_api.py`; updated `tests/test_infrastructure.py` for the 200 page response and the new static assets
- [x] **Acceptance:** typing test runs in browser; events are captured correctly; Tab never intercepted; focus loss cancels test; Esc cancels test. **410 tests pass** in the full suite.
- [x] **Files touched:** `app/static/js/capture.js`, `app/static/js/typing-engine.js`, `app/static/js/test-page.js`, `app/templates/test.html`, `app/static/css/test.css`, `app/routes/__init__.py`, `app/routes/pages.py`, `app/routes/api.py`, `app/__init__.py`, `tests/test_api.py`, `tests/test_infrastructure.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`

### P0-D1-10: First vertical slice — POST /api/sessions
- [x] Implement `app/routes/pages.py`: basic `GET /` route serving `test.html` — **pulled forward into P0-D1-09** (ADR-030)
- [x] Add the three P0 text GET endpoints — **pulled forward into P0-D1-09** (ADR-030)
- [x] Wire up the page and text API blueprints in `create_app()` — **pulled forward into P0-D1-09** (ADR-030)
- [x] Implement `app/routes/api.py`: `POST /api/sessions` route
  - Parse JSON → validate → resolve text → engine.analyze_session() → return 201 with metrics
  - No DB persistence yet (in-memory response only)
- [x] Accumulate accepted events in `capture.js` and submit the documented payload once from `test-page.js` (ADR-031)
- [x] Show metrics on a minimal plain results page (in-memory, no DB) at `GET /results/<session_id>` (ADR-032)
- [x] Add `app/session_store.py`, `app/templates/results.html`, `app/static/css/components.css`, `tests/test_sessions.py`
- [x] **Acceptance:** full flow works: type → submit → see numbers. **434 tests pass**; Chromium verified time-up and passage-completion flows. `pytest` green.
- [x] **Commit:** `feat(core): complete first typing analysis workflow` (`40e41dc`, committed externally)
- [x] **Files touched:** `app/routes/api.py`, `app/routes/pages.py`, `app/__init__.py`, `app/config.py`, `app/session_store.py`, `app/engine/__init__.py`, `app/engine/metrics.py`, `app/templates/results.html`, `app/static/css/components.css`, `app/static/js/capture.js`, `app/static/js/test-page.js`, `tests/test_sessions.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`

---

## Day 2 — Persistence, Results, History, Progress

### P0-D2-01: Database schema and connection
- [x] Write `app/schema.sql`: DDL for all four tables per `docs/ARCHITECTURE.md` §5
  - `sessions`, `session_metrics`, `keystroke_events`, `session_key_stats`
  - Foreign keys, indexes, CHECK constraints
- [x] Implement `app/db.py`: connection factory, `PRAGMA foreign_keys = ON`, `PRAGMA user_version`, `g.db` per-request connection
- [x] Add `init_db()` to `create_app()`
- [x] **Acceptance:** DB initialises on first run; schema matches blueprint exactly; `pytest tests -q`: **459 passed** (434 previous + 25 new schema/connection cases)
- [x] **Files touched:** `app/schema.sql`, `app/db.py`, `app/__init__.py`, `tests/conftest.py`, `tests/test_db.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`
- [x] **Commit (deferred):** `feat(db): schema and connection management` — not performed; commits require explicit approval (see ADR-033)

### P0-D2-02: Repository and persistence
- [x] Implement `app/repository.py`: all SQL — INSERT session, INSERT metrics, INSERT events (`executemany`), INSERT key stats (`executemany`), all in a **single transaction**
- [x] Implement GET queries: session by id, session list (paginated, newest first, with exact total), session key stats
- [x] Write `tests/test_repository.py`:
  - Persistence round-trip (save and retrieve match; 10 cases)
  - FK cascade (deleting session removes events, metrics and key stats)
  - Rollback on mid-save failure (no partial data)
  - Paginated list returns correct total and items
- [x] Update `POST /api/sessions` to persist to DB; `GET /results/<id>` renders the persisted record; `app/session_store.py` removed (ADR-034)
- [x] **Acceptance:** session saved after POST; retrievable by id; rollback works; `pytest tests/ -q`: **469 passed** (459 previous + 10 repository cases)
- [x] **Files touched:** `app/repository.py`, `app/session_store.py` (deleted), `app/__init__.py`, `app/routes/api.py`, `app/routes/pages.py`, `app/templates/results.html`, `tests/test_repository.py`, `tests/test_sessions.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`
- [x] **Commit (deferred):** `feat(db): persistence — single-transaction save and round-trip tests` — not performed; commits require explicit approval (see ADR-034)
- [ ] **Commit:** `feat(db): persistence — single-transaction save and round-trip tests`

### P0-D2-03: Results page (full)
> **Status (2026-11-10):** Complete — API (ADR-035) and results-page UI.
- [x] Implement `GET /api/sessions/<id>` returning `{ session, metrics, key_stats }` (2026-11-10; ADR-035)
- [x] Implement `app/templates/results.html` with all three tiers (see `docs/UI_DESIGN.md` §5)
- [x] Implement `app/static/js/results-page.js` (tooltip interaction only; no fetching or metric math)
- [x] Every metric label has a `?` definition tooltip (accessible button + `role="tooltip"` text)
- [x] "About the measurements" note present (§5.5 timing honesty)
- [x] Data-quality line shows only when non-zero
- [x] `Eu` shown only when non-zero
- [x] **Acceptance:** all metrics displayed correctly; tooltips work; note is present
- [x] **Files touched:** `app/templates/results.html`, `app/static/js/results-page.js`, `app/static/css/components.css`, `tests/test_sessions.py`, `tests/test_infrastructure.py`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`
- [x] **Commit (deferred):** `feat(results): three-tier results page with metric tooltips` — not performed; commits require explicit approval

### P0-D2-04: History page
> **Status (2026-11-14):** Complete — list API (ADR-036), `/history` page and client-side pagination.
- [x] Implement `GET /api/sessions?limit=&offset=` returning `{ items, total }`
- [x] Implement `app/templates/history.html` and `app/static/js/history-page.js`
- [x] 25 rows per page, pagination controls
- [x] Row click navigates to `/results/<id>`
- [x] Empty state: "No sessions yet."
- [x] **Acceptance:** history lists correctly; pagination works; row click navigates. `pytest tests/ -q`: **486 passed**; Chromium verified 25 rows, page 2 of 2, disabled control states and row navigation.
- [x] **Files touched:** `app/config.py`, `app/repository.py`, `app/routes/api.py`, `app/routes/pages.py`, `app/templates/base.html`, `app/templates/history.html`, `app/static/js/history-page.js`, `app/static/css/components.css`, `tests/test_sessions.py`, `tests/test_repository.py`, `tests/test_infrastructure.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`
- [x] **Commit (deferred):** `feat(history): list endpoint and paginated history page` — not performed; commits require explicit approval (ADR-036)

### P0-D2-05: Typing screen polish
> **Status (2026-11-14):** Complete — verified against `docs/UI_DESIGN.md` §4. Caret line alignment fixed; the too-short copy now matches the documented message.
- [x] Passage viewport: caret rendering, character state rendering (untyped/correct/incorrect/caret), scroll-follows-caret (line 2)
- [x] Live row: hidden until first keystroke, labelled *provisional*
- [x] Config strip: mode toggle, time options (15/30/60), passage selector
- [x] All state messages: fix-highlighted, too-short, cancelled-by-focus-loss
- [x] Focus behaviour: auto-focus on load, re-focus after config changes
- [x] **Acceptance:** manual check per `docs/UI_DESIGN.md` §4
- [x] **Files touched:** `app/static/js/typing-engine.js`, `app/routes/api.py`, `tests/test_sessions.py`, `tests/test_typing_screen.py` (new), `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`
- **Commit (deferred):** `feat(test): polish typing screen caret and state messages` — not performed; commits require explicit approval

### P0-D2-06: Progress endpoint and analytics charts
- [ ] Implement `GET /api/analytics/progress?scope=` returning sessions with `net_wpm`, `accuracy_pct`, moving average
- [ ] Implement `app/templates/analytics.html` and `app/static/js/analytics-page.js`
- [ ] WPM and accuracy charts (stacked pair, shared x-axis, 5-session moving average)
- [ ] Charts are theme-aware (re-read tokens on `tba:themechange`)
- [ ] `app/static/js/charts.js` (Chart.js wrappers, theme helpers)
- [ ] Empty state: no fake data
- [ ] **Acceptance:** charts render; theme switch recolours without page reload

### P0-D2-07: sessions.csv export
- [ ] Implement `app/exporters.py`: UTF-8 BOM CSV; injection guard (`= + - @` get leading `'`); fixed columns in blueprint order
- [ ] Implement `GET /api/export/sessions.csv` route
- [ ] Write `tests/test_exports.py`:
  - UTF-8 BOM present
  - Injection guard on cells starting with `= + - @`
  - Null metrics export as empty cells (not "None" or "null")
  - Fixed column order matches spec
- [ ] **Acceptance:** export downloads correctly; BOM present; injection safe; `pytest` green
- [ ] **Commit:** `feat(day2): persistence, results, history, progress, export`
- [ ] Run `git tag day2` after committing

---

## Day 3 — Heatmap, Polish, Delivery

### P0-D3-01: Key stats aggregation and heatmap API
- [ ] Implement `GET /api/analytics/keys?scope=` in `repository.py` and `api.py`
  - Aggregate `SUM(attempts), SUM(errors), SUM(dwell_sum_ms), SUM(dwell_count), SUM(iki_sum_ms), SUM(iki_count)` per `key_code`
  - Compute baseline error rate, Wilson CI, classification per key using `engine/keys.py`
  - Return `{ method, baseline_error_rate, min_observations, overall_mean_dwell_ms, keys: [...] }`
- [ ] `method` field value: `"wilson_vs_pooled_baseline_heuristic"`
- [ ] Write tests in `tests/test_keys.py` for the full classification pipeline
- [ ] **Acceptance:** API returns correct classification; `pytest` green

### P0-D3-02: Heatmap UI
- [ ] Implement `app/templates/keyboard.html` and `app/static/js/keyboard-heatmap.js`
- [ ] ANSI 15-unit keyboard as `<button>` elements
- [ ] Error mode (default): colour keys by classification; grey/no-glyph for insufficient data
- [ ] Legend: text + glyphs (▲ weak, ■ average, ● strong, grey = none)
- [ ] Click-to-pin inspector: n, x, error rate + CI, dwell (n), IKI (n), classification + reason
- [ ] "Weakest keys" list and "Needs more data" list
- [ ] Backspace: shows press count and dwell only (no error classification)
- [ ] Non-tracked keys: neutral (no colour/glyph)
- [ ] `app/static/css/keyboard.css`
- [ ] **Acceptance:** heatmap renders; inspector works; colour is not the only cue; `pytest` green

### P0-D3-03: Hygiene tests
- [ ] Implement `tests/test_hygiene.py`:
  - User-facing heatmap strings (templates + shipped JS literals) contain no "significant" or "statistically" (note: `METRICS.md` technical explanation is excluded from this check per blueprint §14.2 regression group 5)
  - `README` and templates contain no µs/microsecond precision claims for timing
  - Timing-honesty note is present in results template
  - API has no bigram/pause/recalculate routes
  - Schema has no bigram table
- [ ] **Acceptance:** all hygiene tests pass

### P0-D3-04: Manual test pass
- [ ] Execute full manual checklist from `TBA_BLUEPRINT_v3_FINAL.md` §14.3
- [ ] Fix any bugs found
- [ ] `pytest` green after all fixes

### P0-D3-05: README and delivery
- [ ] Write `README.md`: project purpose, setup, run instructions, limitations note (§5.5), `analysis_version` explanation
- [ ] Final `pytest` run; commit; tag `v1.0`
- [ ] **Commit:** `chore(release): v1.0 — all P0 complete`

---

## P1 Tasks (only after all P0 is green)

Take in this order:

| ID | Task |
|---|---|
| P1-01 | Per-second WPM chart on results page (§7.5) |
| P1-02 | Dwell mode on heatmap (§8.3) |
| P1-03 | Speed mode on heatmap (§8.3) |
| P1-04 | IKI histogram on analytics page (§7.3, §14.1) |
| P1-05 | Events CSV export (`GET /api/export/events.csv?session_id=`) |
| P1-06 | Delete session (`DELETE /api/sessions/<id>`) |
| P1-07 | Retry-save and Download JSON on session-save failure |
| P1-08 | Layout-mismatch banner (`navigator.keyboard.getLayoutMap()`) |
| P1-09 | Print stylesheet for results page |
| P1-10 | README polish |

**Rule:** if a P1 is unfinished when time runs out, remove its UI entry point. Do not ship a broken P1 feature.

---

## P2 Tasks (not started in the initial build)

Bigram analysis · rhythm chart · pause charts · session comparison · recalculation endpoint · dedicated report page · pause/resume · error-cascade guard · non-QWERTY full support · colour-blind palette.
