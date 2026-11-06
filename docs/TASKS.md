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
- [ ] Implement `app/engine/keys.py`:
  - `CHAR_TO_CODE` table: all ASCII 32–126 mapped to US-QWERTY key codes
  - `wilson_ci(x, n, z=1.96)` function
  - `classify_key(e, b, lo, hi, x)` → `"weak"` / `"average"` / `"strong"` / `"insufficient"`
- [ ] Write `tests/test_keys.py`:
  - Wilson(3, 20) ≈ [0.052, 0.360]
  - `n < 20` → grey/insufficient
  - `n = 20` → classified
  - Weak requires `lo > b` AND `e - b ≥ 0.02` AND `x ≥ 3`
  - Long dwell never changes classification
  - `CHAR_TO_CODE` covers all 95 printable ASCII characters
- [ ] **Acceptance:** all key tests pass
- [ ] **Files touched:** `app/engine/keys.py`, `tests/test_keys.py`
- [ ] **Commit:** `feat(engine): keys — CHAR_TO_CODE and Wilson heuristic`

### P0-D1-06: Validators
- [ ] Implement `app/validators.py`: full payload schema validation per `docs/EVENT_SCHEMA.md` §6–§7
  - Use `re.fullmatch()` only (never `re.match`, `isalnum`, `isprintable`, `\w`, `isascii`)
  - Check: required fields, field types, event count (2–10 000), body ≤ 2 MB, non-decreasing `t`, first event is non-repeat printable `down`, no repeat-printable, no `up` with non-null `key`, code regex, key regex
- [ ] Write `tests/test_validators.py`:
  - Reject: `key="é"`, `key="ß"`, `key="\u00a0"`, `key="😀"`, `key="\n"`, `key="\x7f"`, `key="Dead"`, `code="KeyÉ"`, `code="KeyA\n"`, `code="٣"` (Unicode digit)
  - Accept: `key=" "` (space, ASCII 32), `key="~"` (ASCII 126)
  - Reject: non-monotonic `t`, gap in `seq`, bad enums, oversized list, wrong `schema_version`
  - Reject: `up` with non-null `key`
  - Reject: payload that includes `ended_at_ms` or `end_reason` fields (blueprint §4.3, regression group 2 — these must not be accepted as inputs; they are server-derived only)
  - Reject: events at `t == duration_limit_ms` are not accepted in time mode; events at `t > limit` are dropped (regression group 2)
- [ ] **Acceptance:** all validator tests pass
- [ ] **Files touched:** `app/validators.py`, `tests/test_validators.py`
- [ ] **Commit:** `feat(validators): full schema and ASCII validation`

### P0-D1-07: Text resolution
- [ ] Create `app/data/passages.json` (~12 passages, original or public-domain, ASCII 32–126 only)
- [ ] Create `app/data/words_en.json` (~200 common English words, lowercase ASCII)
- [ ] Implement `app/texts.py`:
  - Passage loader + getter
  - Deterministic word generator: `random.Random(seed).shuffle()` over fixed word list
  - Word count sizing: 15 s → 120 words, 30 s → 200 words, 60 s → 350 words
  - Startup ASCII assertion (fail loudly if any char outside 32–126)
- [ ] Add startup assertion to `create_app()`
- [ ] **Acceptance:** startup assertion fires; `texts.py` returns correct text for given `text_ref`; deterministic across calls with same seed
- [ ] **Files touched:** `app/texts.py`, `app/data/passages.json`, `app/data/words_en.json`
- [ ] **Commit:** `feat(texts): text resolution and startup ASCII assertion`

### P0-D1-08: Frontend — themes and CSS tokens
- [ ] Create `app/static/css/tokens.css` with all design tokens (light + dark) per `docs/UI_DESIGN.md` §3
- [ ] Create `app/static/css/base.css` (reset, body, nav, typography)
- [ ] Create inline blocking theme script (read `docs/UI_DESIGN.md` §9)
- [ ] Create `app/templates/base.html` with nav, theme toggle, font links, CSS imports
- [ ] Download/vendor Lexend and JetBrains Mono fonts to `app/static/fonts/`
- [ ] Download Chart.js UMD build to `app/static/vendor/chart.umd.min.js`
- [ ] **Acceptance:** no FOUC; theme persists across reload; both light and dark render correctly
- [ ] **Files touched:** `app/static/css/tokens.css`, `app/static/css/base.css`, `app/templates/base.html`, fonts, vendor

### P0-D1-09: Frontend — capture and typing engine
- [ ] Implement `app/static/js/capture.js` per `docs/EVENT_SCHEMA.md`:
  - Keydown/keyup listeners on the passage viewport
  - Pending map, repeat handling, orphan up tracking
  - `t` calculation from first accepted keydown
  - Timestamp fallback with diagnostic logging
  - Focus/blur/visibilitychange handlers
  - Full-buffer enforcement
- [ ] Implement `app/static/js/typing-engine.js`: UI state machine (idle → running → finished/cancelled), live WPM/accuracy display (provisional), caret movement, character state rendering
- [ ] Implement `app/templates/test.html` and `app/static/css/test.css`
- [ ] Implement `app/static/js/test-page.js` (config strip, text fetch, test orchestration)
- [ ] **Acceptance:** typing test runs in browser; events are captured correctly; Tab never intercepted; focus loss cancels test; Esc cancels test

### P0-D1-10: First vertical slice — POST /api/sessions
- [ ] Implement `app/routes/api.py`: `POST /api/sessions` route
  - Parse JSON → validate → resolve text → engine.analyze_session() → return 201 with metrics
  - No DB persistence yet (in-memory response only)
- [ ] Implement `app/routes/pages.py`: basic `GET /` route serving `test.html`
- [ ] Wire up routes in `create_app()`
- [ ] Show metrics on a minimal plain results page (can be in-memory, no DB)
- [ ] **Acceptance:** full flow works: type → submit → see numbers. `pytest` green.
- [ ] **Commit:** `feat(vertical-slice): type → POST → metrics displayed`

---

## Day 2 — Persistence, Results, History, Progress

### P0-D2-01: Database schema and connection
- [ ] Write `app/schema.sql`: DDL for all four tables per `docs/ARCHITECTURE.md` §5
  - `sessions`, `session_metrics`, `keystroke_events`, `session_key_stats`
  - Foreign keys, indexes, CHECK constraints
- [ ] Implement `app/db.py`: connection factory, `PRAGMA foreign_keys = ON`, `PRAGMA user_version`, `g.db` per-request connection
- [ ] Add `init_db()` to `create_app()`
- [ ] **Acceptance:** DB initialises on first run; schema matches blueprint exactly

### P0-D2-02: Repository and persistence
- [ ] Implement `app/repository.py`: all SQL — INSERT session, INSERT metrics, INSERT events (`executemany`), INSERT key stats (`executemany`), all in a **single transaction**
- [ ] Implement GET queries: session by id, session list (paginated), session key stats
- [ ] Write `tests/test_repository.py`:
  - Persistence round-trip (save and retrieve match)
  - FK cascade (deleting session removes events and metrics)
  - Rollback on mid-save failure (no partial data)
  - Paginated list returns correct total and items
- [ ] Update `POST /api/sessions` to persist to DB
- [ ] **Acceptance:** session saved after POST; retrievable by id; rollback works; `pytest` green
- [ ] **Commit:** `feat(db): persistence — single-transaction save and round-trip tests`

### P0-D2-03: Results page (full)
- [ ] Implement `GET /api/sessions/<id>` returning `{ session, metrics, key_stats }`
- [ ] Implement `app/templates/results.html` with all three tiers (see `docs/UI_DESIGN.md` §5)
- [ ] Implement `app/static/js/results-page.js`
- [ ] Every metric label has a `?` definition tooltip
- [ ] "About the measurements" note present (§5.5 timing honesty)
- [ ] Data-quality line shows only when non-zero
- [ ] `Eu` shown only when non-zero
- [ ] **Acceptance:** all metrics displayed correctly; tooltips work; note is present

### P0-D2-04: History page
- [ ] Implement `GET /api/sessions?limit=&offset=` returning `{ items, total }`
- [ ] Implement `app/templates/history.html` and `app/static/js/history-page.js`
- [ ] 25 rows per page, pagination controls
- [ ] Row click navigates to `/results/<id>`
- [ ] Empty state: "No sessions yet."
- [ ] **Acceptance:** history lists correctly; pagination works; row click navigates

### P0-D2-05: Typing screen polish
- [ ] Passage viewport: caret rendering, character state rendering (untyped/correct/incorrect/caret), scroll-follows-caret (line 2)
- [ ] Live row: hidden until first keystroke, labelled *provisional*
- [ ] Config strip: mode toggle, time options (15/30/60), passage selector
- [ ] All state messages: fix-highlighted, too-short, cancelled-by-focus-loss
- [ ] Focus behaviour: auto-focus on load, re-focus after config changes
- [ ] **Acceptance:** manual check per `docs/UI_DESIGN.md` §4

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
