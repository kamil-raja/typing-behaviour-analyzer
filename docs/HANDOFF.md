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
2. The outgoing agent commits all changes with an appropriate message.
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
| **Status** | Clean working tree (documentation committed) |
| **Last commit** | Documentation: AGENTS.md and all docs/ files |
| **Tags** | None yet |

### Files Changed This Session

| File | Description |
|---|---|
| `AGENTS.md` | Created — persistent agent instructions for all agents |
| `docs/PROJECT_BRIEF.md` | Created — project purpose, scope, priorities |
| `docs/ARCHITECTURE.md` | Created — full system architecture, data flows, folder structure |
| `docs/UI_DESIGN.md` | Created — all screens, design tokens, interaction rules |
| `docs/METRICS.md` | Created — all metric formulas, golden fixtures, named constants |
| `docs/EVENT_SCHEMA.md` | Created — event capture rules, payload schema, server processing |
| `docs/TASKS.md` | Created — all development tasks with acceptance criteria |
| `docs/DECISIONS.md` | Created — ADR-001 through ADR-017 + 4 open ambiguities |
| `docs/PROGRESS.md` | Created — current status and remaining work |
| `docs/HANDOFF.md` | Created — this file |

### Tests Run

No tests run — no application code exists yet. `pytest` cannot be run until P0-D1-01 (scaffold) is complete.

### Application Code Written

**None.** This session was documentation-only as instructed.

---

## Exact Next Task

**Task ID:** P0-D1-01
**Title:** Repository and project scaffold

**What to do:**
1. Create `run.py`:
   ```python
   from app import create_app
   app = create_app()
   if __name__ == "__main__":
       app.run(debug=True)
   ```
2. Create `requirements.txt`:
   ```
   Flask>=3.0
   pytest>=8.0
   ```
3. Create `app/__init__.py` with `create_app()` factory (empty Flask app, register blueprints).
4. Create `app/config.py` with **all** named constants from `docs/METRICS.md` §14.
5. Create `app/errors.py` with error code string constants and a `json_error(code, message, details=None, status=422)` helper function.
6. Create a virtual environment (`python -m venv venv`) and install dependencies (`pip install -r requirements.txt`).
7. Verify `python run.py` starts without error.
8. Run `pytest tests/` — it should collect 0 tests and exit 0 (no test files yet).

**Acceptance criteria:**
- `python run.py` starts Flask (even with no routes returning anything useful).
- `pytest tests/` exits 0.
- No other files modified.

**After completing P0-D1-01:**
Proceed immediately to **P0-D1-02** (tests infrastructure and conftest).

---

## Important Reminders for the Next Agent

1. Read `AGENTS.md` **in full** before writing any code.
2. Run `pytest` before every commit. Do not commit a failing suite.
3. The engine (`app/engine/`) must have **zero** HTTP calls and **zero** DB calls.
4. Do **not** install any package not in `requirements.txt` (Flask, pytest only to start).
5. Do **not** create any file not listed in `docs/ARCHITECTURE.md` §8 without logging the decision in `docs/DECISIONS.md`.
6. The word list and passage texts are listed as open ambiguities (AMB-001, AMB-002). Use placeholder content if needed, clearly marked as placeholder. The agent should flag this to the user before the Day 1 final commit.
7. The golden fixtures (A–G) in `docs/METRICS.md` §13 must be implemented and all must pass before moving past P0-D1-04.
