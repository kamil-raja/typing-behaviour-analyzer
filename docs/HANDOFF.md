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
| **Status** | Uncommitted P0-D1-02 changes: modified `docs/DECISIONS.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`, `docs/TASKS.md`; untracked `tests/` |
| **Last commit** | `c0d100c chore: remove accidental diff file` (previous: `9c02975 chore: add project foundation scaffold`) |
| **Tags** | None yet |
| **Commit/push** | **None performed by this agent in P0-D1-02.** P0-D1-01 was committed in `9c02975`; `c0d100c` removed an accidental `tatus` file. P0-D1-02 remains uncommitted. |

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
- Fixture G intentionally leaves `text`, `duration_limit_ms`, `end_reason`, and `active_duration_ms` unresolved (AMB-005).
- `pytest tests/ -v`: **10 passed** (7 fixture-structure checks, 1 fixture-G unresolved check, 2 conftest fixture checks).

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
- `pytest tests/ -v`: **10 passed** (7 fixture-structure checks, 1 fixture-G unresolved check, 2 conftest fixture checks).
- `tests/` now contains the conftest, seven golden JSON fixtures, fixture-integrity tests, and conftest fixture checks. No replay or metric tests exist yet.
- No compatibility issues with Python 3.14.7. Flask's deprecated `__version__` was used only in an ad-hoc check, not in project code.

---

## Exact Next Task

**Task ID:** P0-D1-03
**Title:** Engine — replay

**Scope (from `docs/TASKS.md`):**
1. Implement `app/engine/replay.py`: buffer state machine, `pending` map, and all event-handling rules per `docs/EVENT_SCHEMA.md` §4.
2. Handle accepted printable, repeat printable (discard), Backspace (non-repeat and repeat), `up` pairing, orphan up, missing up, the full-buffer rule, the timer boundary, and dropped-after-end.
3. Implement `app/engine/__init__.py` with an `analyze_session()` stub.
4. Write `tests/test_replay.py` against fixtures A–G for K, C, E, N, U, Ec, Eu, deletions, presses, `dropped_after_end`, `end_reason`, and `T`.
5. Assert invariants on every fixture: `E = U + Ec + Eu`, `K = C + E`, `N ≤ K`.

**Before starting:**
- Pin fixture G's text, duration limit, end reason, and `T` (AMB-005). Until then, replay tests can cover G's deletion, dwell, and interval behaviour but not its end state.
- Fixture F's event at t=2000 is a representative keyup after completion; keep the drop-after-end semantics.

---

## Outstanding Issues for the Next Agent

1. **Golden fixture G** lacks its exact text, `duration_limit_ms`, expected `end_reason`, and `T` (AMB-005); resolve before replay tests (P0-D1-03).
2. **Word list and passage texts** are missing (`AMB-001`, `AMB-002`); handle in P0-D1-07.
3. **Timer-boundary tests** are listed under P0-D1-06, but timing behaviour belongs to the replay engine; resolve before validators.
4. **`ended_at_ms`/`end_reason` handling** ("reject" vs "ignore") is ambiguous; decide and document before validator implementation.
5. **Non-metric application limits** (request size, event counts, allowed durations, word counts) are not formally enumerated; add only when the relevant validation/API tasks specify them.
6. **`docs/UI_DESIGN.md` §7** references `docs/METRICS.md` §6 for the Wilson heuristic; it should be §12. Correct during UI documentation cleanup.
7. **`README.md`** is absent; leave for P0-D3-05.
8. **`app/routes/__init__.py`** is not specified; decide when implementing routes.
9. **P0-D1-02 changes are uncommitted.** HEAD is `c0d100c`; P0-D1-01 was committed in `9c02975`. Do not commit or push without approval.

---

## Important Reminders for the Next Agent

1. Read `AGENTS.md` in full before writing code.
2. Do not commit or push unless the user approves.
3. Run `pytest` before any approved commit; do not commit a failing suite.
4. The engine (`app/engine/`) must have zero HTTP calls and zero DB calls.
5. Do not install packages not listed in `requirements.txt`.
6. Do not create files outside the approved structure in `docs/ARCHITECTURE.md` §8 without logging the decision in `docs/DECISIONS.md`.
7. Golden fixtures A–G in `docs/METRICS.md` §13 must pass before moving past P0-D1-04; fixture G must be pinned first (see outstanding issues).
