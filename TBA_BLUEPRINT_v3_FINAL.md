# Typing Behaviour Analyzer: Blueprint v3 (single source of truth)

Status: **Final for implementation.** This document supersedes v1, all v2 drafts, and the earlier v2 final file. Use this file as the single source of truth.
Target: Windows 11, Chrome/Edge, Python 3.10+, three-day build, single local user.
Unchanged from v1: stack (Flask, sqlite3, vanilla JS ES modules, Chart.js vendored, pytest), layered architecture, visual direction, both themes and tokens, database approach, feature vision.

---

## 0. Revision log (where each requested issue is resolved)

| # | Issue | Resolution |
|---|---|---|
| 1 | Gross WPM | §7: `(K/5)/T_min`, K = all accepted printable keystrokes. Net uses correct chars in the final buffer. Invariant Net ≤ Gross. |
| 2 | Time-mode completion contradiction | §4: one rule for both modes; timer expiry wins at the exact boundary. The server derives the end from the submitted events; the client sends no `ended_at_ms` or `end_reason`. |
| 3 | Repeated Backspace dwell | §5.3: repeat downs are deletion actions only and never touch the pending-keydown map. |
| 4 | ASCII 32–126 | §5.2 / §6.2: the same regex on the client and the server, `fullmatch` only, plus an engine-level assertion. |
| 5 | Heatmap statistics | §8: described as a conservative heuristic over the user's own history, not a significance test. |
| 6 | Final-character correction | §4.2: a passage ends **only when the buffer equals the text exactly**. A wrong last character does not end the test. |
| 7 | Timing claim | §5.5: the clamping claim is removed. Only the honest limitation remains. |
| 8 | IKI definitions | §7.3: **one interval list**, valid only when `0 < I < 1000 ms`; zero intervals are excluded. |
| 9 | Corrected errors | §7.4: split into `corrected`, `erased_unresolved` and `uncorrected`. The invariant is `E = U + Ec + Eu`. |
| 10 | Tab accessibility | §5.4: Tab is never intercepted; leaving the typing viewport cancels an active test. |
| 11 | Scope | §1: bigrams, rhythm and pause charts, compare, recalculation and the report page moved to P2 and removed from the v1 schema and API. |
| 12 | Regression tests | §14: every fix has named tests with hand-computed expected values. |
| 13 | Reference implementations | §3: verified vs unverified vs our choice. |
| 14 | Tab/focus contradiction | §5.4: Tab is never trapped; leaving the typing viewport cancels an active test. |
| 15 | Zero IKI intervals | §7.3 / §8: valid intervals require `0 < I < 1000 ms`; zero intervals are excluded and counted as invalid timing intervals. |
| 16 | Exact timer boundary | §4.2 / §6.3: timer expiry wins at `t >= duration_limit_ms`; events at the exact limit are not accepted. |
| 17 | Timing trust boundary | §4.3 / §16: server replays and validates client-reported events; this is not independent or tamper-proof timing verification. |
| 18 | Final-text accuracy at empty buffer | §7.3: `final_accuracy_pct` is `null` when `N = 0`; otherwise the formula applies. |
| 19 | Hygiene-test contradictions | §14.2: heatmap wording checks are limited to user-facing UI strings; timing checks target unsupported precision claims and do not ban CSS `clamp()`. |
| 20 | Analysis version | §9: `analysis_version` is `1` for the initial metric-definition set and increments when metric definitions change. |
| 21 | Backspace event identity | §5.3 / §7.1: identify Backspace actions using `event.key`; pair keyup with keydown by `event.code`. |
| 22 | Timestamp fallback | §5.1 / `EVENT_SCHEMA.md`: if the non-finite timestamp fallback is used, log that occurrence for diagnostics. |

---

## 1. Scope and priorities (revised)

| P0: must work | P1: important, only after all P0 works | P2: optional, later |
|---|---|---|
| Event capture (§5) · Python engine and validator · SQLite persistence · typing test UI (time + passage modes) · results page · history list · light + dark themes (no flash) · **interactive error heatmap** · progress charts (WPM, accuracy) · `sessions.csv` export | Dwell and speed heatmap modes · IKI histogram · per-second WPM chart on results · events CSV · delete session · retry-save · layout-mismatch banner · print stylesheet for the results page · README polish | Bigram analysis · rhythm chart · pause analysis charts · session comparison · recalculation endpoint · dedicated printable report page · pause/resume on focus loss · error-cascade guard · non-QWERTY support · colour-blind palette |

**Rule:** never start a P1 item while any P0 item is broken. If time runs out, cut from the right.

---

## 2. Architecture (condensed, unchanged in substance)

```
BROWSER: capture.js ─► events in memory ─► ONE POST at test end ──► FLASK routes
         typing-engine.js (UI, provisional live stats)               │ validators.py
         charts.js (Chart.js, theme-aware)                           ▼
                                                    ENGINE (pure Python): replay → metrics → key stats
                                                                     │ repository.py (all SQL)
                                                                     ▼
                                                                  SQLite
```

| Layer | Does | Must not |
|---|---|---|
| Browser JS | Captures events, shows **provisional** live WPM and accuracy, submits once | Compute any stored or final statistic. It does not send an end time or reason; it sends browser-reported event timestamps for server-side replay. |
| Routes | Parse, validate, call the engine and repository, shape JSON | Contain metric math or SQL |
| Engine (`app/engine/`) | Replay, classification, all metrics, heatmap classification | Touch HTTP or the DB |
| Repository | All SQL | Compute metrics |

Pages are Jinja templates; each loads one ES-module script that fetches `/api/...`. There is no ORM, no bundler and no auth.

---

## 3. Reference behaviour: Monkeytype and Keybr

**Method and limits.** I read Monkeytype's About page, its release notes and settings documentation, Keybr's repository README, and some third-party ports. **I did not read either project's source code.** Anything labelled "unverified" must be treated as an assumption. **Do not copy code**: Keybr is AGPL-3.0 (verified from its README), and check the Monkeytype licence before reusing anything.

| Topic | Verified (source) | Unverified | **Our choice and reason** |
|---|---|---|---|
| WPM | Monkeytype: "wpm" counts characters in **correctly typed words including spaces**, ÷5, normalised to 60 s. "Raw wpm" is calculated the same way but **includes incorrect words** (About page). | Exact internals | **Character-level, not word-level.** We are caret-locked with no word skipping, so a character is the natural unit. Gross includes every accepted keystroke (§7); net counts correct characters left in the buffer. We document that this differs from Monkeytype's word-level wpm, so numbers will not match exactly. |
| Accuracy | Monkeytype: "percentage of correctly pressed keys" | n/a | **Same idea:** `C/K`. Corrected mistakes still count against accuracy. |
| Consistency | Monkeytype: based on the coefficient of variation of **raw wpm**, mapped onto 0–100 (About page) | Its exact mapping function. I could not confirm it. | **Our own, per your brief:** CV of valid **inter-key intervals** with `100·max(0, 1−CV)`. It is labelled "timing consistency (interval-based)" so nobody compares it with Monkeytype's number. |
| Results chart | Monkeytype plots a global-average wpm line and a local "raw" line (About page) | n/a | P1 per-second chart of cumulative net WPM, with error ticks. |
| Error handling modes | Monkeytype has Stop-on-error (letter/word), Confidence mode, word-delete with Alt+Backspace, and a Freedom mode (release notes, settings docs) | A third-party article says Monkeytype blocks typing after about 8 consecutive mistypes | **Plain "continue and correct" mode only.** Everything else is out of scope (P2 guard at most). Ctrl/Alt+Backspace is ignored. |
| Restart / Tab | Monkeytype has configurable quick-restart keys (tab/esc/enter) and fixed Ctrl+Tab so it switches tabs rather than restarting (release notes) | n/a | **Esc restarts; Tab is not hijacked outside a running test** (§5.4). We never swallow Ctrl/Meta/Alt shortcuts. |
| Focus loss | Monkeytype has an "out of focus warning" | Whether it cancels the test | We **cancel** the test (§5.4). |
| Last-character / completion | Not verified | Monkeytype's behaviour when the final character is wrong | **Our own rule (§4.2):** the test ends only on an exact match. |
| Per-key stats | Keybr "tracks every keystroke and computes statistics for each individual key," uses a user-set **target speed**, and generates lessons for weak keys (README) | Its exact per-key formula. Third-party ports describe an exponential-smoothing speed/confidence score, which is secondhand. | **We are an analyzer, not a tutor:** no target speed, no adaptive lessons. The primary heatmap is **error-rate based**. Speed and dwell are secondary, informational modes (P1). |
| Heatmap UX | Keybr and similar tools colour an on-screen keyboard per key and show detail on selection (third-party descriptions, not Keybr's own docs) | Exact colour scales | Click-to-pin inspector, an explicit "insufficient data" grey, and text labels alongside the colours. |

---

## 4. Test lifecycle and completion (single behaviour for both modes)

### 4.1 States (client)

`idle` → `running` → `finished` (or `cancelled`).

- **idle:** nothing recorded. The test starts at the **first accepted printable keystroke**, which is `t = 0`. Backspace and every other key are ignored while idle.
- **running:** all capture rules (§5) apply.
- **finished:** the capture listeners are removed. The payload is submitted once.
- **cancelled:** by Esc (restart) or by focus loss. Nothing is saved.

### 4.2 The one completion rule

> **A test ends at the earliest of:**
> **(a) Completion:** the buffer equals the text **exactly** (same length and every character correct), immediately after an accepted keystroke. Applies to both modes.
> **(b) Timer expiry:** time mode only, when `t >= duration_limit_ms`. **Timer expiry takes precedence at the exact boundary.** Therefore, a keystroke timestamped exactly at the duration limit is not accepted, even if it would complete the text. Completion is accepted only when its keystroke timestamp is strictly earlier than the limit.

Consequences:

- **Passage mode** ends only through (a). If the buffer reaches the text length with any mistake, **the test does not end.** The caret stays at the end, further printable keys are not accepted (the client ignores them), and Backspace stays available. The UI shows "fix the highlighted characters to finish". This is how a wrong final character is corrected before the test ends. A passage test therefore always finishes with `U = 0`.
- **Time mode** ends through (b), or earlier through (a) if the user types the whole text correctly. Word-count text is sized so (a) is practically unreachable: **15 s → 120 words, 30 s → 200, 60 s → 350.** The rule is still defined, so behaviour is consistent if it happens.
- **Active duration `T`:** completion → `t` of the completing keystroke (which must be `< duration_limit_ms` in time mode). Timer expiry → exactly `duration_limit_ms`.

### 4.3 Server-side replay and end derivation

- The client submits only `mode`, `duration_limit_ms`, `text_ref` and `events`. It sends **no** `ended_at_ms` and **no** `end_reason`.
- The engine replays the submitted event sequence and derives the end (§6.3). `end_reason ∈ {"completed","time_up"}` and `T` are **stored results**, not inputs.
- The client runs the same rule to decide when to stop capturing and submit. The server is authoritative for validation and metric calculation **over the submitted event sequence**; it does not independently observe the physical keyboard or browser clock.
- Event timestamps originate in the browser and are client-reported data. The server can validate their structure and ordering, but cannot prove they are genuine or tamper-free. This is acceptable for the stated single-user local application; it is not a secure assessment or anti-cheating system.
- For time mode, events with `t >= duration_limit_ms` are not accepted; timer expiry wins at the exact boundary. Other events after a derived completion are dropped and counted (`dropped_after_end`). A key still held at the end has no keyup and counts as `open_at_end`, which is expected and is not an error.

---

## 5. Event capture rules

### 5.1 Timing source

Timestamp = `event.timeStamp`, falling back to `performance.now()` at handler time if it is not a finite number. `t` = timestamp − the first accepted keydown's timestamp, in ms rounded to 0.1. `started_at` (wall clock) is informational only. During development, log `event.timeStamp − performance.now()` once to sanity-check that both share a clock (assumption, §16). If the fallback is used, increment a diagnostic counter and log the occurrence; do not silently mix clocks without recording that fallback occurred. Chrome/Edge are expected to provide finite event timestamps, so this is a defensive path.

### 5.2 What is accepted (client and server use the identical rule)

- **Printable:** `event.key` matches `^[\x20-\x7E]$`, a single ASCII character 32–126, which includes Space. This excludes non-ASCII (é, ß, NBSP), emoji (two UTF-16 units), control characters, `"Dead"`, `"Process"` and anything with `event.isComposing`. These are discarded and counted in `ignored.unsupported_chars`.
- **Backspace:** `event.key === "Backspace"`, no Ctrl/Meta/Alt.
- **Modifiers and shortcuts:** Ctrl/Meta/Alt combinations are ignored and **not** `preventDefault`ed, except AltGr (`getModifierState("AltGraph")`), which is treated as ordinary typing. Shift, Ctrl, Alt, Meta and CapsLock alone are not recorded.
- **Everything else** (arrows, Home/End, Delete, F-keys, Enter): ignored and counted in `ignored.unsupported_keys`. They are `preventDefault`ed only while `running`.
- Paste: there is no text field, so nothing can be inserted. A `paste` listener calls `preventDefault()` and counts `ignored.paste_attempts`.
- At a full buffer, printable keydowns are ignored by the client (not submitted); the server rejects a submitted printable keydown at a full buffer as an invalid event sequence. This intentional client/server asymmetry prevents extra input while retaining strict server validation.

### 5.3 Repeats, Backspace and the pending-keydown map (fixes #3)

The client and engine each keep `pending: code → t_down`, **written only by non-repeat downs**. Identify a Backspace action by `event.key === "Backspace"`, not by assuming `event.code === "Backspace"`. Store its pending keydown under that event's actual `code`, just like other keys; pair the keyup by matching `event.code` because keyup events send `key: null`. A Backspace repeat is valid only when a pending original exists for the same `code`.

| Situation | Handling |
|---|---|
| Printable `down`, `repeat: false` | Accepted. `pending[code] = t`. |
| Printable `down`, `repeat: true` | **Discarded** (`preventDefault`) and counted in `ignored.repeat_keydowns`. A held key is not a keystroke. The server treats one in a payload as an error. |
| Backspace `down`, `repeat: false` | Recorded. `pending[event.code] = t`. It deletes one character if the buffer is non-empty. The action is identified by `event.key`, not by a hard-coded `code` value. |
| Backspace `down`, `repeat: true` | Recorded with `repeat: true` **only if `pending[event.code]` already exists**. It is a deletion action. **It never reads, writes or overwrites `pending`.** If there is no pending original for that code, the client ignores it, and the server rejects it. |
| `up` | If `pending[code]` exists → pair it, `dwell = t_up − t_down`, delete the entry. Otherwise it is an orphan: the client does not record it, the server drops it and counts `orphan_up`. |
| A second non-repeat `down` for a code that is already pending | Missing keyup: the old entry is counted `missing_up`, and the new one replaces it. |

So one physical Backspace hold (`down`, N repeat downs, one `up`) gives **N+1 deletions**, **one dwell sample** measured from the original keydown, **one press**, and **one timed action** for IKI purposes.

### 5.4 Focus, Tab and accessibility (fixes #10)

- **Capture scope:** keystrokes are captured only when `event.target` is the passage viewport. The viewport is focusable (`tabindex="0"`, `aria-label="Typing area. Start typing to begin. Press Escape to restart."`) and receives focus on load and after a config control is activated.
- **Tab:** Tab and Shift+Tab are **never intercepted or prevented**. Browser-native focus navigation remains available in every state; this avoids a keyboard trap. If focus leaves the passage viewport while a test is `running` (including through Tab, Shift+Tab or a mouse click on another control), the active test is cancelled and discarded, with a clear message. Focus is not forcibly moved back; the user can continue navigating normally and click/focus the typing area to start again.
- **Mouse during a run:** clicking a config control cancels the test and applies the new setting. When the user returns to the passage viewport, Space and other typing keys are captured only there, not by unrelated controls.
- **Focus loss** (`window blur`, `visibilitychange → hidden`) while `running`: the test is **cancelled and discarded** with the message "Test cancelled. The window lost focus." (P2: pause/resume). Before the first keystroke, blur only shows the "click to focus" overlay.
- **Esc:** while running, Esc cancels the test and returns the UI to `idle`; it is not a keyboard trap escape mechanism because Tab is never blocked.
- Focus rings (`:focus-visible`) are always visible, and motion respects `prefers-reduced-motion`. A screen-reader experience for the typing area is limited (§16).

### 5.5 Timing honesty statement (fixes #7)

Timestamps are what the browser reports for each event. They include keyboard hardware and driver behaviour, OS input handling, browser event dispatch and main-thread scheduling, and timer precision varies by browser, OS and security settings. The app does **not** claim any specific resolution, and its numbers are **not laboratory-grade**. They are suitable only for relative comparison on the same machine and browser. This statement goes in the README and on a visible "About the measurements" note on the results page.

---

## 6. Event contract and validation

### 6.1 Event object

```json
{ "seq": 17, "type": "down", "t": 1523.4, "code": "KeyE", "key": "e", "repeat": false }
{ "seq": 18, "type": "up",   "t": 1611.0, "code": "KeyE", "key": null, "repeat": false }
```

| Field | Rules |
|---|---|
| `seq` | int; starts at 0; contiguous |
| `type` | `"down"` \| `"up"` |
| `t` | finite number ≥ 0; non-decreasing |
| `code` | `re.fullmatch(r"[A-Za-z0-9]{1,32}", code)` |
| `key` | `down`: `re.fullmatch(r"[\x20-\x7E]", key)` or exactly `"Backspace"`. `up`: must be `null` (keyup `key` can change with Shift and is unused, so it is not sent). |
| `repeat` | bool; `true` only for `Backspace` `down` |

**Python pitfalls the validator must avoid:** use `re.fullmatch`, not `re.match` with `$` (`$` accepts a trailing newline). Never use `str.isalnum()`, `isprintable()` or `\w` for these checks, because they accept non-ASCII. `isascii()` alone is not enough (it accepts control characters).

### 6.2 Session payload (`POST /api/sessions`)

```json
{
  "schema_version": 1,
  "mode": "time",
  "duration_limit_ms": 30000,
  "text_ref": { "type": "words", "seed": 482913, "count": 200 },
  "started_at": "2026-11-06T10:05:00.000Z",
  "client": { "user_agent": "…", "platform": "Win32", "layout_hint": "qwerty|non-qwerty|unknown" },
  "ignored": { "repeat_keydowns": 0, "shortcuts": 1, "unsupported_keys": 2, "unsupported_chars": 0, "paste_attempts": 0 },
  "events": [ … ]
}
```

- `mode`: `"time"` (with `duration_limit_ms ∈ {15000, 30000, 60000}`) or `"passage"` (`duration_limit_ms: null`).
- `text_ref`: `{"type":"passage","id":"p_003"}` or `{"type":"words","seed":int,"count":int(10..400)}`. **The client never sends the text.** The server rebuilds it.
- All passages and the word list are checked at startup to be ASCII 32–126 only. Startup fails loudly otherwise.

### 6.3 Server processing order

1. **Schema validation (422 `VALIDATION_ERROR`, with `details`):** everything above; 2–10 000 events; body ≤ 2 MB (413 otherwise); the first event is a non-repeat printable `down`; `t` non-decreasing; no repeat-printable; no `up` carrying a non-null `key`.
2. **Resolve the text** (404 `TEXT_NOT_FOUND`). Assert text and event keys are ASCII 32–126; any violation is a validation error, never silently processed.
3. **Replay** (engine, §7.1). In order, it derives `end_t` per §4.2; in time mode, any event with `t >= duration_limit_ms` is excluded and the end reason is `time_up`. It drops events after a derived completion and raises `INVALID_EVENT_SEQUENCE` (422) for: a printable `down` when the buffer is already full; a Backspace repeat with no pending original.
4. **Outcome checks:** passage mode with no completion → 422 `INCOMPLETE_SESSION`. `K < 10` or `T < 3000 ms` → 422 `SESSION_TOO_SHORT`.
5. Compute metrics → one transaction → `201`.

Tolerated and reported as `warnings` / `data_quality`: orphan ups, missing keyups, `open_at_end`, invalid dwell, `dropped_after_end`.

Error shape for all endpoints: `{ "error": { "code", "message", "details": [ {"field","problem"} ] } }`. Codes: `INVALID_JSON` 400, `VALIDATION_ERROR` 422, `INVALID_EVENT_SEQUENCE` 422, `INCOMPLETE_SESSION` 422, `SESSION_TOO_SHORT` 422, `TEXT_NOT_FOUND` 404, `NOT_FOUND` 404, `PAYLOAD_TOO_LARGE` 413, `INTERNAL_ERROR` 500.

---

## 7. Metrics (authoritative definitions)

### 7.1 Replay

Inputs are the server-built text `P` and the validated events. Start with an empty buffer; each buffer slot holds the keystroke that produced it.

- **Accepted keystroke:** a non-repeat printable `down` while the buffer is not full. `p = len(buffer)`; `expected = P[p]`; `correct = (typed == expected)`. Append it.
- **Deletion:** a Backspace `down` (repeat or not) while the buffer is non-empty. Pop the last slot and mark its keystroke `deleted`. A Backspace on an empty buffer is ignored.
- After each accepted keystroke, if `buffer == P` exactly → end (completion).
- The final buffer is `typed_final`. All deleted keystrokes keep their position `p`.

### 7.2 Symbols

`K` = accepted keystrokes · `C` = correct ones · `E = K − C` · `N = len(typed_final)` · `U` = positions `i < N` with `typed_final[i] ≠ P[i]` · `T` = active duration (§4.2), `T_min = T/60000`. A session is saved only if `K ≥ 10` and `T ≥ 3000 ms`.

### 7.3 Formulas

| Metric | Definition |
|---|---|
| **Gross WPM** | `(K / 5) / T_min`. Counts **every accepted printable keystroke**, including incorrect attempts and characters later deleted. **Backspaces are not printable and are not counted.** |
| **Net WPM** | `max(0, ((N − U) / 5) / T_min)`: correct characters remaining in the final buffer. Invariant: `Net ≤ Gross` (because `N ≤ K`). |
| **Accuracy** (primary) | `100·C/K` (keystroke accuracy, same idea as Monkeytype's "correctly pressed keys") |
| **Final-text accuracy** | `null` when `N = 0`; otherwise `100·(N−U)/N`. The empty final buffer has no characters whose correctness can be measured. |
| **Error rate** | `100·E/K` (= 100 − accuracy); per key: `x_k / n_k` |
| **Backspace deletions** | Effective deletions, including held-key repeats. **Backspace presses** = non-repeat Backspace downs. |
| **Dwell** | For each non-repeat `down` paired with its `up` (§5.3): `d = t_up − t_down`. Valid if `0 < d ≤ 1000 ms`. Report mean, median, count. **Backspace is excluded from the overall figure** and kept only in its own per-key stats. |
| **Timed actions** | Accepted printable keystrokes **and** non-repeat Backspace presses that deleted a character. Repeat downs are never timed actions. |
| **Interval list `I`** | `I_i = t_down[i] − t_down[i−1]` for consecutive timed actions. The first has none. |
| **Pause** | An interval with `I ≥ 1000 ms` (`PAUSE_THRESHOLD_MS`). Report `pause_count`, `total_pause_ms` (sum of those intervals) and `longest_pause_ms`. Zero intervals are neither pauses nor valid intervals. |
| **Valid intervals `V`** | `0 < I < 1000 ms`. Zero intervals are excluded as invalid timing observations; they are counted in `zero_interval_count` for data-quality reporting. **This is the single list behind every interval statistic.** |
| **Average IKI, median IKI, SD** | Mean, median and sample SD (n−1) of `V`. All are `null` if `|V| < 5`. **Pauses are excluded from all of them.** |
| **Consistency** | If `|V| ≥ 30` and `mean > 0`: `CV = SD/mean`, `score = round(100·max(0, 1−CV), 1)`. Otherwise `null`. CV is always shown beside it. A descriptive index, not a validated measure. |
| **IKI histogram [P1]** | 40 bins × 25 ms over `V` only. Pauses never appear in it, since they are reported separately. |
| **Clean transition** | Two consecutive timed actions that are **both accepted printable keystrokes and both correct**, with `0 < I < 1000`. Used for per-key IKI (§8) and for any future bigram timing. |
| **Per-key IKI** | For each clean transition, the interval is added to the **later** keystroke's expected key: `iki_count += 1`, `iki_sum_ms += I`. Mean = sum/count. It is a subset of `V`, never a different measure. |

*Consistency of IKI definitions:* results, analytics and heatmap all draw on `V`. The only difference is eligibility (the heatmap needs clean transitions), and this is stated in the UI tooltips.

### 7.4 Error accounting (fixes #9)

Every **incorrect** keystroke ends in exactly one of three states:

| Metric | Definition |
|---|---|
| **`uncorrected_errors` (U)** | Incorrect keystrokes still in the final buffer (equals the position-based count of wrong characters). |
| **`corrected_errors` (Ec)** | Incorrect keystrokes that were **deleted** and whose position `p` holds the **correct** character in the final buffer. |
| **`erased_unresolved_errors` (Eu)** | Incorrect keystrokes that were **deleted** but whose position is **empty** (`p ≥ N`) or holds a wrong character in the final buffer. |

**Invariant:** `E = U + Ec + Eu` (tested on every fixture). "Corrected" now means the position was actually fixed. Eu is shown on the results page only when non-zero, as "erased, not retyped correctly", with a tooltip. Eu is mostly relevant in time mode, where the timer can expire right after a deletion.

Cascade note: an omitted letter makes the following keystrokes wrong until fixed. This inflates `E`. It is a known limitation (§16).

### 7.5 Per-second series [P1]

For each whole second `s`, starting at `s = 1`, `net_wpm_cum(s)` is Net WPM computed on the buffer state at time `s` (the last replayed buffer state at or before `s` seconds; if no later event exists, retain the last known state) (correct characters ÷5 ÷ `s/60`), plus `errors_in_sec(s)`.

### 7.6 Changes from v1 (metric diff)

| Metric | v1 | v2 |
|---|---|---|
| Gross WPM | `N/5` per minute | **`K/5` per minute** (all accepted printable keystrokes) |
| Net WPM | same | unchanged (`(N−U)/5`) |
| Active duration | contradictory | derived by the server (§4) |
| Corrected errors | `E − U` | **`Ec`** (deleted and position finally correct) plus **`Eu`** (new), with `E = U + Ec + Eu` |
| IKI mean/median/SD | unspecified for pauses | **exclude pauses** (`V`) everywhere |
| Backspace timing | repeats could overwrite dwell | repeats never touch `pending` |
| End reason / `ended_at_ms` | client-supplied | **server-derived** |
| Bigram, collateral deletions, pause bands/locations | P1 | **P2** (removed from the v1 schema) |

---

## 8. Keyboard heatmap

### 8.1 Identifiers and attribution

- `event.code` = physical key (used for dwell pairing and for the drawn key). `event.key` = the character (used for correctness).
- **Observation `n`** for a key = accepted keystrokes whose **expected character** maps to that key through the static US-QWERTY table `CHAR_TO_CODE` (covers all of ASCII 32–126; a capital and its lowercase both map to the letter key; shifted symbols map to their base key). **Errors `x`** = those that were incorrect, counted when they happen, even if later deleted.
- **Dwell** is attributed to the key **physically pressed** (the `code`). Dwell and observation counts are therefore tracked separately.
- A missed Shift is blamed on the letter key (limitation). Non-tracked keys (Shift, Ctrl, Tab, Caps, Enter) render neutral. Backspace shows its press count and dwell only.

### 8.2 Error-mode classification: a conservative heuristic

For each key with `n ≥ 20` (otherwise grey, "n of 20"): `e = x/n`; `b` = the user's pooled error rate over all tracked keys in scope, `Σx/Σn`, floored at 1 %; `lo`, `hi` = the Wilson interval for `e` (z = 1.96):
`centre = (e + z²/2n)/(1 + z²/n)`, `half = z·√(e(1−e)/n + z²/4n²)/(1 + z²/n)`.

- **Weak (red):** `lo > b` **and** `e − b ≥ 0.02` **and** `x ≥ 3`.
- **Strong (green):** not weak and `e ≤ b`.
- **Average (yellow):** otherwise.

**How to describe this (fixes #5).** It is a **conservative heuristic relative to the user's own typing history**. It is **not a hypothesis test, a p-value or a claim of statistical significance.** The words "significant" and "statistically" must not appear in the UI or docs for it. Reasons: the baseline includes the key itself, about 30 keys are compared with no multiple-comparison correction, keystrokes are not independent (cascades, clustering within sessions), and the practical-margin and minimum-count rules are ad hoc choices. The API returns `"method": "wilson_vs_pooled_baseline_heuristic"`. Reference value for tests: Wilson(3 of 20) ≈ [0.052, 0.360].

### 8.3 Dwell and speed modes [P1], informational only

Dwell mode needs `dwell_count ≥ 20`. The colour scale is `key_mean_dwell / overall_mean_dwell` (overall excludes Backspace), and a **"long dwell" tag** (a label, never red) appears at ratio ≥ 1.25. Speed mode needs `iki_count ≥ 20` and shows the mean clean-transition IKI into the key. **Neither mode ever changes the error classification.** Caveat in the UI: different fingers have naturally different dwell.

### 8.4 Layout

v1 supports US-QWERTY. [P1] Detect mismatches with `navigator.keyboard?.getLayoutMap()` (feature-detected) and show a warning banner. Otherwise `layout_hint = "unknown"`.

---

## 9. SQLite schema (v1 scope)

`PRAGMA foreign_keys = ON` on every connection; version tracked with `PRAGMA user_version`; one `schema.sql`; during development, delete the DB if the schema changes.

```
sessions ──1:1── session_metrics
   ├──1:N── keystroke_events
   └──1:N── session_key_stats
```

| Table | Columns | Notes |
|---|---|---|
| **sessions** | `id` PK · `created_at` TEXT UTC · `mode` · `duration_limit_ms` NULL · `text_ref_json` · `passage_text` NOT NULL (snapshot) · `typed_text` NOT NULL · `active_duration_ms` REAL · `end_reason` (`completed`/`time_up`, derived) · `client_json` · `layout_hint` · `schema_version` · `analysis_version` | `analysis_version = 1` for the initial metric definitions. Increment it whenever metric definitions or derivation semantics change; it identifies the metric logic used for the stored derived values. Recalculation remains P2. |
| **keystroke_events** | `id` PK · `session_id` FK ON DELETE CASCADE · `seq` · `type` CHECK(`down`/`up`) · `t_ms` · `code` · `key` NULL · `repeat` CHECK(0/1) · UNIQUE(`session_id`,`seq`) | Raw and immutable. Only validated events *up to the derived end* are stored. |
| **session_metrics** | `session_id` PK/FK · `gross_wpm`, `net_wpm`, `accuracy_pct`, `final_accuracy_pct` · `total_keystrokes` (K), `correct_keystrokes`, `incorrect_keystrokes` (E), `final_length` (N) · `uncorrected_errors`, `corrected_errors`, `erased_unresolved_errors` · `backspace_count`, `backspace_presses` · `avg_dwell_ms`, `median_dwell_ms`, `dwell_count` · `avg_iki_ms`, `median_iki_ms`, `iki_sd_ms`, `iki_valid_count`, `iki_cv`, `consistency_score` · `pause_count`, `total_pause_ms`, `longest_pause_ms` · `zero_interval_count` (data quality) · `iki_hist_json` (P1, nullable) · `data_quality_json` | Derived. Nullable = "not computable". |
| **session_key_stats** | PK(`session_id`,`key_code`) · `attempts`, `errors`, `dwell_count`, `dwell_sum_ms`, `iki_count`, `iki_sum_ms` | Sums, so cross-session aggregation is an exact `SUM()`. Index on `key_code`. |

Index `sessions(created_at)`. All writes for one session happen in a single transaction (`executemany` for events). P2 adds a bigram table and a recalculation script; raw events are kept so both stay possible. `analysis_version` is set to `1` for every session created by the initial implementation and is incremented only when the metric definitions/derivation semantics change in a later implementation.

---

## 10. API

| Priority | Method & path | Purpose |
|---|---|---|
| P0 | `GET /api/texts/passages`, `GET /api/texts/passages/<id>`, `GET /api/texts/words?count=` | Text issue. Returns a `text_ref` plus `text`. The words endpoint picks the seed. |
| P0 | `POST /api/sessions` | Submit. `201 { session_id, metrics, warnings, links }` |
| P0 | `GET /api/sessions?limit=&offset=` | `{ items, total }`, limit ≤ 100 |
| P0 | `GET /api/sessions/<id>` | `{ session, metrics, key_stats }` (+ `series.wpm` in P1) |
| P0 | `GET /api/analytics/progress?scope=` | Sessions with `net_wpm`, `accuracy_pct`, and a moving average. `scope ∈ last_10, last_30, all` |
| P0 | `GET /api/analytics/keys?scope=` | `{ method, baseline_error_rate, min_observations, overall_mean_dwell_ms, keys:[{code,label,attempts,errors,error_rate,ci_low,ci_high,dwell_count,mean_dwell_ms,iki_count,mean_iki_ms,class,dwell_flag,reason}] }`. Classification is computed on the server. |
| P0 | `GET /api/export/sessions.csv` | UTF-8 **with BOM**; cells starting with `= + - @` get a leading `'`. Fixed columns, in order: `session_id, created_at, mode, duration_limit_ms, active_duration_ms, end_reason, gross_wpm, net_wpm, accuracy_pct, final_accuracy_pct, total_keystrokes, correct_keystrokes, incorrect_keystrokes, backspace_count`. Null metrics export as empty cells. |
| P1 | `GET /api/analytics/iki-histogram?scope=`, `GET /api/export/events.csv?session_id=`, `DELETE /api/sessions/<id>` | |
| P0 | `GET /api/health` | |
| P2 | bigrams, pauses, recalculate, report page | |

---

## 11. UI/UX (condensed; visual direction unchanged)

**Global:** one thin top nav (`test · analytics · keyboard · history` plus a light/dark text toggle). No card chrome, 8-pt spacing, radius 6/8 px, motion 120–160 ms and off under `prefers-reduced-motion`. **No fake data**; empty states say so. The nav fades to ~25 % while `running`.

**Typography (self-hosted, OFL):** UI **Lexend** (fallback Segoe UI); passage and numbers **JetBrains Mono** (fallback Cascadia Mono, Consolas) with tabular figures.

**Test screen (`/`):**
- Order: nav → config strip (`time | passage`, `15 30 60` or a passage select) → live row (timer, wpm, acc: hidden until the first keystroke; labelled *provisional*) → passage viewport (3 lines, caret line kept on line 2, max ~62ch, `clamp(22px,2.1vw,30px)`, line-height 1.75) → restart control.
- **Character states:** untyped = muted; correct = text colour; incorrect = error colour + underline + tinted background (an incorrect space is a tinted block); caret = 2 px accent bar, blinking only when idle. **Accent is never used on passage text.**
- **Footer hint:** `esc restart`. Tab is not mentioned, because it is not blocked outside a running test.
- States: "fix the highlighted characters to finish" (full-length buffer with errors), "too short" (nothing saved), a save-failed message with Retry and Download JSON [P1], and the cancelled-by-focus-loss message.

**Results (`/results/<id>`):**
- Tier 1: **Net WPM** and **Accuracy** (hero numbers).
- Tier 2: Gross WPM, timing consistency (interval-based, `—` if insufficient), corrected errors, uncorrected errors, erased-not-retyped (only if > 0), backspaces (deletions; presses in the tooltip), duration.
- Tier 3: avg dwell, avg IKI, median IKI, pause count, total pause, longest pause.
- Every label has a `?` definition. A data-quality line appears only when non-zero. An "About the measurements" note carries §5.5.
- P1: per-second WPM chart with error ticks.

**Analytics (`/analytics`):** a scope toggle; **P0:** WPM progression and accuracy progression (a stacked pair with a shared x axis, 5-session moving average); **P1:** IKI histogram. Each chart has one "what to look for" line.

**Keyboard (`/keyboard`):** an ANSI 15-unit board as `<button>` keys; mode `errors` (default) / `dwell` / `speed`; a legend with text and glyphs (`▲` weak, `■` average, `●` strong; grey with no glyph); a click-to-pin inspector with `n, x, error rate + interval, dwell (n), IKI (n), classification + reason`; lists "weakest keys" and "needs more data (n of 20)". Heat colours are tokens, and colour is never the only cue.

**History (`/history`):** a plain table (date/time, mode, duration, net WPM, accuracy, consistency), 25 per page, row click → results. Delete is P1. Compare is P2.

**Themes:** tokens on `:root` (light) and `:root[data-theme="dark"]`; no hex literals in components.

| Token | Light (Cheesecake) | Dark |
|---|---|---|
| `--bg` | `#fdf0d5` | `#171519` |
| `--surface` | `#f3e2bf` | `#242027` |
| `--text` | `#3a3335` | `#eee5e9` |
| `--text-muted` | `#756a6d` | `#8a7f86` |
| `--accent` | `#8e2949` | `#e28ab2` |
| `--accent-2` (large text/UI only) | `#d91c81` | `#a85b83` |
| `--error` | `#b3261e` | `#e46b75` (fallback `#f2776b`) |
| `--error-bg` | `rgba(179,38,30,.14)` | `rgba(228,107,117,.18)` |
| `--border` | `rgba(58,51,53,.14)` | `rgba(238,229,233,.12)` |
| `--heat-good / mid / bad / none` | `#7fae6b / #e3b94f / #c9473d / #e8d9b4` | `#5f9e6e / #d6a84a / #e4575f / #2e2a33` |

Contrast ratios are my estimates, so verify them with a checker. **Switching:** an inline blocking `<script>` in `<head>` before the stylesheet reads `localStorage["tba-theme"]` in try/catch (falling back to `prefers-color-scheme`) and sets `data-theme`. `color-scheme` is set per theme, a `.no-transition` class is removed after load, and the toggle dispatches `tba:themechange`, on which charts re-read tokens and call `update("none")`. Print always uses the light tokens.

---

## 12. Folder structure

```
typing-behaviour-analyzer/
├── run.py  requirements.txt (Flask, pytest)  README.md  AGENTS.md  .gitignore
├── docs/  PROJECT_BRIEF · ARCHITECTURE · UI_DESIGN · METRICS · EVENT_SCHEMA · TASKS · DECISIONS (.md)
├── app/
│   ├── __init__.py (create_app) · config.py · db.py · schema.sql · errors.py
│   ├── validators.py · texts.py · repository.py · exporters.py
│   ├── engine/   replay.py · metrics.py · keys.py (CHAR_TO_CODE, Wilson, classification) · __init__.py (analyze_session)
│   ├── routes/   pages.py · api.py · exports.py
│   ├── data/     passages.json (~12 original/public-domain ASCII) · words_en.json (~200 words)
│   ├── templates/ base.html · test.html · results.html · analytics.html · keyboard.html · history.html
│   └── static/   css/ (tokens, base, test, components, keyboard, print) · fonts/ · vendor/chart.umd.min.js
│                 js/ theme · api · capture · typing-engine · test-page · results-page · analytics-page · keyboard-heatmap · history-page · charts
├── tests/        conftest.py · fixtures/ · test_replay · test_metrics · test_keys · test_validators · test_repository · test_api · test_exports · test_hygiene
└── instance/     typing.db (git-ignored)
```

`engine/` is pure Python. There are no service classes and no abstractions beyond this.

---

## 13. Three-day roadmap (revised)

**Rule:** an end-to-end vertical slice (type → POST → numbers) must work by the end of Day 1, and no P1 starts while a P0 is broken.

**Day 1: engine and the core loop**
1. Repo, venv, `create_app`, `docs/` + `AGENTS.md` from this file, Chart.js and fonts vendored. *Commit.*
2. **Tests first**, then `engine/replay.py`, `metrics.py`, `keys.py` against golden examples A–G (§14.1). *Commit when green.*
3. `validators.py` (ASCII regexes, §6) with tests; `texts.py` + data files with the startup ASCII check.
4. `tokens.css` + inline theme script; `capture.js` (§5) and `typing-engine.js`; `test.html`.
5. `POST /api/sessions` returning computed metrics, shown on a plain results page. *Commit: "vertical slice".*

**Day 2: persistence, results, history, progress**
1. `schema.sql`, `db.py`, `repository.py` + persistence tests; POST saves.
2. Session endpoints; **final results page**; history page.
3. Typing-screen polish (caret, states, config strip, focus and Tab behaviour).
4. `progress` endpoint + WPM/accuracy charts (theme-aware); `sessions.csv`. *Commit and tag `day2`.*

**Day 3: signature heatmap, polish, delivery**
1. `session_key_stats` aggregation and `/api/analytics/keys`; heatmap UI (error mode), inspector, legend, grey/empty states. *Commit.*
2. Manual test pass (§14.3), bug fixes, empty/error states, README + limitations, presentation diagrams. *Tag `v1.0`.*
3. **Only if P0 is fully green**, take P1 in this order: results WPM chart → dwell/speed modes → IKI histogram → events CSV → delete → layout banner → print stylesheet.
4. P2 is not started in the three days.

**Contingency:** `TASKS.md` holds small tasks, each with files touched and acceptance criteria. Commit after every green milestone, tag each day, and keep prompts short and pointed at the docs. If a P1 is unfinished, remove its UI entry point instead of shipping it broken.

---

## 14. Testing

### 14.1 Golden examples (hand-computed, used as fixtures)

Engine-level tests use text `"cat"`, which bypasses the API's `K ≥ 10` and `T ≥ 3 s` minimums.

| ID | Mode | Events (`t` in ms) | Expected |
|---|---|---|---|
| **A** | passage | c@0, x@800, ⌫@1600, a@2400, t@6000 | completed at T = 6000 · K=4 C=3 E=1 N=3 U=0 **Ec=1 Eu=0** · deletions 1 · Gross **8.0** · Net **6.0** · accuracy 75 % · intervals 800,800,800,3600 → `V`=[800,800,800], mean 800, SD 0, pause_count 1, total 3600 |
| **B** | time, limit 6000 | c@0, x@800, t@1600 | time_up, T = 6000 · K=3 C=2 E=1 N=3 U=1 Ec=0 Eu=0 · Gross **6.0** · Net **4.0** · accuracy 66.7 % |
| **C** | time, limit 6000 | c@0, x@800, ⌫@1600 | K=2 C=1 E=1 N=1 U=0 Ec=0 **Eu=1** · Gross **4.0** · Net **2.0** |
| **D** | passage | c@0, a@800, x@1600, ⌫@2400, t@3200 | the buffer reaches full length wrong, so the test does **not** end until `t`; completed at T = 3200 · K=4 C=3 E=1 U=0 **Ec=1** · Gross **15.0** · Net **11.25** |
| **E** | passage | c@0, a@800, x@1600 | `INCOMPLETE_SESSION` (wrong final char, no correction) |
| **F** | time, limit 6000 | c@0, a@800, t@1600, then any event @2000 | completed at T = 1600, the later event dropped (`dropped_after_end`=1) · K=3 · Gross = Net = **22.5** |
| **G** | time, long text | c@0, a@100, t@200, ⌫down@1000, ⌫repeat@1500, ⌫repeat@1530, ⌫up@1600 | typed text "" · deletions **3** · presses **1** · **one** Backspace dwell of **600** (not 100) · timed actions c,a,t,⌫ → intervals 100,100,800 · repeats in no interval |

Invariants asserted on every fixture: `E = U + Ec + Eu`, `K = C + E`, `Net ≤ Gross`, `N ≤ K`.

### 14.2 Regression tests (one group per issue)

| # | Automated tests |
|---|---|
| 1 Gross WPM | A–D expected values. Gross > Net whenever a deleted or incorrect keystroke exists. Backspace-only differences do not change Gross. `Net ≤ Gross`. |
| 2 Completion | F (early completion, later events dropped); B (timer expiry, T = limit); passage mode with no completion → 422; client-supplied `end_reason`/`ended_at_ms` are not accepted or are ignored; events at `t == limit` are not accepted and timer expiry wins; events at `t > limit` are dropped; completion at `t == limit` resolves as `time_up`, not `completed`. |
| 3 Repeat Backspace | G: dwell = 600; deletions = 3; presses = 1; repeat without a pending original → 422; repeat on a printable key → 422; a repeat never changes `pending`; a second non-repeat down while pending → `missing_up`. |
| 4 ASCII | Validator rejects `key` = `"é"`, `"ß"`, `"\u00a0"`, `"😀"`, `"\n"`, `"\x7f"`, `"Dead"`, and `code` = `"KeyÉ"`, `"KeyA\n"`. It accepts 32 and 126. `up` with a non-null `key` is rejected. `"٣".isalnum()`-style Unicode digits in `code` are rejected. All passages and words pass the startup ASCII check. The engine raises on a non-ASCII text or key even if the validator is bypassed. `CHAR_TO_CODE` covers all 95 characters. |
| 5 Heatmap wording | n=19 grey, n=20 classified. Wilson(3,20) ≈ [0.052, 0.360]. Weak needs `lo>b`, margin ≥ 0.02 and x ≥ 3. A long dwell never changes the class. The response contains `method`. A hygiene test checks **user-facing heatmap strings only** (rendered templates and shipped JS string literals) and fails if they claim statistical significance. Documentation is excluded because the technical explanation in `METRICS.md` must explicitly state that the heuristic is not a significance test. |
| 6 Final char | D (fix-then-complete); E (rejected); a full-length wrong buffer does not end the test; a printable key at a full buffer → `INVALID_EVENT_SEQUENCE` server-side. |
| 7 Timing | Hygiene test: inspect user-facing copy in `README` and templates for unsupported timing-resolution or laboratory-grade precision claims (for example, claims of microsecond/µs precision). Do **not** ban the CSS `clamp()` function; it is a layout utility, not a timing-precision claim. Confirm that the timing-honesty note is present. |
| 8 IKI | A fixture with intervals [0, 200, 999, 1000, 1500, …]: zero is excluded and increments `zero_interval_count`; 200 and 999 are valid; 1000 and 1500 are pauses. Mean, median, SD, CV and histogram use only `V`; key-level IKI sums only clean transitions; the first action has no interval; `|V| < 5` → null stats; 29 vs 30 intervals for consistency. Include a zero-mean guard so CV is never calculated with a zero denominator. |
| 9 Errors | C (Eu=1); A (Ec=1); an error deleted and re-erred (Eu counts the erased one, U the remaining one); `E = U+Ec+Eu` on randomised event sequences (property-style loop with a seeded RNG). |
| 10 Accessibility | Tab/Shift+Tab are never prevented; focus leaving the viewport while running cancels and discards the session; normal focus navigation remains usable. |
| 11 Scope | The API has no bigram, pause or recalculate routes. The schema has no bigram table. |

Also automated: validators (non-monotonic `t`, `seq` gap, bad enums, oversized lists, unknown `text_ref`, wrong `schema_version`), persistence round-trip, FK cascade, rollback on mid-save failure, CSV BOM and injection guard, deterministic words per seed, status codes and the error shape. The deterministic word generator uses Python's `random.Random(seed).shuffle()` over the fixed source word list; preserve that algorithm and source-list ordering for reproducibility.

### 14.3 Manual checklist

- **Tab (#10):** with the test idle, Tab and Shift+Tab move through nav, config and the passage in a sensible order with visible focus rings. While running, Tab and Shift+Tab retain native behaviour; if focus leaves the passage viewport, the test is cancelled and discarded. Ctrl+Tab still switches browser tabs.
- **Capture:** hold a letter key (no repeated letters); hold Backspace (one dwell, many deletions); Ctrl+V; Ctrl+R; AltGr combos; typing "é" or an emoji is ignored; Space does not scroll or press a focused button.
- **Completion:** in passage mode, finish with a wrong last character (the test stays open), then fix it (the test ends). In time mode, let the timer expire after a deletion.
- **Focus loss:** Alt+Tab, clicking the URL bar and switching tabs mid-test all cancel, with nothing saved.
- **Theme:** no flash on reload in either theme; persistence across a browser restart; charts and heatmap recolour live.
- **Offline:** disconnect the network and restart `python run.py`.
- **Browsers:** Chrome and Edge at 100/125/150 % scaling.
- **Timestamp sanity (dev only):** `event.timeStamp` and `performance.now()` agree to within a few ms. Test a key event timestamped exactly at the time limit: timer expiry must win and that event must not be accepted.

---

## 15. Agent handoff documentation

`AGENTS.md` (OpenCode reads it; for Antigravity, check its docs for the rules-file name and point it here): read the docs first; stack restrictions; engine in pure Python with no metric math in JS; never modify raw events; run `pytest` before every commit; work only on the first unchecked task in `TASKS.md`; log deviations in `DECISIONS.md`; do not copy Monkeytype or Keybr code (Keybr is AGPL-3.0).
`PROJECT_BRIEF.md` (§1, §16) · `ARCHITECTURE.md` (§2, §9, §10, §12) · `UI_DESIGN.md` (§11) · `METRICS.md` (§4, §7, §8, §14.1 verbatim, the single source of truth for formulas) · `EVENT_SCHEMA.md` (§5, §6) · `TASKS.md` (§13 as small checkable tasks plus the §14.3 checklist) · `DECISIONS.md` (a dated log seeded with the §0 table). Commit after every green milestone and tag each day.

---

## 16. Assumptions and known limitations

**Assumptions**
1. Single user, local machine, no authentication. Desktop physical keyboard only.
2. US-QWERTY is the supported layout. Non-QWERTY users get a warning (P1) and a possibly misleading heatmap.
3. Text is printable ASCII 32–126 only, with lowercase word mode in P0.
4. Caret-locked typing: no word skipping, no cursor movement, no Ctrl/Alt+Backspace.
5. Passages are original or public-domain, and I am assuming you will author them.
6. `event.timeStamp` and `performance.now()` share one clock in Chrome/Edge (to be checked in dev).
7. The pause threshold is 1000 ms, the heatmap minimum is 20 observations, the dwell validity range is (0, 1000] ms, and valid IKI is (0, 1000) ms. All are named constants in `config.py`, chosen for practicality, not derived from research.
8. Monkeytype and Keybr behaviours not marked "verified" in §3 are unverified.
9. Browser-reported event timestamps are suitable for local descriptive analysis, not independent verification or secure assessment.

**Known limitations**
- **Timing is browser-observed**, not laboratory-grade (§5.5). Dwell and IKI are comparable only within one machine and browser. The server validates and replays client-reported timestamps; it does not independently verify when physical keystrokes occurred. This local single-user app is not tamper-proof or suitable as a secure exam/assessment platform.
- **Gross vs Monkeytype:** our WPM is character-level, so numbers will not match Monkeytype's word-level wpm. Our consistency is interval-based and is not comparable with Monkeytype's.
- **Error cascades:** a skipped letter inflates `E` until corrected.
- **Heatmap:** a heuristic, not a statistical test (§8.2). Dependence between keystrokes, a baseline that includes the key itself and no multiple-comparison correction. A missed Shift is blamed on the letter key.
- **Dwell** differs naturally by finger and key, so it is informational only.
- **Consistency score** is a descriptive index with no validation. It depends on text difficulty, the pause cutoff and sample size.
- **Focus loss cancels** the test (no pause/resume).
- **Accessibility:** keyboard navigation and focus rings are supported, but a typing test is inherently visual and screen-reader support is limited. Tab navigation is never trapped; leaving the typing viewport cancels a running test.
- **A crash before submit** loses the session. P1 keeps the payload in `sessionStorage` for retry.
- **Keys held at the end** have no dwell (`open_at_end`).
- **P2 features** (bigrams, rhythm/pause charts, compare, recalculation, report page) are intentionally absent, but raw events are retained so they can be added without data loss.

---

## Appendix: viva questions affected by v2

1. *Why is Gross WPM based on keystrokes and Net on final characters?* Gross measures raw output; Net measures usable output; Net ≤ Gross follows from `N ≤ K`.
2. *Why does the server derive when the test ended?* The server applies one deterministic replay and validation rule to the submitted event sequence. It does not independently verify physical key timing; the app is a local single-user analyzer, not a secure assessment system.
3. *What does "corrected error" mean?* Deleted **and** the position is now correct. Otherwise it is erased-unresolved. `E = U + Ec + Eu`.
4. *Why do held-Backspace repeats not affect dwell?* Dwell is a property of the physical press. Repeats are OS-generated and would otherwise overwrite the original keydown.
5. *How do you stop non-ASCII input?* The same regex on the client and in Python (`fullmatch`), plus an engine assertion.
6. *Is the heatmap "statistically significant"?* No. It is a conservative heuristic relative to your own history, and we say why.
7. *How do you differ from Monkeytype and Keybr?* We are an analyzer: error-first per-key stats, no adaptive lessons, interval-based consistency, character-level WPM.
