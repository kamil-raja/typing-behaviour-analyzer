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
**Decision:** The heatmap is described as "a conservative heuristic relative to the user's own typing history." The words "significant" and "statistically" must not appear in any user-facing string (enforced by `test_hygiene.py`). The API returns `"method": "wilson_vs_pooled_baseline_heuristic"`.
**Consequences:** The heuristic is still useful for identifying relatively error-prone keys. Users are not misled about its statistical validity.

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
