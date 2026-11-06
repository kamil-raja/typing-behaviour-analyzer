# AGENTS.md — Persistent Agent Instructions for TBA

> **Every coding agent (Antigravity, OpenCode, or any future tool) working on this repository must read and follow these instructions before making any change.**

---

## 1. Source of Truth

The **single source of truth** is `TBA_BLUEPRINT_v3_FINAL.md` at the repository root.
All `docs/` files are derived from it. When in doubt, the blueprint wins.

Do **not** modify `TBA_BLUEPRINT_v3_FINAL.md` under any circumstances.

---

## 2. Approved Technology Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.10+ |
| Web framework | Flask (no other Python web framework) |
| Database | SQLite via Python built-in `sqlite3` (no ORM, no SQLAlchemy) |
| Frontend | HTML5 + CSS3 + vanilla JavaScript ES modules |
| Charts | Chart.js **vendored locally** as `static/vendor/chart.umd.min.js` |
| Fonts | Lexend and JetBrains Mono, **self-hosted** (OFL licence) |
| Testing | pytest |

### Hard bans — do not introduce:

- React, Vue, Angular, Svelte, or any JS framework
- Node.js, npm, pnpm, yarn, Webpack, Vite, or any JS bundler
- MongoDB, PostgreSQL, Redis, or any database other than SQLite
- Django, FastAPI, or any web framework other than Flask
- Docker, Kubernetes, or containers
- Machine learning, scikit-learn, TensorFlow, or similar
- SQLAlchemy, Pony, or any ORM
- Any CDN-fetched resource (everything must work offline)
- Any dependency not listed in `requirements.txt`

---

## 3. Architecture Rules

1. **Engine is pure Python.** `app/engine/` must have zero HTTP calls and zero DB calls.
2. **No metric math in routes.** Routes parse, validate, call the engine and repository, then shape JSON.
3. **No metric math in JS.** The browser shows *provisional* live stats only; all stored and final statistics are computed server-side.
4. **No SQL in the engine.** `app/repository.py` owns every SQL statement.
5. **No ORM.** Use `sqlite3` directly with parameterised queries.
6. **No metric math in JS** — the browser's live WPM/accuracy display is labelled *provisional* and computed only for UX feedback.
7. **Client never sends** `ended_at_ms` or `end_reason`. The server derives these by replay.
8. **Client never sends the text.** The server rebuilds it from `text_ref`.

---

## 4. Coding Standards

### Python
- PEP 8. Type hints on all public functions.
- `re.fullmatch()` **only** for the ASCII 32–126 and code-field checks. Never `re.match()`, `str.isalnum()`, `str.isprintable()`, `\w`, or `str.isascii()` alone for these validation rules.
- Parameterised SQL only — never f-string or `.format()` queries.
- All DB writes for a session in a **single transaction**.
- `PRAGMA foreign_keys = ON` on every connection.
- Named constants in `app/config.py` for all thresholds (pause, dwell, IKI, heatmap min n, etc.).
- Module docstrings explaining layer responsibility.

### JavaScript
- ES modules (`type="module"`). No `var`. No `import()` calls to external URLs.
- Event listeners cleaned up when a test finishes or is cancelled.
- No metric calculations stored or treated as final — clearly label provisional stats.
- `fullmatch`-equivalent regex `^[\x20-\x7E]$` used identically to the Python rule.
- All DOM queries cached; no repeated `querySelector` in hot paths.

### HTML / CSS
- No hex literals in component CSS; use CSS tokens defined in `tokens.css`.
- All theme tokens set on `:root` (light) and `:root[data-theme="dark"]`.
- Inline blocking `<script>` in `<head>` reads `localStorage["tba-theme"]` before the stylesheet.
- Focus rings (`:focus-visible`) always visible. Motion respects `prefers-reduced-motion`.
- No `tabindex` values other than `0` and `-1`.

---

## 5. Event Capture Rules (critical — do not misimpliment)

1. `event.key` identifies Backspace actions; `event.code` pairs keydowns/keyups.
2. Repeat printable keydowns are **discarded**. Repeat Backspace downs are only valid when a pending original exists.
3. Repeat Backspace downs **never** read, write, or overwrite `pending`.
4. Tab is **never** `preventDefault`ed.
5. Ctrl/Meta/Alt combos are **not** `preventDefault`ed (except AltGr which is treated as normal typing).
6. Timestamp = `event.timeStamp`, falling back to `performance.now()` only if non-finite; log that fallback occurred.
7. Capture scope: keystrokes only when `event.target` is the passage viewport.

See `docs/EVENT_SCHEMA.md` and blueprint §5 for the full rules.

---

## 6. Testing Requirements

- **Run `pytest` from the repo root before every commit.** No commit if any test fails.
- Tests live in `tests/`. Fixtures in `tests/fixtures/`.
- Golden examples A–G (blueprint §14.1) must be implemented as fixtures and tested in `test_replay.py` and `test_metrics.py`.
- All invariants must be asserted on every fixture: `E = U + Ec + Eu`, `K = C + E`, `Net ≤ Gross`, `N ≤ K`.
- Regression test groups 1–11 (blueprint §14.2) must each have named tests with hand-computed expected values.
- **Never bypass a test** by changing the test fixture instead of fixing the code.
- Hygiene tests (`test_hygiene.py`) check:
  - User-facing strings do not claim statistical significance for the heatmap.
  - User-facing copy does not claim laboratory-grade or µs-precision timing.
  - The timing-honesty note is present.
  - No bigram/pause/recalculate routes exist in the API.

---

## 7. Task Flow Rules

1. Read `docs/TASKS.md` before starting any work.
2. Work only on the **first unchecked P0 task**. Never start P1 while any P0 is broken.
3. Mark a task complete (`[x]`) only when its acceptance criteria are met and `pytest` is green.
4. If P0 is entirely green and time permits, take P1 tasks in `TASKS.md` order.
5. P2 tasks are **not started** in the initial three-day build.

---

## 8. Blueprint Fidelity Rules

- Do **not** redesign the architecture.
- Do **not** reinterpret metric definitions. Copy formulas exactly from `docs/METRICS.md`.
- Do **not** introduce technology not in §2 above.
- Do **not** add API endpoints not listed in blueprint §10.
- Do **not** add database tables not in blueprint §9 (P2 tables are deferred).
- If a decision requires deviation, log it in `docs/DECISIONS.md` with date and reason **before** making the change.
- Genuine ambiguities → `docs/DECISIONS.md`, not a guess.

---

## 9. Git Rules

- Branch off `feature/project-foundation` for the initial build.
- Commit after **every green milestone** (not at end of day only).
- Commit message format: `type(scope): short description` (e.g., `feat(engine): implement replay and metrics`).
- Tag each day: `day1`, `day2`, `day3` and final release `v1.0`.
- Do **not** commit a failing `pytest` suite.
- Do **not** commit `instance/typing.db` (it is git-ignored).
- Do **not** commit vendor/font files if they were already committed on the current branch.

---

## 10. Handoff Rules

- Update `docs/HANDOFF.md` at the end of every work session.
- Record: current branch, files changed, tests run and results, exact next task.
- Update `docs/PROGRESS.md` with completed items.
- Tick the matching task in `docs/TASKS.md`.
- If you are stopping mid-task, describe the exact stopping point in `HANDOFF.md`.

---

## 11. Licence and Copyright

- Do **not** copy code from Monkeytype or Keybr.
- Keybr is AGPL-3.0. Any code derived from it would infect the whole project.
- Check Monkeytype's licence before reusing any fragment.
- Fonts must be OFL-licensed. Chart.js is MIT.
- All passages in `app/data/passages.json` must be original or verified public-domain ASCII text.

---

## 12. Things That Are Explicitly Out of Scope

The following are **P2 or never** — do not implement them:

- Bigram analysis
- Rhythm / pause charts
- Session comparison
- Recalculation endpoint
- Dedicated printable report page
- Pause/resume on focus loss
- Error-cascade guard
- Non-QWERTY layout support (beyond the P1 mismatch banner)
- Colour-blind palette (P2)
- Authentication or multi-user support
- Any cloud/remote API
