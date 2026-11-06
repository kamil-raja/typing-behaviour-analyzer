# PROGRESS.md — Project Status

> Updated: 2026-11-06
> Branch: `feature/project-foundation`

---

## Current Status

**Phase: Implementation in progress — P0-D1-01 scaffold complete.**

Documentation is complete and the minimum Flask application foundation now exists. No automated tests exist yet; test infrastructure is the next task (P0-D1-02).

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

### Application code
- [x] P0-D1-01 scaffold only; no engine, validators, routes, database, or frontend yet

---

## Remaining Work (P0, in order)

| Task | Status |
|---|---|
| P0-D1-01: Repository scaffold | ✅ Complete (2026-11-06) |
| P0-D1-02: Tests infrastructure | ⬜ Not started |
| P0-D1-03: Engine — replay | ⬜ Not started |
| P0-D1-04: Engine — metrics | ⬜ Not started |
| P0-D1-05: Engine — key stats / heatmap | ⬜ Not started |
| P0-D1-06: Validators | ⬜ Not started |
| P0-D1-07: Text resolution | ⬜ Not started |
| P0-D1-08: Frontend — themes / CSS | ⬜ Not started |
| P0-D1-09: Frontend — capture / typing engine | ⬜ Not started |
| P0-D1-10: First vertical slice | ⬜ Not started |
| P0-D2-01: DB schema and connection | ⬜ Not started |
| P0-D2-02: Repository and persistence | ⬜ Not started |
| P0-D2-03: Results page (full) | ⬜ Not started |
| P0-D2-04: History page | ⬜ Not started |
| P0-D2-05: Typing screen polish | ⬜ Not started |
| P0-D2-06: Progress endpoint and analytics charts | ⬜ Not started |
| P0-D2-07: sessions.csv export | ⬜ Not started |
| P0-D3-01: Key stats aggregation and heatmap API | ⬜ Not started |
| P0-D3-02: Heatmap UI | ⬜ Not started |
| P0-D3-03: Hygiene tests | ⬜ Not started |
| P0-D3-04: Manual test pass | ⬜ Not started |
| P0-D3-05: README and delivery | ⬜ Not started |

---

## Next Milestone

**Day 1 vertical slice:** by end of Day 1, a user should be able to type, submit, and see metrics — even without DB persistence. The engine must pass all golden fixtures (A–G).

Exact next task: **P0-D1-02** — test infrastructure and `tests/conftest.py`.

---

## Blockers / Ambiguities

See `docs/DECISIONS.md` for open ambiguities:
- **AMB-001:** Word list content not yet finalised (needs author approval)
- **AMB-002:** Passage texts not yet provided (needs author to write/approve them)
- **AMB-003:** Passage selector label format (minor, can be decided during implementation)
- **AMB-004:** Moving average window behaviour at < 5 sessions (assumed trailing window with expanding for early sessions)

### Known issues carried forward
- Golden fixture G lacks `duration_limit_ms` and expected `end_reason`/`T`; resolve before replay tests (P0-D1-03).
- Word list and passage texts are missing; handle in P0-D1-07.
- Timer-boundary tests are listed under P0-D1-06 but timing belongs to the replay engine; resolve before validators.
- Client-supplied `ended_at_ms`/`end_reason` handling ("reject" vs "ignore") remains ambiguous; decide before validator implementation.
- Application limits outside `docs/METRICS.md` §14 (request size, event counts, allowed durations, word counts) are not formally enumerated; add when the relevant validation/API tasks specify them.
- `docs/UI_DESIGN.md` §7 references `docs/METRICS.md` §6 for the Wilson heuristic; correct during UI documentation cleanup.
- P0-D1-02 requests an in-memory DB fixture before the database task; resolve when implementing the test infrastructure.
- `README.md` is not yet present; leave for P0-D3-05.
- `app/routes/__init__.py` is not specified; decide when implementing routes.
