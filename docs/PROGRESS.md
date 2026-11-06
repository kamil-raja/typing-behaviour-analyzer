# PROGRESS.md — Project Status

> Updated: 2026-11-06
> Branch: `feature/project-foundation`

---

## Current Status

**Phase: Implementation in progress — P0-D1-01 through P0-D1-04 complete.**

Documentation, the minimum Flask application foundation, the pytest infrastructure, the replay engine, and the metric layer now exist. All seven golden examples pass through replay, and every replayable fixture matches its hand-computed speed, accuracy, interval, pause, dwell and error-accounting values. Per-key `CHAR_TO_CODE` mapping and heatmap classification are the next task (P0-D1-05).

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

### Application code
- [x] P0-D1-01 scaffold, P0-D1-02 test infrastructure, P0-D1-03 replay, and P0-D1-04 metrics; no keys/heatmap, validators, routes, database, or frontend yet

---

## Remaining Work (P0, in order)

| Task | Status |
|---|---|
| P0-D1-01: Repository scaffold | ✅ Complete (2026-11-06) |
| P0-D1-02: Tests infrastructure | ✅ Complete (2026-11-06) |
| P0-D1-03: Engine — replay | ✅ Complete (2026-11-06) |
| P0-D1-04: Engine — metrics | ✅ Complete (2026-11-06) |
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

Exact next task: **P0-D1-05** — engine key stats and heatmap classification (`app/engine/keys.py`, `tests/test_keys.py`).

---

## Blockers / Ambiguities

See `docs/DECISIONS.md` for open ambiguities:
- **AMB-001:** Word list content not yet finalised (needs author approval)
- **AMB-002:** Passage texts not yet provided (needs author to write/approve them)
- **AMB-003:** Passage selector label format (minor, can be decided during implementation)
- **AMB-004:** Moving average window behaviour at < 5 sessions (assumed trailing window with expanding for early sessions)

### Known issues carried forward
- Per-key attribution: `metrics.py` returns observations/IKI keyed by expected character and dwell keyed by physical code. The `CHAR_TO_CODE` merge into `session_key_stats` is P0-D1-05 (ADR-022).
- The fixture-A IKI contradiction is closed under ADR-023; `golden_a.json` now expects null IKI statistics because `|V| = 3 < 5`.
- Word list and passage texts are missing; handle in P0-D1-07.
- Timer-boundary behaviour is now covered by replay tests; P0-D1-06 still lists a boundary test, so keep validator coverage focused on schema and sequence checks.
- Client-supplied `ended_at_ms`/`end_reason` handling ("reject" vs "ignore") remains ambiguous; decide before validator implementation.
- Application limits outside `docs/METRICS.md` §14 (request size, event counts, allowed durations, word counts) are not formally enumerated; add when the relevant validation/API tasks specify them.
- `docs/UI_DESIGN.md` §7 references `docs/METRICS.md` §6 for the Wilson heuristic; correct during UI documentation cleanup.
- `README.md` is not yet present; leave for P0-D3-05.
- `app/routes/__init__.py` is not specified; decide when implementing routes.
