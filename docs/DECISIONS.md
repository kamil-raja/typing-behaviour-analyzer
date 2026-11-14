# DECISIONS.md — Architectural Decision Log

> Every architectural decision, technology choice, and approved constraint is recorded here with its date and reason.
> When a deviation from the blueprint is required, it must be logged here **before** the change is made.
> Genuine ambiguities are also recorded here rather than resolved by guessing.

---

## Format

Each entry follows this template:

```
### ADR-NNN: Title
**Date:** YYYY-MM-DD
**Status:** Approved | Superseded by ADR-NNN | Open
**Context:** Why this decision was needed.
**Decision:** What was decided.
**Consequences:** Trade-offs and implications.
```

---

## Seed decisions from Blueprint §0 (Revision Log)

The following decisions are pre-approved and locked in `TBA_BLUEPRINT_v3_FINAL.md`. They are reproduced here for agent reference.

---

### ADR-001: Gross WPM formula
**Date:** 2026-11-06
**Status:** Approved
**Context:** v1 used `N/5` per minute. The issue was that this did not reflect total effort — it excluded incorrect and later-deleted keystrokes.
**Decision:** `gross_wpm = (K / 5) / T_min` where `K` = all accepted printable keystrokes. Backspaces are not printable and are not counted.
**Consequences:** Gross WPM captures raw output including errors. The invariant `Net ≤ Gross` holds because `N ≤ K`. Numbers will differ from Monkeytype's word-level WPM and must be labelled accordingly.

---

### ADR-002: Server derives end time and end reason
**Date:** 2026-11-06
**Status:** Approved
**Context:** v1 had a contradiction where the client supplied `ended_at_ms` and `end_reason`, but these conflict with server-side authoritative replay.
**Decision:** The client submits only `mode`, `duration_limit_ms`, `text_ref`, and `events`. The server replays the event sequence and derives `end_reason` and `T`. These are stored results, not inputs.
**Consequences:** The server is authoritative for all stored metrics. The client runs the same completion rule to decide when to stop capturing, but the server result takes precedence. This is not tamper-proof (client timestamps are taken at face value); it is acceptable for a single-user local application.

---

### ADR-003: Repeat Backspace never touches `pending`
**Date:** 2026-11-06
**Status:** Approved
**Context:** v1 had a bug where repeat Backspace downs could overwrite the pending dwell start time, causing incorrect dwell measurements.
**Decision:** Backspace repeat downs are recorded as deletion actions **only**. They never read, write, or overwrite the `pending: code → t_down` map. Dwell is measured only from the original non-repeat keydown.
**Consequences:** One physical Backspace hold gives N+1 deletions but exactly one dwell sample, one press, and one timed action. Correctly models real typing behaviour.

---

### ADR-004: ASCII 32–126 enforced with `re.fullmatch` on both client and server
**Date:** 2026-11-06
**Status:** Approved
**Context:** `str.isalnum()`, `str.isprintable()`, `\w`, and `str.isascii()` accept non-ASCII characters. `re.match` with `$` accepts trailing newlines. These caused validation bypass bugs in v1.
**Decision:** Use `re.fullmatch(r"[\x20-\x7E]", key)` exclusively for the printable character check. Use `re.fullmatch(r"[A-Za-z0-9]{1,32}", code)` for key codes. Same regex on client (JS) and server (Python).
**Consequences:** Any non-ASCII, control character, or multi-code-unit character is unambiguously rejected. The validation is uniform across the stack.

---

### ADR-005: Heatmap classification is a conservative heuristic, not a statistical test
**Date:** 2026-11-06
**Status:** Approved
**Context:** An earlier draft implied statistical significance. The heatmap uses Wilson confidence intervals compared against a pooled baseline, but it is not a valid hypothesis test for several reasons: the baseline includes the key itself, ~30 keys are compared with no multiple-comparison correction, keystrokes are not independent, and the threshold rules are ad hoc.
**Decision:** The heatmap is described as "a conservative heuristic relative to the user's own typing history." The words "significant" and "statistically" must not appear in any **user-facing UI string** — rendered templates and shipped JS string literals (enforced by `test_hygiene.py`). Technical documentation (`METRICS.md`) is explicitly **excluded** from this check; `METRICS.md` must state the heuristic is not a significance test for correctness. The API returns `"method": "wilson_vs_pooled_baseline_heuristic"`. (Blueprint §14.2 regression group 5.)
**Consequences:** The heuristic is still useful for identifying relatively error-prone keys. Users are not misled about its statistical validity. The hygiene test scans UI only — not docs.

---

### ADR-006: Passage mode ends only on exact buffer match
**Date:** 2026-11-06
**Status:** Approved
**Context:** v1 was ambiguous about whether a wrong final character ends a passage test.
**Decision:** A passage test ends **only when the buffer equals the text exactly** (same length and every character correct). A wrong final character does not end the test. The UI shows "Fix the highlighted characters to finish." Backspace remains available. A passage test always finishes with `U = 0`.
**Consequences:** Passage mode has no `uncorrected_errors` in the final buffer. This is consistent and predictable.

---

### ADR-007: Timing honesty — no precision claims
**Date:** 2026-11-06
**Status:** Approved
**Context:** An earlier version claimed specific timing resolution. Browser event timestamps include hardware, driver, OS, and scheduling jitter and are not lab-grade.
**Decision:** The app does not claim any specific timing resolution. Measurements are "suitable only for relative comparison on the same machine and browser." This statement appears in the README and in an "About the measurements" note on the results page.
**Consequences:** The app is honest about its limitations. The CSS `clamp()` function is a layout utility and is not affected by this rule.

---

### ADR-008: IKI valid intervals exclude zero and pauses (single definition)
**Date:** 2026-11-06
**Status:** Approved
**Context:** v1 was ambiguous about how zero intervals and pauses should be handled across different statistics. Having multiple definitions caused inconsistencies.
**Decision:** A single interval list `V` is defined: `V = { I : 0 < I < 1000 ms }`. Zero intervals are excluded and counted in `zero_interval_count`. Intervals ≥ 1000 ms are pauses and also excluded from `V`. All interval statistics (mean, median, SD, CV, histogram, consistency, per-key IKI) use `V`.
**Consequences:** Consistent statistics across results, analytics, and heatmap. Pauses are reported separately. Zero intervals are reported as a data-quality metric.

---

### ADR-009: Corrected errors split into Ec and Eu
**Date:** 2026-11-06
**Status:** Approved
**Context:** v1 defined corrected errors as `E − U`, which is imprecise. An error can be deleted without the position being subsequently correctly typed.
**Decision:** Three distinct states: `Ec` (deleted AND position finally correct), `Eu` (deleted AND position empty or still wrong), `U` (still in final buffer). Invariant: `E = U + Ec + Eu`.
**Consequences:** More accurate error accounting. `Eu` is most relevant in time mode (timer expires after a deletion). `Eu` is shown in the UI only when non-zero.

---

### ADR-010: Tab is never intercepted; focus loss cancels test
**Date:** 2026-11-06
**Status:** Approved
**Context:** Blocking Tab creates a keyboard trap, which is an accessibility violation. Earlier drafts were contradictory about this.
**Decision:** Tab and Shift+Tab are **never** `preventDefault`-ed in any state. Focus leaving the passage viewport while running cancels the test. The UI shows "Test cancelled. The window lost focus."
**Consequences:** Native keyboard navigation is always available. Users can tab away (which cancels the test). This is acceptable and expected behaviour. P2 may add pause/resume.

---

### ADR-011: P2 features deferred — bigrams, rhythm, compare, recalculation
**Date:** 2026-11-06
**Status:** Approved
**Context:** v1 scope was too broad for a three-day build.
**Decision:** Bigrams, rhythm charts, pause analysis charts, session comparison, recalculation endpoint, and the dedicated report page are P2 and not started in the initial build. Raw events are retained to make these possible later without data loss.
**Consequences:** The initial build is scoped to P0 (must work) and P1 (important). P2 is explicitly out of scope.

---

### ADR-012: Timer expiry wins at exact boundary
**Date:** 2026-11-06
**Status:** Approved
**Context:** v1 was ambiguous about events timestamped exactly at the duration limit.
**Decision:** Timer expiry wins at `t >= duration_limit_ms`. A keystroke at `t = duration_limit_ms` is NOT accepted. Completion is only accepted when its keystroke `t` is strictly less than `duration_limit_ms`.
**Consequences:** Deterministic, unambiguous behaviour at the boundary. The active duration `T = duration_limit_ms` exactly when the timer expires.

---

### ADR-013: Timing trust boundary — client timestamps are taken at face value
**Date:** 2026-11-06
**Status:** Approved
**Context:** The server replays client-submitted event timestamps. It cannot independently verify when physical keystrokes occurred.
**Decision:** The server validates event structure and ordering but treats client timestamps as the data to be analysed, not verified ground truth. This is documented as a limitation. The app is not a secure assessment or anti-cheating system.
**Consequences:** A motivated user could submit fabricated timestamps. This is acceptable for a single-user local application.

---

### ADR-014: `final_accuracy_pct = null` when `N = 0`
**Date:** 2026-11-06
**Status:** Approved
**Context:** When the final buffer is empty (all characters deleted, timer expired in time mode), dividing by N produces a division-by-zero.
**Decision:** `final_accuracy_pct = null` when `N = 0`. The empty final buffer has no characters whose correctness can be measured.
**Consequences:** Null is a valid, expected value for this metric. The UI renders it as `—` or similar, not as 0%.

---

### ADR-015: `analysis_version = 1` for the initial metric definition set
**Date:** 2026-11-06
**Status:** Approved
**Context:** Metric definitions may change over time. Without a version marker, it is impossible to know which formula was used to compute stored metrics.
**Decision:** `analysis_version` is stored per session. It is `1` for all sessions created by the initial implementation. It is incremented whenever metric definitions or derivation semantics change in a later implementation. Recalculation is a P2 feature.
**Consequences:** Future implementations can identify which formula version was used for each stored session.

---

### ADR-016: Backspace identified by `event.key`, keyup paired by `event.code`
**Date:** 2026-11-06
**Status:** Approved
**Context:** `event.code` for Backspace is typically `"Backspace"` on QWERTY, but the spec says to identify the action by `event.key === "Backspace"` to avoid assuming the physical key's code. Keyup events do not reliably carry `event.key` (it can change with Shift) so pairing uses `event.code`.
**Decision:** Identify Backspace by `event.key === "Backspace"`. Store the pending keydown under the event's actual `code`. Pair keyup with keydown using `event.code`.
**Consequences:** Correct handling of non-standard physical keyboard layouts where Backspace might be remapped, and correct dwell measurement.

---

### ADR-017: Timestamp fallback must be logged
**Date:** 2026-11-06
**Status:** Approved
**Context:** `event.timeStamp` should always be finite in Chrome/Edge, but a fallback to `performance.now()` is needed defensively. Silently mixing clocks without recording it would corrupt timing data without any trace.
**Decision:** If the fallback is used, increment a diagnostic counter and log the occurrence. The session payload includes the ignored/fallback counts. The server receives this information.
**Consequences:** Any clock-mixing incident is visible in the session data and logs. The fallback is a defensive path, not a silent data quality issue.

---

### ADR-018: P0-D1-02 provides an in-memory SQLite fixture only
**Date:** 2026-11-06
**Status:** Approved
**Context:** P0-D1-02 requires an in-memory DB fixture, but the database schema and application connection factory are P0-D2-01. Creating `app/db.py` or `app/schema.sql` now would prematurely implement a later task.
**Decision:** `tests/conftest.py` provides a `db_conn` fixture backed by `sqlite3.connect(":memory:")` with `PRAGMA foreign_keys = ON`. It creates no tables. The application connection factory, schema, and `init_db()` remain in P0-D2-01.
**Consequences:** Repository tests can receive a connection later, but schema-dependent tests must wait for P0-D2-01. No production database code is introduced early.

---

### ADR-019: Golden fixture G values (AMB-005 resolved)
**Date:** 2026-11-06
**Status:** Approved
**Context:** Blueprint §14.1 leaves fixture G's exact text, duration limit, end reason, and active duration unspecified.
**Decision:** The author approved these values:
- text: `the quick brown fox jumps over the lazy dog while another quiet fox watches from the green hill`
- `duration_limit_ms`: `2000`
- fixture-level `end_reason` label: `timer_expiry`
- `active_duration_ms`: `2000`

The fixture-level label `timer_expiry` describes timer expiry. The engine and stored schema use the canonical blueprint value `time_up` (blueprint §4.3 and §9). `tests/test_replay.py` maps the fixture label to `time_up`.
**Consequences:** Fixture G now asserts the full end state, error accounting (`K=3 C=0 E=3 N=0 U=0 Ec=0 Eu=3`), Backspace deletion/dwell behaviour, and interval list. AMB-005 is closed.

---

### ADR-020: Replay returns a structured result; outcome checks stay with the caller
**Date:** 2026-11-06
**Status:** Approved
**Context:** Replay derives completion or timer expiry, but the documented server processing order applies `INCOMPLETE_SESSION` as an outcome check after replay.
**Decision:** `app.engine.replay.replay_events()` returns a `ReplayResult` containing the buffer, accepted keystrokes, timed actions, dwell samples, end reason, active duration, and data-quality counters. A passage run that never completes returns `end_reason=None`; the caller raises `INCOMPLETE_SESSION`. Timer expiry uses the canonical `time_up` value. `INVALID_EVENT_SEQUENCE` violations raise `InvalidEventSequence`.
**Consequences:** The replay layer stays pure and testable. Route/outcome handling and metric computation can consume the same structured result without re-parsing events.

---

### ADR-021: Metric edge-case guards
**Date:** 2026-11-06
**Status:** Approved
**Context:** `docs/METRICS.md` defines the formulas but leaves four boundary cases to the database's "nullable = not computable" convention: zero active duration, zero keystrokes, no pauses, and display precision. These cases cannot occur in a saved session (`K ≥ 10`, `T ≥ 3000 ms`), but the engine can be called directly by tests and by the future API layer.
**Decision:** The author approved these guards:
- `T <= 0` → `gross_wpm` and `net_wpm` are `null` (never a division by zero).
- `K = 0` → `accuracy_pct` and `error_rate` are `null`.
- No pause-class intervals → `pause_count = 0`, `total_pause_ms = 0.0`, `longest_pause_ms = null`.
- Percentages are stored unrounded; only `consistency_score` is rounded to one decimal place, as §8.6 explicitly requires.
**Consequences:** Null consistently means "not computable". Fixtures A–G are unaffected because all have `T > 0` and `K > 0`. Accuracy tests compare display-rounded values (for example `66.666…` → `66.7`).

---

### ADR-022: Metric layer splits per-key attribution by source
**Date:** 2026-11-06
**Status:** Approved
**Context:** `docs/METRICS.md` §10 says per-key IKI is added to `key_stats[expected_char]`, while §12.1 says observations and errors are attributed to the expected character's key via `CHAR_TO_CODE` and dwell is attributed to the physically pressed `event.code`. The `CHAR_TO_CODE` table is P0-D1-05, so `metrics.py` cannot yet produce the final `key_code`-keyed `session_key_stats` rows.
**Decision:** `app.engine.metrics.compute_key_stats()` returns a `KeyStats` with two additive maps:
- `observations_by_char` — `attempts`, `errors`, `iki_count`, `iki_sum_ms`, keyed by expected character (the exact `key_stats[expected_char]` form in §10).
- `dwell_by_code` — `dwell_count`, `dwell_sum_ms`, keyed by physical `event.code`, including Backspace and excluding invalid dwells.

P0-D1-05 will map expected characters through `CHAR_TO_CODE` and merge the two maps into `session_key_stats` rows.
**Consequences:** No metric is computed against a guessed key mapping, and the per-key IKI definition remains exactly the §10 subset of `V`. The merge is explicitly deferred to the task that owns `CHAR_TO_CODE`.

---

### ADR-023: Fixture A IKI expectations follow the §8.5 sample-size rule
**Date:** 2026-11-06
**Status:** Approved
**Context:** `docs/METRICS.md` §8.5 says all IKI statistics are `null` when `|V| < 5`, and regression group 8 requires `|V| < 5 → null stats`. Fixture A's §13 row (and blueprint §14.1) lists `V = [800, 800, 800]` with `mean = 800, SD = 0`, which contradicts the sample-size rule.
**Decision:** The author ruled that §8.5 takes precedence. `tests/fixtures/golden_a.json` now expects `avg_iki_ms: null` and `iki_sd_ms: null`; the three valid intervals remain listed as `valid_intervals_ms`. The fixture's gross, net, accuracy, interval and pause values are unchanged.
**Consequences:** The fixture no longer asserts an unreachable mean/SD for three intervals. A synthetic test with five valid intervals verifies that mean, median, sample SD and CV are computed when the minimum is met.

### ADR-024: Key statistics merge shape and classification gate
**Date:** 2026-11-06
**Status:** Approved
**Context:** P0-D1-05 must merge the two attribution maps produced by `metrics.compute_key_stats()` (ADR-022) into the `session_key_stats` columns from blueprint §9. The documented `classify_key(e, b, lo, hi, x)` signature has no sample-size argument, yet the heatmap has an `n < HEATMAP_MIN_N` "insufficient" state. The stored row shape and the merge return type are also not named in the task.
**Decision:**
- `app/engine/keys.py` defines `SessionKeyStat`, a frozen dataclass whose fields are exactly the additive `session_key_stats` columns: `key_code`, `attempts`, `errors`, `dwell_count`, `dwell_sum_ms`, `iki_count`, `iki_sum_ms`.
- `merge_session_key_stats(key_stats)` returns a `key_code`-keyed dict sorted by key code. The keys are the union of the codes reached through `CHAR_TO_CODE` from expected characters and the physically pressed dwell codes (including `Backspace`); rows with no data for one source keep zeros for that source. An expected character outside the static table raises `ValueError` rather than being silently dropped.
- `classify_key(e, b, lo, hi, x)` keeps the documented five-argument signature. `lo` and `hi` may be `None`, which represents the `n < HEATMAP_MIN_N` grey state and returns `"insufficient"`. `classify_observation(attempts, errors, baseline)` applies the `n >= HEATMAP_MIN_N` gate, computes `e`, calls `wilson_ci`, and then calls `classify_key`; `classify_key_stat` is the same operation for a stored row.
- `pooled_baseline_error_rate(total_errors, total_attempts)` returns `None` when there are no observations (nothing to pool) and otherwise applies the documented 1 % floor.
- The `e - b >= 0.02` margin comparison allows a `1e-12` floating-point tolerance so an exact decimal boundary is not lost to binary representation. No threshold value changes.
- `SessionAnalysis` gains `session_key_stats` (the merged rows). The existing `key_stats` field remains the raw two-map intermediate for auditability.
**Consequences:** The repository can insert one row per `session_key_stats` item. Classification can be reused unchanged by the P0-D3-01 aggregation endpoint. The raw attribution maps remain available, so no information is lost in the merge.

### ADR-025: Client-supplied `ended_at_ms` and `end_reason` are rejected
**Date:** 2026-11-06
**Status:** Approved
**Context:** Blueprint §4.3 and §6.2 state that the client sends no `ended_at_ms` and no `end_reason`; they are server-derived. Blueprint §14.2 regression group 2 says such fields are "not accepted or are ignored", leaving two possible validator behaviours.
**Decision:** The validator rejects a payload that contains either field, even when the value is `null`. Each occurrence produces a `VALIDATION_ERROR` detail whose field is the offending key and whose problem states that the field is server-derived and must not be supplied.
**Consequences:** The API is strict and cannot be made to trust client-supplied end state. A conforming client never sends these fields. This choice follows the explicit regression instruction in `docs/TASKS.md` P0-D1-06.

---

### ADR-026: Validator contract, timer-boundary handling and request limits
**Date:** 2026-11-06
**Status:** Approved
**Context:** No validator API was specified. `docs/TASKS.md` P0-D1-06 lists events at `t == duration_limit_ms` under "Reject", but blueprint §6.3 and `docs/EVENT_SCHEMA.md` §7 place that rule in replay: events with `t >= duration_limit_ms` are excluded and the session ends with `time_up`. Rejecting the whole payload during schema validation would turn an ordinary timer expiry into a 422 error. The "2 MB" body limit and the handling of unknown fields, `started_at` format and unknown `text_ref` values were also unspecified.
**Decision:**
- The public entry point is `validate_session_payload(payload, *, body_size_bytes=None) -> ValidatedSessionPayload`. It is pure Python and independent of Flask routes. It raises `ValidationError` (`VALIDATION_ERROR`, 422) with aggregated `{field, problem}` details, or `PayloadTooLargeError` (`PAYLOAD_TOO_LARGE`, 413).
- The 2 MB body limit is interpreted as 2 MiB (`2 * 1024 * 1024` bytes) and is checked before field validation when a body size is supplied.
- Events at `t >= duration_limit_ms` are structurally valid. The validator only enforces finite, non-negative, non-decreasing `t`. Replay owns the timer boundary: it excludes those events and sets `time_up`, which is the documented "not accepted" meaning.
- `text_ref` is checked structurally (type enum, required fields, word-count bounds). Existence is resolved later and produces `TEXT_NOT_FOUND`, not `VALIDATION_ERROR`.
- Top-level unknown fields are allowed for forward compatibility. The two forbidden server-derived fields in ADR-025 are the exception.
- `started_at` must be a non-empty string but its ISO format is not enforced because it is informational and no validation rule is specified. `client.user_agent` and `client.platform` must be strings; `client.layout_hint` must be one of the documented enum values. `ignored` must contain the five documented non-negative integer counters.
- Time limits are restricted to `{15000, 30000, 60000}` ms; passage mode requires `null`. Word-mode `count` is restricted to `10..400` inclusive. Event counts are `2..10000` inclusive.
- All validation problems are accumulated into one error response where possible; the first structural failure does not hide later field details.
**Consequences:** A normal timer expiry remains a replay outcome, not a validation failure. Routes only need to translate `ValidationError.code`, `.message`, `.details` and `.status` through `app.errors.json_error()`. Future text resolution still owns unknown-reference errors.

---

### ADR-027: Text content, frozen ordering and the deterministic generator
**Date:** 2026-11-06
**Status:** Approved
**Context:** `AMB-001` and `AMB-002` required author-approved content, and `docs/EVENT_SCHEMA.md` §9 requires a reproducible word generator and a startup ASCII check. No text or word list existed in the repository. The author approved authoring original project content for this build (in-session, 2026-11-06) rather than supplying external text.
**Decision:**
- `app/data/passages.json` is a JSON array of `{"id", "text"}` objects, ordered `p_001` … `p_012`. All twelve texts are original prose written for this project, not copied from Monkeytype, Keybr or any public-domain source. Each is 150–400 characters, contains only ASCII 32–126, single spaces, and no newline or tab. Per `AMB-003`, the UI label is the first ~40 characters; no title field is added.
- `app/data/words_en.json` is a JSON array of exactly 200 unique, lowercase `a-z` words in a frozen order. The order is frequency-inspired but is not a cited frequency list; its only contract is that it never changes without a new ADR.
- Word generation is frozen as: `rng = random.Random(seed)`; repeatedly `rng.shuffle(words)` on a working copy of the source list and append the whole shuffled list until at least `count` words exist; return the first `count` joined by one space. For `count <= 200` this is one shuffle and a slice. The repeat-cycling rule exists because the documented `count` range is 10–400 while the source list has 200 words. It preserves the blueprint's `random.Random(seed).shuffle()` algorithm and source-list ordering.
- Duration sizing lives in `app/config.py` as `WORDS_FOR_DURATION_MS = {15000: 120, 30000: 200, 60000: 350}` and is exposed through `texts.words_for_duration()`.
- `texts.resolve_text(text_ref)` is the only entry point routes need. Unknown passage ids raise `TextNotFoundError` (`TEXT_NOT_FOUND`, 404); an unsupported ref type is a `ValueError` because schema validation already owns the enum.
- `texts.validate_text_sources()` is called from `create_app()` and raises `TextSourceError` on unreadable/invalid JSON, malformed structure, duplicate ids, non-ASCII characters (including control characters), empty strings, or words that are not lowercase `a-z`.
**Consequences:** Seed-to-text mappings are reproducible only while both files keep their exact ordering; any content change requires a new ADR and must not reorder existing entries. Sessions store a passage snapshot, so historical results remain interpretable, but future text for an existing seed will change if the word list changes. `AMB-001` and `AMB-002` are resolved by this decision; the authored texts remain subject to the author's editorial review before release.

---

### ADR-028: Frontend asset provenance and theme foundation
**Date:** 2026-11-06
**Status:** Approved
**Context:** P0-D1-08 requires self-hosted fonts and a locally vendored Chart.js build with no runtime CDN. The blueprint fixes the technology and the visual tokens but does not name exact asset versions, font subsets or file names. The inline theme bootstrap and the later toggle also need a clear division of responsibility.
**Decision:**
- Chart.js `4.4.7` is vendored as `app/static/vendor/chart.umd.min.js` (the minified UMD build) with its MIT licence at `app/static/vendor/CHARTJS-LICENSE.md`. It is not loaded by `base.html`; chart-using pages load it explicitly when those pages are built.
- Lexend (`v26`) and JetBrains Mono (`v24`) are vendored as variable WOFF2 files in `app/static/fonts/`, with the two SIL OFL licence texts stored beside them. Only the latin subset is vendored because all application content is ASCII 32–126; out-of-subset glyphs use the documented fallback stacks.
- The inline blocking script in `base.html` owns only the first paint: it reads `localStorage["tba-theme"]` in a try/catch, falls back to `prefers-color-scheme`, sets `data-theme`, and adds `.no-transition` until the window load event.
- `app/static/js/theme.js` owns later toggles: it persists the choice in `tba-theme`, keeps the toggle's accessible label in sync, and dispatches `tba:themechange` with the active theme. It performs no metric or application work.
- `base.html` uses literal path links for the four future pages because their endpoints do not exist until P0-D1-10; using `url_for` for missing endpoints would break template rendering. The links intentionally resolve to 404 until those routes land.
- `tokens.css` is the only stylesheet permitted to contain raw colour values. Print media re-declares the light palette on both `:root` and `:root[data-theme="dark"]` so a dark session prints light.
**Consequences:** Frontend assets work fully offline and their versions are reproducible. Upgrading Chart.js or either font requires replacing the file, updating the licence notice and recording a new ADR. The nav is structurally complete but not navigable until the page routes arrive.

---

### ADR-029: Text API response shapes and the passage selector label (resolves AMB-003)
**Date:** 2026-11-06
**Status:** Approved
**Context:** Blueprint §10 fixes the three P0 text endpoints but only says they return a `text_ref` plus `text`. `AMB-003` leaves the passage selector's option text unspecified. The test page needs a display label before it can populate the selector, and the contract must be frozen before the page is wired to it.
**Decision:**
- `GET /api/texts/passages` returns `{"passages": [{"text_ref": {"type": "passage", "id": ...}, "label": ...}]}` in frozen `passages.json` order. It does **not** include each passage's full text, so the list stays small.
- `label` is the first 40 characters of the passage with trailing whitespace removed, followed by `"..."` when the passage is longer than 40 characters. No title field is added to `passages.json`.
- `GET /api/texts/passages/<id>` returns `{"text_ref": {"type": "passage", "id": ...}, "text": ...}`. An unknown id returns `404 TEXT_NOT_FOUND` in the documented error shape.
- `GET /api/texts/words?count=N` returns `{"text_ref": {"type": "words", "seed": <server-picked int>, "count": N}, "text": ...}`. The server picks `seed` with `secrets.randbelow(2**31)`; the client never chooses it.
- `count` is required and must be an integer from 10 to 400 inclusive. Missing, non-integer, or out-of-range values return `422 VALIDATION_ERROR` with a detail whose `field` is `"count"`.
- The page never embeds passage text in the HTML. It fetches the chosen text from these endpoints, preserving the architecture rule that pages call `/api/...`.
**Consequences:** The passage list is stable and cacheable; changing the label length or response shape is an API change. `AMB-003` is resolved by this decision. The client still sends only `text_ref` when session submission arrives, never the text body.

---

### ADR-030: Pulling `GET /` and the text endpoints forward from P0-D1-10
**Date:** 2026-11-06
**Status:** Approved
**Context:** P0-D1-09 builds the typing screen, but `docs/TASKS.md` assigned `GET /` to P0-D1-10 and did not assign the three P0 text endpoints to any task. Without a page route and text API, the completed screen would not be reachable or able to load a passage. The user asked for the real interface at `http://127.0.0.1:5000/` as early as possible.
**Decision:**
- Pull forward only: `app/routes/__init__.py`, `app/routes/pages.py` with `GET /`, `app/routes/api.py` with the three text GET endpoints, and blueprint registration in `create_app()`.
- Keep the rest of P0-D1-10 out of scope: no `POST /api/sessions`, no results page, no persistence, no history or analytics.
- P0-D1-10 now covers session submission and the minimal results view only; the page route and text endpoints are already complete.
- Tests for the pulled-forward surface live in `tests/test_api.py`; `tests/test_infrastructure.py` expects `GET /` to return 200 and includes the new static assets.
**Consequences:** The typing screen is reachable and usable now, but a finished attempt only shows client-side provisional numbers. The server remains the sole owner of final metrics, as required by AGENTS.md §3.

### ADR-031: Client event accumulation and one-shot session submission
**Date:** 2026-11-06
**Status:** Approved
**Context:** The server's `POST /api/sessions` contract requires the complete accepted event sequence (downs and ups in order) and rejects client-supplied `ended_at_ms`/`end_reason`. The typing engine previously kept only counters and the final buffer. Passage mode finishes from inside the completing keydown handler, before the capture layer has recorded that event.
**Decision:**
- `app/static/js/capture.js` owns accepted-event accumulation. It assigns a contiguous `seq` at record time and records only events the engine accepts. `getEvents()` returns shallow copies so callers cannot mutate the attempt.
- `app/static/js/test-page.js` builds the documented payload from capture state: `schema_version`, `mode`, `duration_limit_ms`, `text_ref`, `started_at`, `client` (with `layout_hint: "unknown"`), `ignored`, and `events`. It never sends the text body, `ended_at_ms` or `end_reason`.
- Submission is one-shot: `submitted`/`submitting` guards prevent duplicate posts, and a failed post resets only `submitting` so the user can start a new attempt.
- `onFinish` defers `submitAttempt()` with `queueMicrotask`. This lets capture record the completing keydown before the payload is serialised. Without the deferral, a completed passage is submitted one character short and the server returns `INCOMPLETE_SESSION`.
- The final keyup remains intentionally uncaptured (`docs/EVENT_SCHEMA.md` §5); replay reports `open_at_end`.
**Consequences:** Final metrics are always derived from the authoritative replay of the captured events. A regression test asserts the microtask deferral and the absence of a synchronous `submitAttempt()` call.

### ADR-032: In-memory session store, POST response shape and results routing
**Date:** 2026-11-06
**Status:** Approved
**Context:** P0-D1-10 needs a session id and a results page before database persistence exists (P0-D2-01/02). The blueprint fixes `201 { session_id, metrics, warnings, links }` but not the pre-persistence storage mechanism.
**Decision:**
- `app/session_store.py` provides a thread-safe, process-local `InMemorySessionStore`, attached as `app.extensions["tba_session_store"]` in `create_app()`. Each application instance owns an isolated store, which keeps tests independent.
- Session ids are `uuid4().hex`; `created_at` is UTC ISO-8601 with a `Z` suffix. Records are lost when the process restarts; P0-D2-02 replaces this store with the SQLite repository.
- `metrics` is `asdict(SessionMetrics)` plus `mode`, `duration_limit_ms`, `active_duration_ms`, `end_reason`, and `analysis_version` (`ANALYSIS_VERSION = 1`).
- `warnings` contains only non-zero tolerated conditions: `orphan_up`, `missing_up`, `open_at_end`, `invalid_dwell`, `dropped_after_end`. `invalid_dwell_count` was added to `SessionMetrics`, and `DataQualityWarning` plus `warnings` were added to `SessionAnalysis`.
- `GET /results/<session_id>` renders the stored analysis server-side. Unknown ids return 404. There is no `GET /api/sessions/<id>` yet; that endpoint belongs to P0-D2-03.
- Routes and templates contain no metric math. The API only serialises engine output.
**Consequences:** The full type → submit → results flow works without a database. The results page is temporary but already reads the same server-computed values the persisted version will expose.

### ADR-033: SQLite schema, connection management and database location
**Date:** 2026-11-08
**Status:** Approved
**Context:** P0-D2-01 requires `app/schema.sql` and `app/db.py` for the four tables in blueprint §9. The blueprint fixes the column names and the documented CHECKs (`type ∈ {down, up}`, `repeat ∈ {0,1}`) but does not name SQLite types, index names, the `user_version` value, or how tests should isolate the database from `instance/typing.db`. The engine also carries `error_rate` and `invalid_dwell_count`, which are not `session_metrics` columns in the blueprint.
**Decision:**
- Column storage types: identifiers and JSON snapshots are `TEXT`; counters, sequence numbers and limits are `INTEGER`; timings and computed ratios are `REAL`. `sessions.id` is the repository-generated 32-character uuid hex string.
- CHECK constraints encode only documented invariants: `mode ∈ {time, passage}`, the matching duration rule (`time` requires 15000/30000/60000 ms; `passage` requires NULL), `end_reason ∈ {completed, time_up}`, `layout_hint ∈ {qwerty, non-qwerty, unknown}`, `type ∈ {down, up}`, `repeat ∈ {0,1}`, non-negative `seq`/`t_ms`, and `key IS NULL` exactly for `up` events.
- Indexes are `idx_sessions_created_at` on `sessions(created_at)` and `idx_session_key_stats_key_code` on `session_key_stats(key_code)`; the `keystroke_events(session_id, seq)` UNIQUE constraint supplies its lookup index.
- `PRAGMA user_version` is `1` (`SCHEMA_VERSION` in `app/db.py`). `CREATE TABLE IF NOT EXISTS` makes initialisation idempotent. A non-zero version other than 1 aborts with a clear error and the documented development remedy (delete `instance/typing.db`); no migration path is added in the initial build.
- `DATABASE` defaults to `<app.instance_path>/typing.db` (the documented `instance/typing.db`). `create_app()` gains an optional `test_config` mapping applied before initialisation, so the test application uses `tmp_path/typing.db` instead of the developer database.
- `connect()` sets `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`. `get_db()` stores one connection in `g` per request; `close_db()` is registered as the application-context teardown.
- `session_metrics` keeps exactly the blueprint columns. `error_rate` is derivable from `accuracy_pct`, and `invalid_dwell_count` plus the warning counters belong in `data_quality_json`; adding extra columns would break blueprint fidelity. P0-D2-02 owns how those JSON payloads are populated.
**Consequences:** The schema is a direct transcription of blueprint §9, so P0-D2-02 can insert the engine output without schema changes except for serialising `data_quality_json`. Tests never touch the developer database, and every connection enforces foreign keys.

### ADR-034: Session repository, persistence contract and read-back reconstruction
**Date:** 2026-11-09
**Status:** Approved
**Context:** P0-D2-02 replaces the in-memory store with `app/repository.py`. The blueprint §9 columns do not include the validator's `started_at`/`ignored` diagnostics or the engine's `error_rate`/`invalid_dwell_count`, replay drops stored events only implicitly, and the results page and 201 response currently read `SessionMetrics`/`ReplayResult` objects from the store. These gaps need an explicit persistence contract.
**Decision:**
- `SessionRepository(database)` lives in `app/repository.py`, opens one connection per method through `app.db.connect()`, and is attached as `app.extensions["tba_session_store"]`. The extension-key constant keeps its historical name (`STORE_EXTENSION_KEY`) and value for continuity with the routes and tests; the class surface mirrors the store: `create(payload, analysis)` → `SessionRecord`, `get(id)`, `count()`, plus `list_sessions(limit, offset) → (items, total)` and `get_key_stats(id)`.
- `create()` writes one row per table in a single transaction: sessions, session_metrics, then `executemany` over the retained events and the `SessionKeyStat` rows, then commit; any failure rolls the whole transaction back and re-raises. `created_at` is UTC ISO-8601 with a `Z` suffix (same format as ADR-032); ids are `uuid4().hex`. `analysis_version` comes from `config.ANALYSIS_VERSION`.
- Stored per-session values come verbatim from the engine: `passage_text` = the replayed text snapshot, `typed_text` = `ReplayResult.typed_final`, `active_duration_ms` and `end_reason` from the replay. `started_at` and the `ignored` counters are **not persisted** — blueprint §9 defines no columns for them (ADR-026 keeps `started_at` informational).
- Only validated events *up to the derived end* are stored (EVENT_SCHEMA §10). Replay drops events strictly as a trailing suffix once an end is derived (the retained prefix includes the completing keystroke and excludes the timer-boundary event), so the retained events are `validated.events[:len(events) - dropped_after_end]`.
- `data_quality_json` holds a JSON array of the non-zero tolerated condition entries `{code, count, message}` (the `warnings` list); NULL when none occurred. `invalid_dwell_count` is recovered from that array on read-back (0 when absent); `iki_hist_json` stays NULL until P1.
- `SessionRecord` (frozen dataclass) is the read shape for both the POST response and the results page. Read-back reconstructs a full `SessionMetrics` from the stored columns; `error_rate` is derived at that point as `100 − accuracy_pct`. This is a deliberate, minimal deviation from "the repository computes no metrics": it only applies the documented identity `error_rate = 100 · E / K = 100 − accuracy_pct` (`docs/METRICS.md` §4.4) because the blueprint defines no `error_rate` column, and it never recomputes anything from raw events. It deviates from ADR-033's wording ("derivable" rather than derivable *at read time*) in rendering only.
- `list_sessions(limit, offset)` returns newest-first summaries (`SessionSummary`: id, created_at, mode, duration_limit_ms, active_duration_ms, end_reason, net_wpm, accuracy_pct) ordered by `created_at DESC, id DESC`, with the exact total count.
- Routes keep handling only JSON shaping; pages.py renders from `SessionRecord`; the results template reads `session.active_duration_ms` instead of the in-memory `replay` object. `app/session_store.py` is deleted.
**Consequences:** `pytest test_sessions.py` keeps working with `SessionRepository` behind the same `create`/`get`/`count` calls. No metric is recomputed from raw events on read; the only arithmetic is the documented error-rate identity. `GET /api/sessions/<id>` (P0-D2-03) can build directly on `get()` and `get_key_stats()`.

### ADR-035: Session detail API response shape
**Date:** 2026-11-10
**Status:** Approved
**Context:** Blueprint §10 fixes `GET /api/sessions/<id>` as `{ session, metrics, key_stats }` but does not name the nested fields. The persisted shapes already exist: `SessionRecord` (ADR-034), `SessionMetrics`, and `SessionKeyStat` (ADR-024). The endpoint must serialise them without recomputing metrics or exposing SQL.
**Decision:**
- `session` mirrors the stored session record: `session_id`, `created_at`, `schema_version`, `mode`, `duration_limit_ms`, `text_ref`, `passage_text`, `typed_text`, `active_duration_ms`, `end_reason`, `client`, `layout_hint`, `analysis_version`, and `warnings` (the persisted non-zero data-quality conditions).
- `metrics` is exactly `asdict(SessionMetrics)` — the stored metric fields including the read-back `error_rate` identity and `invalid_dwell_count` (ADR-034). Session context (`mode`, `duration_limit_ms`, `active_duration_ms`, `end_reason`, `analysis_version`) lives in `session`, unlike the flattened `POST /api/sessions` response.
- `key_stats` is the ordered list of stored `SessionKeyStat` rows (`key_code`, `attempts`, `errors`, `dwell_count`, `dwell_sum_ms`, `iki_count`, `iki_sum_ms`) from `get_key_stats()`. No means or classification are added here; those belong to the P0-D3-01 analytics endpoint.
- Unknown ids return `404 NOT_FOUND` in the documented error envelope. The route calls only `repository.get()` and `repository.get_key_stats()`.
**Consequences:** The response exposes persisted values only, so the results page and API cannot disagree. The remaining P0-D2-03 UI can consume this shape; adding per-key means or `series.wpm` (P1) is an additive API change.

### ADR-036: History list contract and client-rendered history page
**Date:** 2026-11-14
**Status:** Approved
**Context:** P0-D2-04 needs `GET /api/sessions?limit=&offset=`, but blueprint §10 fixes only the `{ items, total }` envelope and the `limit ≤ 100` cap. It does not fix the default limit, the behaviour for invalid query values, or the item field set. `docs/UI_DESIGN.md` §8 requires a six-column table including consistency and 25 rows per page, while `SessionSummary` (ADR-034) carried only net WPM and accuracy. The task requires `history-page.js` but does not say whether the page is server-rendered or fetches the list.
**Decision:**
- `items` is one `SessionSummary` object per row with `session_id`, `created_at`, `mode`, `duration_limit_ms`, `active_duration_ms`, `end_reason`, `net_wpm`, `accuracy_pct` and `consistency_score`. `SessionSummary` gains `consistency_score` because the documented table needs it; the repository's list `SELECT` reads `session_metrics.consistency_score`. `total` is the exact count of all stored sessions.
- `limit` defaults to `HISTORY_PAGE_SIZE = 25` and must be an integer from 1 to `SESSION_LIST_MAX_LIMIT = 100`. `offset` defaults to 0 and must be a non-negative integer. Both are validated against a digits-only pattern before reaching the repository; violations return `422 VALIDATION_ERROR` with `field` `"limit"` or `"offset"`, matching the existing words-endpoint convention.
- `/history` is a thin server-rendered shell (`pages.history_page`) carrying the six column headers, the empty state and a page-size data attribute. `history-page.js` fetches `/api/sessions?limit=<pageSize>&offset=<offset>`, renders rows, and owns Previous/Next state. Page size travels through `data-page-size`, so the constant is not duplicated in JavaScript.
- Rendering formats stored values only (`toFixed`/date locale); it computes no metric. Duration and mode labels are unit presentation of stored fields.
- Each row carries a real `<a>` to `/results/<session_id>` in its first cell for keyboard and screen-reader navigation, plus a row-level click listener. A click on an inner link is left to the browser so navigation is not duplicated.
- The empty state is the `docs/UI_DESIGN.md` §8 text and only appears when `total == 0`; the table and controls are hidden in that state.
- `base.html` now resolves the history nav entry with `url_for('pages.history_page')` per ADR-028; the rendered path stays `/history`.
**Consequences:** The list API, page and results page agree on the summary shape. Pagination is bounded server-side, so a client cannot request an unbounded page. Any future page size change is a single constant edit, and adding columns to the list is an additive `SessionSummary` change.

---

## Open Ambiguities

### AMB-001: Exact words in `words_en.json`
**Date:** 2026-11-06
**Status:** Resolved by ADR-027 (2026-11-06)
**Context:** The blueprint says "~200 common English words" but does not list them.
**Decision needed:** Author must provide or approve the specific word list. The requirement is: lowercase, ASCII 32–126 only, ~200 words, common English.
**Impact:** The word-generator determinism depends on the exact list and its ordering. Once set, the list must not be reordered (it would change seed → text mappings).
**Resolution:** The author approved authoring original project content. `app/data/words_en.json` now holds 200 unique lowercase `a-z` words in a frozen order; see ADR-027.

### AMB-002: Exact passage texts
**Date:** 2026-11-06
**Status:** Resolved by ADR-027 (2026-11-06)
**Context:** The blueprint says "~12 original or public-domain ASCII passages" and notes the user will author them (§16, assumption 5).
**Decision needed:** Author must provide the passage texts. Each must be: printable ASCII 32–126 only, original or verified public-domain, reasonable length for a typing test.
**Impact:** These are needed before `texts.py` and the passage-mode UI can be fully tested.
**Resolution:** Twelve original ASCII passages (`p_001`–`p_012`) were authored for this build with author approval; see ADR-027. Editorial review before release remains with the author.

### AMB-003: Passage selector UI — ordered or labelled?
**Date:** 2026-11-06
**Status:** Resolved by ADR-029 (2026-11-06)
**Context:** The blueprint mentions a passage selector in the config strip but does not specify whether passages have titles, descriptions, or any ordering rule.
**Decision:** Use passage `id` (e.g., `p_001`) as internal identifier; display a short label or first ~40 chars as the `<select>` option text. Record here if a different approach is chosen.
**Resolution:** `GET /api/texts/passages` returns the frozen source order with a `label` built from the first 40 characters plus `"..."` when longer; no title field is added. See ADR-029.

### AMB-004: Moving average in progress chart — window or cumulative?
**Date:** 2026-11-06
**Status:** Open
**Context:** The blueprint says "5-session moving average" but does not specify whether this is a trailing window average or an expanding average for early sessions (fewer than 5).
**Decision:** Use a **trailing window** of 5 sessions. For the first 1–4 sessions, use all available sessions (expanding window). This is the conventional interpretation. Log here if changed.
