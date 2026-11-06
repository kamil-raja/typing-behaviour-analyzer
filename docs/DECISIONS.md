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

## Open Ambiguities

### AMB-001: Exact words in `words_en.json`
**Date:** 2026-11-06
**Status:** Open
**Context:** The blueprint says "~200 common English words" but does not list them.
**Decision needed:** Author must provide or approve the specific word list. The requirement is: lowercase, ASCII 32–126 only, ~200 words, common English.
**Impact:** The word-generator determinism depends on the exact list and its ordering. Once set, the list must not be reordered (it would change seed → text mappings).

### AMB-002: Exact passage texts
**Date:** 2026-11-06
**Status:** Open
**Context:** The blueprint says "~12 original or public-domain ASCII passages" and notes the user will author them (§16, assumption 5).
**Decision needed:** Author must provide the passage texts. Each must be: printable ASCII 32–126 only, original or verified public-domain, reasonable length for a typing test.
**Impact:** These are needed before `texts.py` and the passage-mode UI can be fully tested.

### AMB-003: Passage selector UI — ordered or labelled?
**Date:** 2026-11-06
**Status:** Open
**Context:** The blueprint mentions a passage selector in the config strip but does not specify whether passages have titles, descriptions, or any ordering rule.
**Decision:** Use passage `id` (e.g., `p_001`) as internal identifier; display a short label or first ~40 chars as the `<select>` option text. Record here if a different approach is chosen.

### AMB-004: Moving average in progress chart — window or cumulative?
**Date:** 2026-11-06
**Status:** Open
**Context:** The blueprint says "5-session moving average" but does not specify whether this is a trailing window average or an expanding average for early sessions (fewer than 5).
**Decision:** Use a **trailing window** of 5 sessions. For the first 1–4 sessions, use all available sessions (expanding window). This is the conventional interpretation. Log here if changed.
