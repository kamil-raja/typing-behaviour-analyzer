# HANDOFF.md — Work Transfer Instructions

> This file is updated at the end of every work session.
> Both Antigravity and OpenCode must read this file before starting any work.

---

## How to Hand Off Between Agents

1. The outgoing agent updates this file with:
   - Current branch and git status
   - Files changed in this session (with brief description)
   - Tests run and their results
   - Exact next task (task ID from `docs/TASKS.md`)
   - Any mid-task stopping point details
2. The outgoing agent commits all changes with an appropriate message once the user approves. If a commit is deferred, record that in Current State.
3. The incoming agent reads: `AGENTS.md` → `docs/HANDOFF.md` → `docs/TASKS.md` → starts at the first unchecked task.

---

## For OpenCode

OpenCode reads `AGENTS.md` automatically (it is the standard `AGENTS.md` file at the repo root).
Then read this file. Then read `docs/TASKS.md` and start at the first unchecked `[ ]` P0 task.

## For Antigravity

Antigravity reads `AGENTS.md` as a rules file (check Antigravity docs for the exact rules-file name and point it here).
Then read this file. Then read `docs/TASKS.md` and start at the first unchecked `[ ]` P0 task.

---

## Current State (as of 2026-11-10)

### Development server (Windows)

Run the server in a normal PowerShell terminal, never through a detached shell:

```powershell
cd K:\Projects\typing-behaviour-analyzer
.\.venv\Scripts\python.exe run.py
```

Open `http://127.0.0.1:5000/`. Stop with `Ctrl+C` in the same terminal; restart by running the command again.

`run.py` uses `app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)`. The reloader is intentionally off so there is no Flask parent/child process pair and `Ctrl+C` stops the server cleanly. Debug mode remains enabled.

Note: on this machine `.venv\Scripts\python.exe` is a Python Launcher shim, so Task Manager still shows two Python processes (the shim plus the real interpreter). That is not the Flask reloader; the startup log contains no `Restarting with stat` line, and `Ctrl+C` terminates both processes.

### Git

| Field | Value |
|---|---|
| **Branch** | `database-version` (in sync with `origin/database-version`) |
| **Status** | Uncommitted P0-D2-03 work: modified `app/routes/api.py`, `app/templates/results.html`, `app/static/css/components.css`, `tests/test_sessions.py`, `tests/test_infrastructure.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md`; new `app/static/js/results-page.js` |
| **Last commit** | `4992846 feat(db): persistence — single-transaction save and round-trip tests` (P0-D2-02) |
| **Tags** | None yet |
| **Commit/push** | **None performed by this agent.** P0-D1-01–P0-D1-10 were committed as `9c02975`, `147ec1e`, `e9e2215`, `61d8c36`, `55130e1`, `1c0137a`, `4599be0`, `3cc8a56`, `20864ab`, `40e41dc`; the dev-server fix as `8a940b4`; P0-D2-01 as `8b1e811`; P0-D2-02 as `4992846` (all committed externally). This agent composes working-tree changes only. |

`.venv/`, `__pycache__/`, and `instance/` (including `instance/typing.db` created by the first-run check) are ignored and are not part of the working-tree changes.

### Completed This Session — P0-D2-03 (part 2) Results page UI

| File | Purpose |
|---|---|
| `app/templates/results.html` | Full three-tier layout (hero Net WPM/Accuracy, Supporting metrics, Detail and timing, More detail); accessible tooltip macro; module script block |
| `app/static/js/results-page.js` | Tooltip interaction: assigns ids/`aria-describedby`, toggles `aria-expanded`, closes on blur, Escape and outside click; no fetching and no metric math |
| `app/static/css/components.css` | Tooltip wrap/button/panel styles plus the existing results styles, all from design tokens |
| `tests/test_sessions.py` | Tooltip markup/JS contracts, data-quality absence on clean sessions, zero-length interval reporting, and the `Eu`/data-quality assertions |
| `tests/test_infrastructure.py` | Static asset check now includes `/static/js/results-page.js` |
| `docs/TASKS.md`, `docs/PROGRESS.md`, `docs/HANDOFF.md` | P0-D2-03 marked complete; test count and next-task updates |

- Tooltips are progressive: the button keeps a `title` fallback for no-JS, and `results-page.js` removes it once the `role="tooltip"` panel is wired. Hover, `:focus-visible` and `aria-expanded="true"` all reveal the panel through CSS only.
- Conditional rendering: `Eu` appears only when `metrics.erased_unresolved_errors > 0`; the Data quality section appears only when `warnings` is non-empty or `metrics.zero_interval_count > 0`; every unavailable numeric value stays `—`.
- No metric math, SQL or API calls were added to JavaScript. The page remains server-rendered from the persisted `SessionRecord`; `GET /api/sessions/<id>` is unchanged (ADR-035).
- Browser smoke test (Playwright, real persisted session `053d6adeee02460ead0559dfda2b7204`): 25 tooltips, click pins, hover shows, Escape and outside click dismiss, `Eu` and Data quality visible. The only console error is the pre-existing `/favicon.ico` 404.
- `pytest tests/ -q`: **474 passed** (472 previous + 2 new).
- **P0-D2-03 is now fully complete:** API (ADR-035) plus the results-page UI.

### Completed This Session — P0-D2-03 (part 1) Session retrieval API

| File | Purpose |
|---|---|
| `app/routes/api.py` | `GET /api/sessions/<id>` returns `{ session, metrics, key_stats }` from `SessionRepository.get()`/`get_key_stats()`; unknown ids return `404 NOT_FOUND`; `_session_detail()` serialises the stored record without metric math or SQL |
| `tests/test_sessions.py` | Three endpoint cases: full envelope plus session/metric/key-stat fidelity, the dwell-only Backspace row, and the unknown-id 404 |
| `docs/DECISIONS.md` | ADR-035 (nested response shape; blueprint §10 fixes only the envelope) |
| `docs/TASKS.md`, `docs/PROGRESS.md`, `docs/HANDOFF.md` | Status, test count and next-task updates |

- The endpoint serialises persisted values only: `session` mirrors the stored record (including the persisted `warnings`), `metrics` is exactly `asdict(SessionMetrics)` with the read-back `error_rate` identity, and `key_stats` is the ordered list of stored `SessionKeyStat` rows. No SQL or metric math exists in the route.
- `pytest tests/test_sessions.py -q -k "session_detail or unknown_session_detail"`: **3 passed**.
- `pytest tests/ -q`: **472 passed** (469 previous + 3 new).
- **P0-D2-03 is now fully complete** after part 2 (results-page UI) above; this part covered only the retrieval endpoint.

### Completed This Session — P0-D2-02 Repository and persistence

| File | Purpose |
|---|---|
| `app/repository.py` | `SessionRepository`: single-transaction save (sessions → session_metrics → `executemany` events → `executemany` key stats), `get()`, `count()`, `list_sessions()`, `get_key_stats()` |
| `app/session_store.py` | Deleted — the repository replaces the in-memory store behind the same `extensions["tba_session_store"]` key |
| `app/__init__.py` | `create_app()` attaches `SessionRepository(app.config["DATABASE"])` |
| `app/routes/api.py` | `POST /api/sessions` persists through the repository and responds from the stored record |
| `app/routes/pages.py` | `GET /results/<id>` renders the persisted `SessionRecord` |
| `app/templates/results.html` | Active duration now reads `session.active_duration_ms` (no in-memory replay object) |
| `tests/test_repository.py` | 10 persistence cases: round-trip fidelity, events-up-to-derived-end, restart persistence, FK cascade, mid-save rollback, pagination, key stats |
| `tests/test_sessions.py` | Updated to the repository; the full type → submit → results flow now exercises the database |
| `docs/DECISIONS.md` | ADR-034 (persistence contract, read-back reconstruction, retained-event suffix rule) |

- **Single-transaction save:** `create()` inserts the four table shapes with one connection; `commit()` on success and `rollback()` plus re-raise on any failure, verified by the mid-save-failure test (a duplicated `seq` that passes validation and replay but violates the `keystroke_events` UNIQUE constraint).
- **Retained events:** only validated events up to the derived end are stored; replay drops a strictly trailing suffix, so the repository retains `validated.events[:len(events) - dropped_after_end]` (the completing keystroke is retained; the timer-boundary event is not).
- **Read-back is reconstruction, not recomputation:** `SessionRecord` rebuilds `SessionMetrics` from the stored columns; `invalid_dwell_count` is recovered from `data_quality_json`, and `error_rate` applies the documented identity `100 − accuracy_pct` (ADR-034). `started_at` and the `ignored` counters are not persisted (blueprint §9 defines no columns for them).
- **`list_sessions(limit, offset)`** returns newest-first summaries plus the exact total, ready for P0-D2-04's history page.
- `pytest tests/ -q`: **469 passed** (459 previous + 10 new).

### Completed This Session — P0-D2-01 Database schema and connection

| File | Purpose |
|---|---|
| `app/schema.sql` | DDL transcribing blueprint §9: `sessions`, `session_metrics`, `keystroke_events`, `session_key_stats` |
| `app/db.py` | `connect()`, `apply_schema()`, `init_db()`, `get_db()`/`close_db()`; `SCHEMA_VERSION = 1` |
| `app/__init__.py` | `create_app(test_config)` now sets `DATABASE` (default `instance/typing.db`) and calls `init_db()` |
| `tests/conftest.py` | The `app` fixture creates the app with `DATABASE` in `tmp_path`, so tests never touch the developer database |
| `tests/test_db.py` | 25 schema/connection cases: fresh-run creation, column fidelity, indexes, constraints, cascade, `g.db` lifecycle, version guard |
| `docs/DECISIONS.md` | ADR-033 (types, CHECK constraints, index names, `user_version`, test isolation, blueprint column fidelity) |

- The schema is blueprint §9 verbatim. Be aware of the deliberate constraint details (ADR-033):
  - `sessions.duration_limit_ms` must be 15000/30000/60000 for `time` and NULL for `passage`; SQLite evaluates a CHECK with NULL as *passing*, so the constraint includes an explicit `IS NOT NULL` test for time mode.
  - `session_metrics` has **no `error_rate` and no `invalid_dwell_count` column** — the blueprint column list is complete. P0-D2-02 stores `invalid_dwell_count` and the warning counters in `data_quality_json`; `error_rate` is derived at read-back (`docs/METRICS.md` §4.4, ADR-034).
  - `keystroke_events.key` is NULL exactly for `up` events; `repeat` is 0/1; `(session_id, seq)` is UNIQUE.
  - `iki_hist_json` and `data_quality_json` are nullable TEXT columns reserved for P0-D2-02/P1.
- `apply_schema()` is idempotent (`CREATE TABLE IF NOT EXISTS`), records `PRAGMA user_version = 1`, and raises `RuntimeError` on a non-zero, unexpected schema version with the documented remedy (delete `instance/typing.db` during development; no migration path in the initial build).
- `connect()` sets `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`; `get_db()` stores one connection in `g` per request and `close_db()` runs at app-context teardown.
- First-run check: `create_app()` created `instance/typing.db` (git-ignored) with the four tables and `user_version = 1`.
- `pytest tests/ -q`: **459 passed** (434 previous + 25 new).

### Completed This Session — P0-D1-01 Scaffold

| File | Purpose |
|---|---|
| `run.py` | Development entry point: `create_app()` plus `app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)` for a single, Ctrl+C-friendly server process |
| `requirements.txt` | Direct dependencies only: `Flask>=3.0`, `pytest>=8.0` |
| `app/__init__.py` | `create_app()` factory; creates the Flask app and loads `app.config` via `from_object` |
| `app/config.py` | All 15 named metric thresholds from `docs/METRICS.md` §14; no metric calculations |
| `app/errors.py` | Nine documented API error codes plus `json_error()` in the documented response shape |
| `.gitignore` | Added `instance/`; existing `.venv/`, `venv/`, `__pycache__/`, `*.py[cod]`, and `.pytest_cache/` rules preserved |

### Completed This Session — P0-D1-02 Test Infrastructure

| File | Purpose |
|---|---|
| `tests/conftest.py` | `app`, `client`, and `db_conn` fixtures; `db_conn` is an in-memory `sqlite3` connection with `PRAGMA foreign_keys = ON` and no tables |
| `tests/test_fixtures.py` | Structural checks for the golden JSON fixtures only; no replay or metric logic |
| `tests/test_infrastructure.py` | Verifies the `app`, `client`, and `db_conn` fixtures |
| `tests/fixtures/golden_a.json` … `golden_g.json` | Golden examples A–G from `docs/METRICS.md` §13 |

- The DB-fixture ordering issue is resolved by ADR-018: no `app/db.py`, schema, or `init_db()` was added early.
- At P0-D1-02 completion: `pytest tests/ -v` reported **10 passed** (7 fixture-structure checks, 1 fixture-G check, 2 conftest fixture checks).

### Completed This Session — P0-D1-03 Replay Engine

| File | Purpose |
|---|---|
| `app/engine/replay.py` | Pure replay: buffer state machine, pending-key map, end derivation, error accounting, timed actions and dwell samples |
| `app/engine/__init__.py` | `analyze_session()` replay-stage entry point; metrics are P0-D1-04 |
| `tests/test_replay.py` | Golden fixtures A–G plus focused pending-key, full-buffer, boundary, and drop-after-end tests |
| `tests/fixtures/golden_g.json` | AMB-005 approved text, 2000 ms limit, end state, and derived error counts |
| `tests/fixtures/golden_f.json` | Added derived C/E/N/U/Ec/Eu counts for the invariant assertions |
| `tests/test_fixtures.py` | Updated fixture G checks for the approved values |

- Replay returns a structured `ReplayResult`; a passage run that never completes has `end_reason=None` and is left for the caller's `INCOMPLETE_SESSION` outcome check (ADR-020).
- Fixture G's values were completed under ADR-019 (AMB-005); its events and Backspace expectations are preserved.
- Fixture-level `timer_expiry` is mapped to the canonical engine value `time_up` in `tests/test_replay.py` (ADR-019).
- Invariants `E = U + Ec + Eu`, `K = C + E`, and `N ≤ K` are asserted for every fixture.
- `pytest tests/ -v`: **34 passed** at P0-D1-03 completion.

### Completed This Session — P0-D1-04 Metrics

| File | Purpose |
|---|---|
| `app/engine/metrics.py` | Pure metric formulas: Gross/Net WPM, accuracy, final accuracy, error rate, dwell, intervals `V`, pauses, IKI mean/median/sample SD/CV, consistency, per-key observations/IKI and dwell sums |
| `app/engine/__init__.py` | `SessionAnalysis` result type; `analyze_session()` now returns replay + metrics + key stats |
| `tests/test_metrics.py` | Golden fixtures A–G plus interval boundaries, IKI gates, consistency 29/30, zero-mean CV, dwell validity, per-key clean transitions |
| `tests/test_replay.py` | Updated the `analyze_session()` assertion to use `analysis.replay` |
| `tests/fixtures/golden_a.json` | IKI expectations changed to `null` under ADR-023 |
| `docs/DECISIONS.md` | ADR-021 (edge-case guards), ADR-022 (per-key attribution split), ADR-023 (fixture-A IKI conflict) |

- §8.5 sample-size rule wins for fixture A: with `|V| = 3 < 5`, `avg_iki_ms` and `iki_sd_ms` are `null` (ADR-023, author-approved).
- Edge-case guards: `T <= 0` → null WPM; `K = 0` → null accuracy/error rate; no pauses → `longest_pause_ms = null`; percentages stored unrounded (ADR-021).
- Per-key IKI/observations are keyed by expected character; dwell is keyed by physical `event.code` and includes Backspace (ADR-022).
- `pytest tests/ -v`: **91 passed** (34 previous + 57 metric tests).

### Completed This Session — P0-D1-05 Key Statistics and Heatmap Classification

| File | Purpose |
|---|---|
| `app/engine/keys.py` | `CHAR_TO_CODE` (all 95 printable ASCII characters), `wilson_ci()`, `pooled_baseline_error_rate()`, `classify_key()`, `classify_observation()`, `classify_key_stat()`, `SessionKeyStat`, `KeyClassification`, and `merge_session_key_stats()` |
| `app/engine/__init__.py` | `SessionAnalysis` now carries both the raw `key_stats` maps and the merged `session_key_stats` rows |
| `tests/test_keys.py` | 33 tests: ASCII coverage and shifted pairs, Wilson reference/boundaries/guards, baseline floor, n = 19/20 gate, all three weak conditions, strong/average, dwell invariance, merge unions, Backspace dwell-only rows, unmapped-character failure |
| `docs/DECISIONS.md` | ADR-024 (merge shape, classification gate, `None` bounds for insufficient, 1e-12 margin tolerance, `session_key_stats` on `SessionAnalysis`) |

- `CHAR_TO_CODE` maps capitals and lowercase letters to the same letter key, and shifted symbols to their base key (for example `!` → `Digit1`, `?` → `Slash`). It contains exactly ASCII 32–126.
- `merge_session_key_stats()` returns a dict keyed by `key_code`, sorted by code. It unions expected-character-derived keys with physical dwell codes; `Backspace` therefore appears with `attempts = 0`, and a dwell-only code never creates fake observations.
- `classify_key(e, b, lo, hi, x)` keeps the documented five-argument signature. `None` bounds mean the grey state; `classify_observation()` applies the `n >= 20` gate and returns the bounds and class in `KeyClassification`.
- Pooled baseline: `max(Σx/Σn, 0.01)`, or `None` when the scope has no observations. The weak margin uses a 1e-12 tolerance only to preserve the exact `>= 0.02` comparison in binary floating point.
- `pytest tests/ -v`: **124 passed** (91 previous + 33 key tests).

### Completed This Session — P0-D1-06 Validators

| File | Purpose |
|---|---|
| `app/validators.py` | `validate_session_payload()`, `ValidatedSessionPayload`, `ValidationError` (422) and `PayloadTooLargeError` (413); pure Python, no Flask/DB/metric logic |
| `tests/test_validators.py` | 57 test functions (190 cases): Unicode keys/codes, space/tilde acceptance, enums, required fields, seq gaps, `t` monotonicity, event/body limits, forbidden end fields, first-event rule, repeat rules, and both halves of the timer-boundary contract |
| `app/config.py` | Added `SUPPORTED_SCHEMA_VERSION`, `MIN_SESSION_EVENTS`, `MAX_SESSION_EVENTS`, `MAX_SESSION_BODY_BYTES`, `ALLOWED_TIME_LIMITS_MS`, `WORD_COUNT_MIN`, `WORD_COUNT_MAX` |
| `docs/DECISIONS.md` | ADR-025 (reject client-supplied `ended_at_ms`/`end_reason`, even null) and ADR-026 (validator API, 2 MiB body, timer boundary owned by replay, unknown-field policy, `started_at` policy) |

- Key and code checks use `re.fullmatch()` with `re.compile(r"[\x20-\x7E]")` and `r"[A-Za-z0-9]{1,32}"`; no Unicode-aware helpers.
- `_required()` takes an optional `path` so nested details report `text_ref.type`, `client.layout_hint`, `ignored.shortcuts`, and `events[0].t` instead of bare leaf names.
- Timer expiry remains a replay outcome: the validator accepts events at `t >= duration_limit_ms`, and `replay_events()` excludes them and sets `time_up`. Rejecting them during schema validation would turn a normal timer finish into a 422.
- Validation errors aggregate: every failing field gets its own `{field, problem}` detail where structurally possible.
- `pytest tests/ -v`: **314 passed** (124 previous + 190 validator cases).

### Completed This Session — P0-D1-07 Text Resolution

| File | Purpose |
|---|---|
| `app/data/passages.json` | 12 original ASCII passages (`p_001`–`p_012`, 222–260 characters each) with frozen order |
| `app/data/words_en.json` | 200 unique lowercase `a-z` words in a frozen order |
| `app/texts.py` | Cached loaders, `get_passage()`, `resolve_text()`, `generate_words()`, `words_for_duration()`, `validate_text_sources()`, `Passage`, `TextNotFoundError`, `TextSourceError` |
| `app/__init__.py` | `create_app()` now calls `validate_text_sources()` before returning the app |
| `app/config.py` | Added `WORDS_FOR_DURATION_MS = {15000: 120, 30000: 200, 60000: 350}` |
| `tests/test_texts.py` | 76 cases: content contract, frozen seed mapping, count/duration boundaries, passage/word resolution, `TEXT_NOT_FOUND`, malformed sources, startup wiring, engine integration |
| `docs/DECISIONS.md` | ADR-027 (author-approved original content, frozen ordering, generator, duration sizing, startup guard); AMB-001/AMB-002 marked resolved |

- All twelve passages are original prose written for this project, not copied from Monkeytype, Keybr or public-domain sources. The author approved authoring them in-session; editorial review remains theirs.
- Generation is frozen as shuffle-and-extend: `rng.shuffle()` cycles the 200-word list until `count` (10–400) is reached, then joins with single spaces. For `count <= 200` this is exactly one shuffle plus a slice.
- `resolve_text({"type": "passage", "id": ...})` returns the stored text; an unknown id raises `TextNotFoundError` with `code == TEXT_NOT_FOUND` and `status == 404`. Word refs delegate to `generate_words(seed, count)`.
- `validate_text_sources()` rejects unreadable/invalid JSON, malformed structure, duplicate passage ids, empty strings, any character outside ASCII 32–126 (including newline/tab), and words that are not lowercase `a-z`.
- `pytest tests/ -v`: **390 passed** (314 previous + 76 text-resolution cases).

### Completed This Session — P0-D1-08 Frontend foundation

| File | Purpose |
|---|---|
| `app/static/css/tokens.css` | Light and dark design tokens: approved palettes, typography, 8-pt spacing, layout, radii, motion, focus and heatmap colours; print forces the light palette |
| `app/static/css/base.css` | Self-hosted `@font-face` rules, reset, global typography, application shell, nav, theme toggle, skip link, focus rings, reduced-motion handling |
| `app/static/js/theme.js` | Toggle handler: persists `localStorage["tba-theme"]`, updates the accessible label, dispatches `tba:themechange` |
| `app/templates/base.html` | Shared shell: inline blocking theme init, font preloads, CSS imports, nav, toggle, skip link, content/meta/head/scripts blocks |
| `app/static/fonts/lexend-latin-variable.woff2` | Lexend v26 variable font, latin subset, 39,680 bytes |
| `app/static/fonts/jetbrains-mono-latin-variable.woff2` | JetBrains Mono v24 variable font, latin subset, 40,404 bytes |
| `app/static/fonts/OFL-Lexend.txt`, `OFL-JetBrainsMono.txt` | SIL OFL 1.1 licence texts |
| `app/static/vendor/chart.umd.min.js` | Chart.js 4.4.7 minified UMD build, 205,615 bytes |
| `app/static/vendor/CHARTJS-LICENSE.md` | Chart.js MIT licence |
| `tests/test_infrastructure.py` | Two frontend checks: base-template rendering/script ordering/local-only URLs, and static asset resolution incl. WOFF2 magic bytes and Chart.js header |
| `docs/DECISIONS.md` | ADR-028 (asset provenance, font subset, theme responsibilities, literal nav paths) |

- The inline script runs before `tokens.css` and `base.css`, sets `data-theme` from storage or `prefers-color-scheme`, and removes `.no-transition` after the window `load` event.
- `theme.js` is an ES module using `const`/`let` only; no `var`, no external imports.
- The nav uses literal `href` paths (`/`, `/analytics`, `/keyboard`, `/history`) because page endpoints arrive in P0-D1-10. Those links currently 404 by design.
- `tokens.css` is the only stylesheet with raw colour values; `base.css` consumes custom properties only.
- Fonts are variable WOFF2 files with `font-display: swap`; JetBrains Mono carries `font-variant-numeric: tabular-nums` via the shared `.numeric` and code-element rule.
- Verified in Chromium against a temporary (uncommitted) local server: OS dark fallback, toggle to light, persistence across reload, `.no-transition` removal, Lexend and JetBrains Mono loaded, tabular figures, and no console errors.
- `pytest tests/ -v`: **392 passed** (390 previous + 2 frontend checks).

### Completed This Session — P0-D1-09 Typing screen and pulled-forward routes

| File | Purpose |
|---|---|
| `app/static/js/capture.js` | Keyboard capture per `docs/EVENT_SCHEMA.md`: printable/Backspace rules, pending map, repeat handling, AltGr, timestamp fallback logging, keyup pairing, focus/window/visibility cancellation and listener cleanup |
| `app/static/js/typing-engine.js` | Idle → running → finished attempt state, character-state rendering, caret and scroll-follows-caret, provisional time/WPM/accuracy, completion, timer expiry, full-buffer message |
| `app/static/js/test-page.js` | Config strip, aborted/token-guarded text fetch, passage selector, Esc restart, focus handling and capture/engine wiring |
| `app/templates/test.html` | Test screen: config strip, provisional live row, three-line viewport, caret, status region, Esc footer hint |
| `app/static/css/test.css` | Test layout and character presentation using design tokens only; `[hidden]` enforcement and caret states |
| `app/routes/__init__.py`, `pages.py` | Route package and `GET /` rendering `test.html` with the word-count map |
| `app/routes/api.py` | Three P0 text GET endpoints with ADR-029 response shapes and error handling |
| `app/__init__.py` | Registers `pages_bp` and `api_bp` after the startup text check |
| `tests/test_api.py` | 18 cases: home page, passage list/order/labels, single passage, unknown passage, word generation, count bounds and invalid counts |
| `tests/test_infrastructure.py` | `GET /` now expects 200; static asset checks include `test.css`, `capture.js`, `typing-engine.js`, `test-page.js` |
| `docs/DECISIONS.md` | ADR-029 (text API shapes and passage label, resolves AMB-003); ADR-030 (pulled-forward page/text routes) |

- Capture uses `event.key === "Backspace"` for Backspace and `event.code` for down/up pairing. Repeat Backspace downs never read, write or overwrite the pending map.
- First accepted printable keydown starts the test. Escape is owned by the page controller: while running it cancels and returns to idle with no message; Esc also restarts from idle/finished.
- Time-mode events with `t >= duration_limit_ms` are not recorded; the engine finishes as `time_up`. Completion requires the buffer to equal the text exactly.
- At a full buffer with mistakes, printable keys are blocked by both capture and engine, and the UI shows "Fix the highlighted characters to finish". Backspace clears the message and allows correction.
- Focus loss while running cancels and discards the attempt, shows the documented "Test cancelled. The window lost focus." message, and reattaches capture for the next attempt.
- The live row is hidden until the first keystroke and labelled **provisional**. WPM is a client-only net-style estimate over the current buffer; accuracy is accepted-keystroke accuracy. No final metrics or submission exist yet.
- Scroll-follows-caret was verified: after 130 characters the caret was on layout line 3 and the track had shifted by one line, leaving it on visible line 2.
- `pytest tests/ -v`: **410 passed** (392 previous + 18 new route cases plus the updated infrastructure checks).

### Completed This Session — P0-D1-10 First vertical slice

| File | Purpose |
|---|---|
| `app/session_store.py` | Thread-safe, process-local `InMemorySessionStore` attached as `app.extensions["tba_session_store"]`; `uuid4().hex` ids, UTC `created_at`; replaced by the repository in P0-D2-02 |
| `app/routes/api.py` | `POST /api/sessions`: size limit, JSON parsing, validator delegation, text resolution, authoritative replay/metrics, outcome checks and the documented 201 shape |
| `app/routes/pages.py` | `GET /results/<session_id>` server-renders the stored analysis; unknown ids return 404 |
| `app/templates/results.html` | Tier 1/2/3 metrics, `—` for unavailable values, conditional `Eu`, data-quality section, timing-honesty note and New test links |
| `app/static/css/components.css` | Results and shared component styles using design tokens only |
| `app/static/js/capture.js` | Accepted-event accumulation with contiguous `seq` and `getEvents()`; no reconstruction of rejected events |
| `app/static/js/test-page.js` | One-shot payload construction and `POST /api/sessions`, redirect on success, `queueMicrotask` deferral so the completing keydown is recorded first |
| `app/engine/__init__.py` | `DataQualityWarning` and `warnings` for `orphan_up`, `missing_up`, `open_at_end`, `invalid_dwell`, `dropped_after_end` |
| `app/engine/metrics.py` | Added `invalid_dwell_count` to `SessionMetrics` |
| `app/config.py` | Added `ANALYSIS_VERSION = 1` |
| `tests/test_sessions.py` | 24 cases: engine-metric equality, results rendering, passage completion, timer boundary, incomplete/too-short rejection, invalid JSON, validation, forbidden fields, unknown text, invalid sequences, oversized body, `Eu` display, invalid dwell, unknown result id and frontend contracts |

- The server remains the sole metric authority: the results page renders `analysis.metrics` and `replay.active_duration_ms`; no metric math exists in routes or JavaScript.
- `POST /api/sessions` returns `201 {session_id, metrics, warnings, links}`. `metrics` is the serialised `SessionMetrics` plus `mode`, `duration_limit_ms`, `active_duration_ms`, `end_reason` and `analysis_version`. `warnings` lists only non-zero tolerated conditions.
- Passage completion exposed a genuine bug during Chromium verification: submission was built synchronously inside the completing keydown handler, so the final character was missing and the server returned `INCOMPLETE_SESSION`. `onFinish` now defers submission with `queueMicrotask`; `tests/test_sessions.py` asserts the deferral.
- Chromium verification: 15 s time flow (Start → Type → Finish → Submit → Results → New test) returned the server metrics with `Active duration 15.0 s`; passage mode completed 242 characters with 100% accuracy and `completed`; both results pages showed the timing-honesty note, data-quality section and working New test links; zero console errors.
- `pytest tests/ -v`: **434 passed** (410 previous + 24 vertical-slice cases).

### Environment

| Field | Value |
|---|---|
| Python | 3.14.7 |
| Virtual environment | `.venv` (Python 3.14.7) |
| Direct dependencies | Flask 3.1.3, pytest 9.2.0 |
| Transitive dependencies | blinker 1.9.0, click 8.5.0, colorama 0.4.6, iniconfig 2.3.1, itsdangerous 2.2.0, Jinja2 3.1.6, MarkupSafe 3.0.4, packaging 26.3, pluggy 1.7.0, Pygments 2.21.0, Werkzeug 3.1.9 |
| `pip check` | No broken requirements |
| Minimum Python | Unchanged at 3.10+ per blueprint |

### Verification

- `python -m pytest tests\ -q`: **474 passed** (7 fixture-structure checks, 1 fixture-G check, 2 conftest fixture checks, 2 infrastructure checks, 18 API/page cases, 24 replay tests, 57 metric tests, 33 key tests, 190 validator cases, 76 text-resolution cases, 25 vertical-slice cases, 25 schema/connection cases, 10 repository tests, 2 results-UI contracts). The vertical-slice and results-UI cases cover session detail, tooltips, data quality and conditional `Eu`.
- `GET /` returns **200** and renders `test.html`. `GET /api/texts/passages`, `/api/texts/passages/p_001` and `/api/texts/words?count=200` all return **200** with the ADR-029 shapes; unknown passages return **404 TEXT_NOT_FOUND**; invalid counts return **422 VALIDATION_ERROR** with `field: "count"`.
- `POST /api/sessions` returns **201** with the documented `{session_id, metrics, warnings, links}` shape; malformed JSON is **400 INVALID_JSON**, schema failures are **422 VALIDATION_ERROR**, oversized bodies are **413 PAYLOAD_TOO_LARGE**, unknown passages are **404 TEXT_NOT_FOUND**, invalid sequences are **422 INVALID_EVENT_SEQUENCE**, incomplete passages are **422 INCOMPLETE_SESSION**, and short sessions are **422 SESSION_TOO_SHORT**.
- `GET /api/sessions/<id>` returns **200** with `{ session, metrics, key_stats }` (ADR-035); an unknown id returns **404 NOT_FOUND** with `field: "session_id"`. The route reads only through `SessionRepository.get()`/`get_key_stats()`.
- `GET /results/<id>` renders the persisted server metrics from `SessionRecord`; an unknown id returns **404**. The results template distinguishes unavailable (`—`) from zero, shows `Eu` only when non-zero, and shows the Data quality section only when warnings exist or `zero_interval_count > 0`. Every metric label carries an accessible `?` tooltip (`button[data-metric-help]` + `role="tooltip"`), wired by `app/static/js/results-page.js`.
- `POST /api/sessions` saves all four table shapes in one transaction and the 201 response is serialised from the persisted record (`SessionRepository.get()`), so response, page and database hold identical numbers. A mid-save failure leaves the database untouched (rollback test).
- Chromium check against the running Flask server: 15 s time flow (Start → Type → Finish → Submit → Results → New test) and full 242-character passage completion both reached the results page with server-computed numbers, the timing-honesty note, the data-quality section where applicable, and working New test links; zero console errors.
- Playwright smoke check on a real persisted session (`053d6adeee02460ead0559dfda2b7204`): 25 metric tooltips present; hover reveals, click pins, `:focus-visible` reveals, Escape closes and blurs, outside click closes; `Eu` and Data quality both visible. Only console error is the pre-existing `/favicon.ico` 404.
- The final keyup of the completing keystroke is not captured because capture listeners are removed on finish. This is deliberate per `docs/EVENT_SCHEMA.md` §5 and is covered by the server's tolerated `open_at_end` condition.
- `app/routes/api.py` contains no metric math and no SQL; it delegates every text lookup/generation to `app/texts.py`.
- `app/static/js/results-page.js` contains no fetching and no metric math; it only manages tooltip ARIA state and dismissal. The page stays server-rendered from the persisted record.
- `tests/` now contains the conftest, seven golden JSON fixtures, fixture checks, replay tests, metric tests, key-map/classification tests, validator tests, text-resolution tests, API/page tests and the frontend smoke checks.
- No compatibility issues with Python 3.14.7.

---

## Exact Next Task

**Task ID:** P0-D2-04
**Title:** History page

**Scope (from `docs/TASKS.md`):**
1. Implement `GET /api/sessions?limit=&offset=` returning `{ items, total }`.
2. Implement `app/templates/history.html` and `app/static/js/history-page.js`.
3. 25 rows per page with pagination controls.
4. Row click navigates to `/results/<id>`.
5. Empty state: "No sessions yet."
6. **Acceptance:** history lists correctly; pagination works; row click navigates.

**Starting point:**
- P0-D2-03 is complete: `GET /api/sessions/<id>` returns `{ session, metrics, key_stats }` (ADR-035) and `/results/<id>` renders the persisted session through the three-tier template with accessible metric tooltips.
- `SessionRepository.list_sessions(limit, offset)` already returns newest-first summaries plus the exact total, so the history endpoint is mostly serialisation.
- `app/repository.py` remains the single SQL owner; do not put SQL or metric math in routes.
- Reuse `components.css` and the existing page patterns (`app/routes/pages.py`, `app/static/js/test-page.js`) rather than inventing a new surface.
- The literal nav path `/history` in `base.html` should become `url_for` once the page endpoint exists (ADR-028).
- `pytest tests/ -q`: **474 passed**.
- Do not commit or push without approval.

---

## Outstanding Issues for the Next Agent

1. **Passage and word content now exists** (ADR-027) and is frozen for reproducibility. The twelve passages are original, author-approved in approach, but still need the author's editorial review before release. Do not reorder or rewrite either file without a new ADR.
2. **`ended_at_ms`/`end_reason` are rejected** under ADR-025, even when `null`. Do not relax this without a new decision.
3. **The timer boundary belongs to replay**, not validation (ADR-026). The validator accepts `t >= duration_limit_ms`; `replay_events()` excludes those events and sets `time_up`. Do not move this rule into the validator.
4. **Validation limits and duration sizing live in `app/config.py`.** `SUPPORTED_SCHEMA_VERSION`, `MIN/MAX_SESSION_EVENTS`, `MAX_SESSION_BODY_BYTES` (2 MiB), `ALLOWED_TIME_LIMITS_MS`, `WORD_COUNT_MIN/MAX` and `WORDS_FOR_DURATION_MS` are named constants; do not hard-code them in routes.
5. **`docs/UI_DESIGN.md` §7** references `docs/METRICS.md` §6 for the Wilson heuristic; it should be §12. Correct during UI documentation cleanup.
6. **`README.md`** is absent; leave for P0-D3-05.
7. **`app/routes/__init__.py`** now exists as the route package docstring; `pages.py` and `api.py` live beside it and are registered in `create_app()`.
8. **HEAD is `4992846 feat(db): persistence — single-transaction save and round-trip tests`** (P0-D2-02) on `database-version`, in sync with `origin/database-version`. The only uncommitted work is the complete P0-D2-03 (API + results-page UI, ADR-035) and its doc updates. Do not commit or push without approval.
9. **Fixture A's IKI values are null by decision.** The §13 row's mean/SD arithmetic conflicts with §8.5; the author ruled §8.5 wins (ADR-023). Do not "fix" this by restoring `800.0`/`0.0`.
10. **`session_key_stats` rows are now stored** with every session (`executemany` in the same transaction as the session row, ADR-034); `get_key_stats(id)` reads them back ordered by key code.
11. **Heatmap classification is not yet wired to an endpoint.** `classify_observation()` and `pooled_baseline_error_rate()` are reused by P0-D3-01; do not duplicate the formula in routes or SQL.
12. **The test page is live at `/`; `analytics`, `keyboard` and `history` still 404.** Those routes belong to later tasks, so the literal nav paths remain deliberate (ADR-028). Replace them with `url_for` as each page endpoint lands.
13. **Chart.js is vendored but not referenced by any template yet.** It stays unused until the analytics/chart pages (P0-D2-06); do not add it to `base.html`.
14. **Only the latin font subsets are vendored.** All app content is ASCII 32–126. Out-of-subset glyphs use the documented fallback stacks; add subsets only with a new ADR and the corresponding licence/version note.
15. **The inline theme script and `theme.js` deliberately split responsibilities.** First paint belongs to the inline script; later toggles belong to `theme.js`. Do not move the storage read into the module, or a reload will flash the wrong theme.
16. **Accepted-event accumulation lives in `capture.js`.** It records only events the engine accepts and assigns `seq` at record time. Do not reconstruct rejected events or rederive pending state in the route.
17. **The completion keystroke's keyup is intentionally lost.** Capture stops listening when the attempt finishes (EVENT_SCHEMA §5), so the server may report `open_at_end`; this is tolerated by design.
18. **Provisional live stats are client-only.** WPM and accuracy in the live row are estimates over the current buffer and accepted keystrokes. Never store them or present them as final; the server remains the sole metric authority.
19. **Submission is deferred with `queueMicrotask` (ADR-031).** Passage mode finishes inside the completing keydown handler, before capture records it. Do not make `onFinish` call `submitAttempt()` synchronously; a regression test in `tests/test_sessions.py` enforces the deferral.
20. **Sessions persist across restarts.** The in-memory store (ADR-032) is replaced by `SessionRepository` behind the same `app.extensions["tba_session_store"]` key (ADR-034). Do not add SQL outside `app/repository.py` or tables outside blueprint §9.
21. **`GET /api/sessions/<id>` returns `{ session, metrics, key_stats }` (ADR-035); `GET /results/<id>` renders the persisted `SessionRecord` server-side.** P0-D2-03 is complete; keep the results surface in `results.html`/`components.css`/`results-page.js` rather than creating a second one. `results-page.js` must stay presentation-only: no fetching, no metric math.
22. **`invalid_dwell_count` is part of `SessionMetrics`.** Keep it in sync with the `invalid_dwell` warning (`count > 0` emits the warning). Do not re-derive it in routes.
23. **The development server runs without the reloader.** `run.py` calls `app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)`. Do not reintroduce the reloader, and do not launch the server through a detached shell; `Ctrl+C` in the starting terminal is the supported stop.
24. **`session_metrics` has no `error_rate` and no `invalid_dwell_count` column** (ADR-033, ADR-034); the blueprint §9 column list is complete. The repository serialises `invalid_dwell_count` and the warning counters into `data_quality_json` and derives `error_rate = 100 − accuracy_pct` at read-back per `docs/METRICS.md` §4.4. Do not widen the schema for them.
25. **Schema matches blueprint §9 verbatim, with SQLite-specific CHECK nuances** (ADR-033): `sessions.duration_limit_ms` must be 15000/30000/60000 for `time` and NULL for `passage`; the constraint carries an explicit `IS NOT NULL` because SQLite treats a NULL CHECK result as passing. `PRAGMA user_version` is 1; there is no migration path — a mismatched non-zero version aborts startup with the documented remedy (delete `instance/typing.db` during development).
26. **Test apps never touch the developer database.** The `app` fixture in `tests/conftest.py` passes `DATABASE` inside `tmp_path` via `create_app(test_config)`; keep this isolation for all future persistence work.
27. **Results tooltips are progressive enhancement.** The template ships a `title` fallback plus a `role="tooltip"` panel; `results-page.js` assigns ids, sets `aria-describedby` and removes `title`. Do not replace this with `title`-only help text or move metric definitions into JavaScript — the definitions are documentation and belong in the template.

---

## Important Reminders for the Next Agent

1. Read `AGENTS.md` in full before writing code.
2. Do not commit or push unless the user approves.
3. Run `pytest` before any approved commit; do not commit a failing suite.
4. The engine (`app/engine/`) must have zero HTTP calls and zero DB calls.
5. Do not install packages not listed in `requirements.txt`.
6. Do not create files outside the approved structure in `docs/ARCHITECTURE.md` §8 without logging the decision in `docs/DECISIONS.md`.
7. Golden fixtures A–G in `docs/METRICS.md` §13 must pass before moving past P0-D1-04; the fixture-A IKI contradiction is resolved under ADR-023.
