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
| **Status** | Uncommitted P0-D1-04 changes: new `app/engine/metrics.py` and `tests/test_metrics.py`; modified `app/engine/__init__.py`, `tests/test_replay.py`, `tests/fixtures/golden_a.json`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `docs/HANDOFF.md` |
| **Last commit** | `e9e2215 feat(engine): implement event replay` (previous: `147ec1e test: add test infrastructure and golden fixtures`) |
| **Tags** | None yet |
| **Commit/push** | **None performed by this agent in P0-D1-04.** P0-D1-01 was committed in `9c02975`; P0-D1-02 in `147ec1e`; P0-D1-03 was committed externally in `e9e2215`. The branch is 2 commits ahead of `origin/feature/project-foundation`; nothing was pushed. |

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
- Per-key IKI/observations are keyed by expected character; dwell is keyed by physical `event.code` and includes Backspace (ADR-022). Merging via `CHAR_TO_CODE` is P0-D1-05.
- `pytest tests/ -v`: **91 passed** (34 previous + 57 metric tests).

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
- `GET /` returns **404** — expected because no routes exist yet.
- `json_error()` verified for `VALIDATION_ERROR` (422 with supplied details) and `INVALID_JSON` (400 with empty details).
- `pytest tests/ -v`: **91 passed** (7 fixture-structure checks, 1 fixture-G check, 2 conftest fixture checks, 24 replay tests, 57 metric tests).
- `tests/` now contains the conftest, seven golden JSON fixtures, fixture checks, replay tests, and metric tests. Key-map/heatmap tests do not exist yet.
- No compatibility issues with Python 3.14.7. Flask's deprecated `__version__` was used only in an ad-hoc check, not in project code.

---

## Exact Next Task

**Task ID:** P0-D1-05
**Title:** Engine — key stats and heatmap classification

**Scope (from `docs/TASKS.md`):**
1. Implement `app/engine/keys.py`:
   - `CHAR_TO_CODE` table mapping all printable ASCII 32–126 to US-QWERTY key codes.
   - `wilson_ci(x, n, z=1.96)`.
   - `classify_key(e, b, lo, hi, x) -> "weak" | "average" | "strong" | "insufficient"`.
2. Write `tests/test_keys.py`:
   - Wilson(3, 20) ≈ `[0.052, 0.360]`.
   - `n < HEATMAP_MIN_N` → grey/insufficient; `n = 20` → classified.
   - Weak requires `lo > b` AND `e - b >= 0.02` AND `x >= 3`.
   - A long dwell never changes classification.
   - `CHAR_TO_CODE` covers all 95 printable ASCII characters.
3. Merge `metrics.compute_key_stats()` output into `key_code`-keyed `session_key_stats` rows using `CHAR_TO_CODE` (ADR-022).

**Starting point:**
- `app.engine.analyze_session()` returns `SessionAnalysis(replay, metrics, key_stats)`.
- `SessionMetrics` exposes all stored session metrics plus `error_rate`.
- `KeyStats.observations_by_char` (attempts, errors, iki_count, iki_sum_ms) is keyed by expected character.
- `KeyStats.dwell_by_code` (dwell_count, dwell_sum_ms) is keyed by physical key code and already includes Backspace.
- `app/config.py` already holds `HEATMAP_MIN_N`, `HEATMAP_BASELINE_FLOOR`, `HEATMAP_WEAK_MARGIN`, `HEATMAP_WEAK_MIN_X`, `HEATMAP_Z`, `DWELL_LONG_RATIO`.

---

## Outstanding Issues for the Next Agent

1. **Word list and passage texts** are missing (`AMB-001`, `AMB-002`); handle in P0-D1-07.
2. **`ended_at_ms`/`end_reason` handling** ("reject" vs "ignore") is ambiguous; decide and document before validator implementation.
3. **Non-metric application limits** (request size, event counts, allowed durations, word counts) are not formally enumerated; add only when the relevant validation/API tasks specify them.
4. **`docs/UI_DESIGN.md` §7** references `docs/METRICS.md` §6 for the Wilson heuristic; it should be §12. Correct during UI documentation cleanup.
5. **`README.md`** is absent; leave for P0-D3-05.
6. **`app/routes/__init__.py`** is not specified; decide when implementing routes.
7. **P0-D1-04 changes are uncommitted.** HEAD is `e9e2215` (P0-D1-03 committed externally); P0-D1-01 was committed in `9c02975`, P0-D1-02 in `147ec1e`. The branch is 2 commits ahead of origin; do not commit or push without approval.
8. **Per-key merge is deferred.** `metrics.compute_key_stats()` deliberately returns two maps (expected-character observations/IKI and physical-code dwell). P0-D1-05 must merge them through `CHAR_TO_CODE`; do not guess a mapping before then (ADR-022).
9. **Fixture A's IKI values are null by decision.** The §13 row's mean/SD arithmetic conflicts with §8.5; the author ruled §8.5 wins (ADR-023). Do not "fix" this by restoring `800.0`/`0.0`.

---

## Important Reminders for the Next Agent

1. Read `AGENTS.md` in full before writing code.
2. Do not commit or push unless the user approves.
3. Run `pytest` before any approved commit; do not commit a failing suite.
4. The engine (`app/engine/`) must have zero HTTP calls and zero DB calls.
5. Do not install packages not listed in `requirements.txt`.
6. Do not create files outside the approved structure in `docs/ARCHITECTURE.md` §8 without logging the decision in `docs/DECISIONS.md`.
7. Golden fixtures A–G in `docs/METRICS.md` §13 must pass before moving past P0-D1-04; the fixture-A IKI contradiction is resolved under ADR-023.
