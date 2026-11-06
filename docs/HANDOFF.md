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
| **Status** | Uncommitted P0-D1-03 changes: modified `docs/DECISIONS.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`, `docs/TASKS.md`, `tests/fixtures/golden_f.json`, `tests/fixtures/golden_g.json`, `tests/test_fixtures.py`; untracked `app/engine/`, `tests/test_replay.py` |
| **Last commit** | `147ec1e test: add test infrastructure and golden fixtures` (previous: `c0d100c chore: remove accidental diff file`) |
| **Tags** | None yet |
| **Commit/push** | **None performed by this agent in P0-D1-03.** P0-D1-01 was committed in `9c02975`; P0-D1-02 was committed externally in `147ec1e`; P0-D1-03 remains uncommitted. The branch is 1 commit ahead of `origin/feature/project-foundation`; nothing was pushed. |

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
- `pytest tests/ -v`: **34 passed**.

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
- `pytest tests/ -v`: **34 passed** (7 fixture-structure checks, 1 fixture-G check, 2 conftest fixture checks, 24 replay tests).
- `tests/` now contains the conftest, seven golden JSON fixtures, fixture checks, and replay tests. Metric tests do not exist yet.
- No compatibility issues with Python 3.14.7. Flask's deprecated `__version__` was used only in an ad-hoc check, not in project code.

---

## Exact Next Task

**Task ID:** P0-D1-04
**Title:** Engine — metrics

**Scope (from `docs/TASKS.md`):**
1. Implement `app/engine/metrics.py` with all formulas from `docs/METRICS.md` (Gross WPM, Net WPM, accuracy, final-text accuracy, dwell, IKI stats, consistency, pause stats, per-key IKI, error accounting).
2. Include the zero-mean guard for CV.
3. Write `tests/test_metrics.py` verifying the exact expected values from fixtures A–G.
4. Assert `Net ≤ Gross` on every fixture.

**Starting point:**
- `app.engine.replay.ReplayResult` already exposes `keystrokes`, `typed_final`, `backspace_deletions`, `backspace_presses`, `dwell_samples`, `timed_actions`, `end_reason`, and `active_duration_ms`.
- `analyze_session()` is a thin replay wrapper and should be extended to return the metric payload in P0-D1-04.
- Fixture G's canonical engine end reason is `time_up`; the fixture label `timer_expiry` is mapped in the replay test only.

---

## Outstanding Issues for the Next Agent

1. **Word list and passage texts** are missing (`AMB-001`, `AMB-002`); handle in P0-D1-07.
2. **`ended_at_ms`/`end_reason` handling** ("reject" vs "ignore") is ambiguous; decide and document before validator implementation.
3. **Non-metric application limits** (request size, event counts, allowed durations, word counts) are not formally enumerated; add only when the relevant validation/API tasks specify them.
4. **`docs/UI_DESIGN.md` §7** references `docs/METRICS.md` §6 for the Wilson heuristic; it should be §12. Correct during UI documentation cleanup.
5. **`README.md`** is absent; leave for P0-D3-05.
6. **`app/routes/__init__.py`** is not specified; decide when implementing routes.
7. **P0-D1-03 changes are uncommitted.** HEAD is `147ec1e` (P0-D1-02 committed externally); P0-D1-01 was committed in `9c02975`. The branch is 1 commit ahead of origin; do not commit or push without approval.

---

## Important Reminders for the Next Agent

1. Read `AGENTS.md` in full before writing code.
2. Do not commit or push unless the user approves.
3. Run `pytest` before any approved commit; do not commit a failing suite.
4. The engine (`app/engine/`) must have zero HTTP calls and zero DB calls.
5. Do not install packages not listed in `requirements.txt`.
6. Do not create files outside the approved structure in `docs/ARCHITECTURE.md` §8 without logging the decision in `docs/DECISIONS.md`.
7. Golden fixtures A–G in `docs/METRICS.md` §13 must pass before moving past P0-D1-04; fixture G must be pinned first (see outstanding issues).
