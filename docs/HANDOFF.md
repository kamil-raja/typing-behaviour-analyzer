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

## Current State (as of 2026-11-06)

### Git

| Field | Value |
|---|---|
| **Branch** | `feature/project-foundation` |
| **Status** | Uncommitted P0-D1-08 changes: new `app/static/css/tokens.css`, `app/static/css/base.css`, `app/static/js/theme.js`, `app/templates/base.html`, `app/static/fonts/` (two WOFF2 fonts + two OFL texts), `app/static/vendor/chart.umd.min.js` + MIT licence; modified `tests/test_infrastructure.py`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md` |
| **Last commit** | `4599be0 feat(texts): implement typing text resolution` (P0-D1-07, committed externally) |
| **Tags** | None yet |
| **Commit/push** | **None performed by this agent in P0-D1-08.** P0-D1-01 was committed in `9c02975`; P0-D1-02 in `147ec1e`; P0-D1-03 in `e9e2215`; P0-D1-04 in `61d8c36`; P0-D1-05 in `55130e1`; P0-D1-06 in `1c0137a`; P0-D1-07 in `4599be0`. The branch is 6 commits ahead of `origin/feature/project-foundation`; nothing was pushed. |

`.venv/`, `__pycache__/`, and `instance/` are ignored and are not part of the working-tree changes.

### Completed This Session — P0-D1-01 Scaffold

| File | Purpose |
|---|---|
| `run.py` | Development entry point: `app = create_app(); app.run(debug=True)` |
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

- Activating `.venv` resolves `python` to `.venv\Scripts\python.exe` (Python 3.14.7).
- `import flask, pytest` succeeds.
- `create_app()` returns a Flask application (`app.name == "app"`).
- All 15 `METRICS.md` §14 constants load into `app.config`.
- `python run.py` starts on `http://127.0.0.1:5000` with debug mode on.
- `GET /` returns **404** — expected because no page routes exist yet (P0-D1-10).
- `GET /static/css/tokens.css`, `/static/css/base.css`, `/static/js/theme.js`, both WOFF2 fonts and `/static/vendor/chart.umd.min.js` all return **200** with correct MIME types.
- `base.html` renders in a request context; the theme bootstrap appears before both stylesheets and the rendered document contains no external URLs.
- Chromium check: dark OS preference applied on first load with empty storage; toggle switched to light and persisted `tba-theme`; reload restored the saved theme; `.no-transition` was removed after load; Lexend and JetBrains Mono both loaded; `.numeric` computed to `tabular-nums`; zero console errors.
- `json_error()` verified for `VALIDATION_ERROR` (422 with supplied details) and `INVALID_JSON` (400 with empty details).
- `pytest tests/ -v`: **392 passed** (7 fixture-structure checks, 1 fixture-G check, 2 conftest fixture checks, 2 frontend checks, 24 replay tests, 57 metric tests, 33 key tests, 190 validator cases, 76 text-resolution cases).
- `tests/` now contains the conftest, seven golden JSON fixtures, fixture checks, replay tests, metric tests, key-map/classification tests, validator tests, text-resolution tests, and the frontend smoke checks in `test_infrastructure.py`.
- No compatibility issues with Python 3.14.7. Flask's deprecated `__version__` was used only in an ad-hoc check, not in project code.

---

## Exact Next Task

**Task ID:** P0-D1-09
**Title:** Frontend — capture and typing engine

**Scope (from `docs/TASKS.md`):**
1. Implement `app/static/js/capture.js` per `docs/EVENT_SCHEMA.md`:
   - Keydown/keyup listeners on the passage viewport.
   - Pending map, repeat handling, orphan up tracking.
   - `t` calculation from the first accepted keydown.
   - Timestamp fallback with diagnostic logging.
   - Focus/blur/visibilitychange handlers.
   - Full-buffer enforcement.
2. Implement `app/static/js/typing-engine.js`: UI state machine (idle → running → finished/cancelled), live WPM/accuracy display (provisional), caret movement, character state rendering.
3. Implement `app/templates/test.html` and `app/static/css/test.css`.
4. Implement `app/static/js/test-page.js` (config strip, text fetch, test orchestration).
5. **Acceptance:** typing test runs in the browser; events are captured correctly; Tab never intercepted; focus loss cancels test; Esc cancels test.

**Starting point:**
- `app/templates/base.html` now provides the shell, nav, theme toggle and `head` / `content` / `footer` / `scripts` blocks. `test.html` must extend it.
- `tokens.css` and `base.css` are loaded globally. Do not add hex literals to `test.css`; use the tokens.
- `theme.js` is already loaded by `base.html` and dispatches `tba:themechange`. It is the only frontend JS module so far.
- Chart.js is vendored but intentionally unused until P0-D2-06.
- No page routes exist yet. P0-D1-10 adds `GET /`; until then, render `test.html` through an ad-hoc test route or the test client.
- Nav links use literal paths and currently 404 by design (ADR-028).
- Content is frozen: do not edit `passages.json` or `words_en.json` ordering without a new ADR (ADR-027).
- `docs/UI_DESIGN.md` §4 and `docs/EVENT_SCHEMA.md` §4–§7 are the authoritative sources for the test screen and capture rules.

---

## Outstanding Issues for the Next Agent

1. **Passage and word content now exists** (ADR-027) and is frozen for reproducibility. The twelve passages are original, author-approved in approach, but still need the author's editorial review before release. Do not reorder or rewrite either file without a new ADR.
2. **`ended_at_ms`/`end_reason` are rejected** under ADR-025, even when `null`. Do not relax this without a new decision.
3. **The timer boundary belongs to replay**, not validation (ADR-026). The validator accepts `t >= duration_limit_ms`; `replay_events()` excludes those events and sets `time_up`. Do not move this rule into the validator.
4. **Validation limits and duration sizing live in `app/config.py`.** `SUPPORTED_SCHEMA_VERSION`, `MIN/MAX_SESSION_EVENTS`, `MAX_SESSION_BODY_BYTES` (2 MiB), `ALLOWED_TIME_LIMITS_MS`, `WORD_COUNT_MIN/MAX` and `WORDS_FOR_DURATION_MS` are named constants; do not hard-code them in routes.
5. **`docs/UI_DESIGN.md` §7** references `docs/METRICS.md` §6 for the Wilson heuristic; it should be §12. Correct during UI documentation cleanup.
6. **`README.md`** is absent; leave for P0-D3-05.
7. **`app/routes/__init__.py`** is not specified; decide when implementing routes.
8. **P0-D1-07 is committed** as `4599be0` (externally). **P0-D1-08 changes are uncommitted.** HEAD is `4599be0`. The branch is 6 commits ahead of `origin/feature/project-foundation`; do not commit or push without approval.
9. **Fixture A's IKI values are null by decision.** The §13 row's mean/SD arithmetic conflicts with §8.5; the author ruled §8.5 wins (ADR-023). Do not "fix" this by restoring `800.0`/`0.0`.
10. **`session_key_stats` rows are ready for persistence but not yet stored.** P0-D2-02 owns the repository insert; `SessionKeyStat` field names match the blueprint §9 columns exactly.
11. **Heatmap classification is not yet wired to an endpoint.** `classify_observation()` and `pooled_baseline_error_rate()` are reused by P0-D3-01; do not duplicate the formula in routes or SQL.
12. **The base nav links use literal paths and all 404 until P0-D1-10.** This is deliberate (ADR-028); `url_for` cannot be used for endpoints that do not exist. Replace with `url_for` when the page routes arrive.
13. **Chart.js is vendored but not referenced by any template yet.** It stays unused until the analytics/chart pages (P0-D2-06); do not add it to `base.html`.
14. **Only the latin font subsets are vendored.** All app content is ASCII 32–126. Out-of-subset glyphs use the documented fallback stacks; add subsets only with a new ADR and the corresponding licence/version note.
15. **The inline theme script and `theme.js` deliberately split responsibilities.** First paint belongs to the inline script; later toggles belong to `theme.js`. Do not move the storage read into the module, or a reload will flash the wrong theme.

---

## Important Reminders for the Next Agent

1. Read `AGENTS.md` in full before writing code.
2. Do not commit or push unless the user approves.
3. Run `pytest` before any approved commit; do not commit a failing suite.
4. The engine (`app/engine/`) must have zero HTTP calls and zero DB calls.
5. Do not install packages not listed in `requirements.txt`.
6. Do not create files outside the approved structure in `docs/ARCHITECTURE.md` §8 without logging the decision in `docs/DECISIONS.md`.
7. Golden fixtures A–G in `docs/METRICS.md` §13 must pass before moving past P0-D1-04; the fixture-A IKI contradiction is resolved under ADR-023.
