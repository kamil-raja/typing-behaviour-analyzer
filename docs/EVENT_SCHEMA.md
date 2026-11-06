# EVENT_SCHEMA.md — Keyboard Event Capture and Contract

> Reference: `TBA_BLUEPRINT_v3_FINAL.md` §5, §6

---

## 1. Timing Source (§5.1)

```
timestamp = event.timeStamp
```

If `event.timeStamp` is not a finite number:
- Fall back to `performance.now()` measured at handler time.
- **Log this occurrence** (increment a diagnostic counter, log to console).
- Do **not** silently mix clocks without recording that the fallback occurred.

```
t = round(timestamp − first_accepted_keydown_timestamp, 1)   # milliseconds, one decimal place
```

`started_at` (wall-clock ISO string, `new Date().toISOString()`) is recorded once at the first accepted keydown. It is **informational only** — stored in the session but not used for metric derivation.

During development: log `event.timeStamp − performance.now()` once to sanity-check that both share a clock (Chrome/Edge assumption).

---

## 2. What Is Accepted (§5.2)

The **identical rule** applies on the client (JS) and the server (Python):

| Input | Rule |
|---|---|
| **Printable** | `event.key` matches `^[\x20-\x7E]$` exactly (single ASCII character 32–126, including Space). Excludes non-ASCII (é, ß, NBSP), emoji, control characters, `"Dead"`, `"Process"`, and anything with `event.isComposing = true`. |
| **Backspace** | `event.key === "Backspace"`, with no Ctrl, Meta, or Alt modifier. |
| **AltGr combos** | Treated as ordinary typing (`getModifierState("AltGraph")` check). |
| **Modifiers alone** | Shift, Ctrl, Alt, Meta, CapsLock — not recorded. |
| **Ctrl/Meta/Alt combos** | Ignored and **NOT** `preventDefault`-ed. |
| **Other keys** | Arrows, Home, End, Delete, F-keys, Enter — ignored; counted in `ignored.unsupported_keys`; `preventDefault`-ed only while `running`. |
| **Paste** | `paste` listener calls `preventDefault()` and increments `ignored.paste_attempts`. |

Discarded characters are counted in:
- `ignored.repeat_keydowns` — repeat printable keydowns
- `ignored.shortcuts` — Ctrl/Meta/Alt combos
- `ignored.unsupported_keys` — non-printable, non-Backspace keys
- `ignored.unsupported_chars` — non-ASCII or multi-unit characters
- `ignored.paste_attempts` — paste events

**Full-buffer rule:** when the buffer equals the text length, further printable keydowns are **ignored by the client** (not submitted). The server rejects a submitted printable keydown at a full buffer as `INVALID_EVENT_SEQUENCE`. This asymmetry is intentional.

---

## 3. Event Object Format (§6.1)

```json
{ "seq": 17, "type": "down", "t": 1523.4, "code": "KeyE", "key": "e",    "repeat": false }
{ "seq": 18, "type": "up",   "t": 1611.0, "code": "KeyE", "key": null,   "repeat": false }
```

| Field | Type | Rules |
|---|---|---|
| `seq` | integer | Starts at 0; contiguous (no gaps) |
| `type` | string | `"down"` or `"up"` only |
| `t` | number | Finite, ≥ 0, non-decreasing across the event list |
| `code` | string | Matches `re.fullmatch(r"[A-Za-z0-9]{1,32}", code)` — ASCII alphanumeric, 1–32 chars |
| `key` | string or null | `down`: matches `re.fullmatch(r"[\x20-\x7E]", key)` or exactly `"Backspace"`. `up`: must be `null` (keyup `key` can change with Shift and is unused). |
| `repeat` | boolean | `true` only for Backspace `down` events |

**Python validation pitfalls:**
- Use `re.fullmatch()`, not `re.match()`. (`$` in `re.match` accepts trailing newline.)
- Never use `str.isalnum()`, `str.isprintable()`, or `\w` for these checks (they accept non-ASCII).
- `str.isascii()` alone is insufficient (accepts control characters).

---

## 4. Pending-Keydown Map and Repeat Handling (§5.3)

Both the client JS and the server engine maintain a `pending: code → t_down` map.

| Situation | Action |
|---|---|
| Printable `down`, `repeat: false` | Accepted. `pending[code] = t`. |
| Printable `down`, `repeat: true` | **Discarded** (`preventDefault`), counted in `ignored.repeat_keydowns`. Server treats one in a payload as an error. |
| Backspace `down`, `repeat: false` | Recorded. `pending[event.code] = t`. Deletes one character if buffer non-empty. Identified by `event.key`, not by assuming `code === "Backspace"`. |
| Backspace `down`, `repeat: true` | Recorded **only if `pending[event.code]` already exists**. Deletion action. **Never reads, writes, or overwrites `pending`.** No pending original → client ignores, server rejects (`INVALID_EVENT_SEQUENCE`). |
| `up` event | If `pending[code]` exists → pair it, `dwell = t_up − t_down`, delete entry. If not → orphan; client does not record it; server drops and counts in `orphan_up`. |
| Second non-repeat `down` for a pending `code` | Missing keyup: old entry counted `missing_up`, new entry replaces it. |

**Rule for one physical Backspace hold (down + N repeats + up):**
- N+1 total deletions
- One dwell sample (measured from the **original** keydown, not from repeats)
- One press (the non-repeat down)
- One timed action (the non-repeat down)

---

## 5. Test Lifecycle and States (§4)

```
idle → running → finished
              → cancelled
```

| State | Transition |
|---|---|
| `idle` | Waiting. Backspace and all other keys ignored. |
| `idle → running` | First accepted printable keydown. `t = 0`. |
| `running → finished` | Completion (buffer == text exactly) OR timer expiry (`t >= duration_limit_ms`). Capture listeners removed. Payload submitted once. |
| `running → cancelled` | Esc key, or focus loss from the passage viewport. Nothing submitted. |

**Focus rules:**
- Keystrokes captured only when `event.target` is the passage viewport.
- Viewport: `tabindex="0"`, `aria-label="Typing area. Start typing to begin. Press Escape to restart."`.
- Receives focus on page load and after any config control is activated.
- **Tab / Shift+Tab are never `preventDefault`-ed** in any state.
- Focus loss while `running` (including Tab, Shift+Tab, mouse click elsewhere) → test **cancelled and discarded**.
- `window blur` or `visibilitychange → hidden` while `running` → test **cancelled** with message "Test cancelled. The window lost focus."
- Esc while `running` → cancelled, UI returns to `idle`.

---

## 6. Session Payload (`POST /api/sessions`) (§6.2)

```json
{
  "schema_version": 1,
  "mode": "time",
  "duration_limit_ms": 30000,
  "text_ref": { "type": "words", "seed": 482913, "count": 200 },
  "started_at": "2026-11-06T10:05:00.000Z",
  "client": {
    "user_agent": "Mozilla/5.0 ...",
    "platform": "Win32",
    "layout_hint": "qwerty"
  },
  "ignored": {
    "repeat_keydowns": 0,
    "shortcuts": 1,
    "unsupported_keys": 2,
    "unsupported_chars": 0,
    "paste_attempts": 0
  },
  "events": [ ... ]
}
```

| Field | Rules |
|---|---|
| `mode` | `"time"` (with `duration_limit_ms ∈ {15000, 30000, 60000}`) or `"passage"` (`duration_limit_ms: null`) |
| `text_ref` | `{"type":"passage","id":"p_003"}` or `{"type":"words","seed":int,"count":int(10..400)}`. **Client never sends the text body.** |
| `events` | Array of event objects; 2–10 000 events; body ≤ 2 MB |
| `client.layout_hint` | One of `"qwerty"`, `"non-qwerty"`, `"unknown"` |

The **client never sends** `ended_at_ms` or `end_reason`. These are server-derived.

---

## 7. Server Processing Order (§6.3)

1. **Schema validation** → 422 `VALIDATION_ERROR` with `details`:
   - All required fields present and correctly typed
   - 2–10 000 events; body ≤ 2 MB (413 `PAYLOAD_TOO_LARGE` otherwise)
   - First event is a non-repeat printable `down`
   - `t` values are non-decreasing
   - No repeat-printable events
   - No `up` event with a non-null `key`
   - `code` matches `[A-Za-z0-9]{1,32}`
   - `key` on `down` matches `[\x20-\x7E]` or `"Backspace"`

2. **Resolve text** → 404 `TEXT_NOT_FOUND`:
   - Rebuild text from `text_ref` using `texts.py`
   - Assert text and all event keys are ASCII 32–126 (validation error if not — never silently processed)

3. **Replay** (engine, `replay.py`):
   - For time mode: exclude events with `t >= duration_limit_ms`; end reason = `time_up`
   - Derive completion (buffer == text exactly) → end reason = `completed`
   - Drop events after derived end; count in `dropped_after_end`
   - Raise `INVALID_EVENT_SEQUENCE` (422) for: printable `down` at full buffer; Backspace repeat with no pending original

4. **Outcome checks**:
   - Passage mode with no completion → 422 `INCOMPLETE_SESSION`
   - `K < 10` or `T < 3000 ms` → 422 `SESSION_TOO_SHORT`

5. **Compute metrics → persist → return 201**

**Tolerated conditions** (reported as `warnings` / `data_quality`): `orphan_up`, `missing_up`, `open_at_end`, invalid dwell, `dropped_after_end`.

---

## 8. Error Response Shape

All endpoints use this shape:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": [
      { "field": "events[3].t", "problem": "t must be non-decreasing" }
    ]
  }
}
```

| Code | HTTP Status |
|---|---|
| `INVALID_JSON` | 400 |
| `VALIDATION_ERROR` | 422 |
| `INVALID_EVENT_SEQUENCE` | 422 |
| `INCOMPLETE_SESSION` | 422 |
| `SESSION_TOO_SHORT` | 422 |
| `TEXT_NOT_FOUND` | 404 |
| `NOT_FOUND` | 404 |
| `PAYLOAD_TOO_LARGE` | 413 |
| `INTERNAL_ERROR` | 500 |

---

## 9. Text Source Rules

- **Words mode:** deterministic word generator using `random.Random(seed).shuffle()` over the fixed source word list in `words_en.json`. The algorithm and source-list ordering must be preserved exactly for reproducibility across sessions.
- **Passage mode:** passages loaded from `passages.json`; ~12 original or public-domain ASCII texts.
- **Startup check:** at app startup, all passages and the word list are verified to contain only ASCII 32–126. Startup fails loudly if any character falls outside that range.

---

## 10. Event Storage

Only validated events **up to the derived end** are stored in `keystroke_events`. Events after the derived end are dropped and counted in `dropped_after_end` (reported as a warning, not an error).

Stored fields per event: `session_id`, `seq`, `type`, `t_ms`, `code`, `key` (null for `up`), `repeat`.

Events are **immutable** once stored. The `keystroke_events` table is preserved even for P2 recalculation purposes, so raw data is never discarded.
