# UI_DESIGN.md — Typing Behaviour Analyzer

> Reference: `TBA_BLUEPRINT_v3_FINAL.md` §11

---

## 1. Global Layout

- **Top navigation bar** (always visible, except it fades to ~25% opacity while a test is `running`):
  - Links: `test · analytics · keyboard · history`
  - Right side: light/dark theme toggle (text button, not icon-only)
- **8-pt spacing grid** throughout.
- **Border radius:** 6 px (small elements), 8 px (cards/panels).
- **Motion:** 120–160 ms transitions; `prefers-reduced-motion` disables all transitions.
- **No fake data.** Empty states display explicit text (e.g., "No sessions yet").

---

## 2. Typography

| Use | Font | Fallback |
|---|---|---|
| UI text, labels, body | **Lexend** (self-hosted, OFL) | Segoe UI, sans-serif |
| Passage text, numbers, code | **JetBrains Mono** (self-hosted, OFL) | Cascadia Mono, Consolas, monospace |

JetBrains Mono is used with **tabular figures** (`font-variant-numeric: tabular-nums`) for all numeric displays so digits align vertically.

---

## 3. Design Tokens (CSS Custom Properties)

Defined in `static/css/tokens.css`. **No hex literals outside this file.**

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
| `--heat-good` | `#7fae6b` | `#5f9e6e` |
| `--heat-mid` | `#e3b94f` | `#d6a84a` |
| `--heat-bad` | `#c9473d` | `#e4575f` |
| `--heat-none` | `#e8d9b4` | `#2e2a33` |

> **Contrast notice:** ratios are design estimates. Verify with a contrast checker before submission.

---

## 4. Screen: Test (`/`)

### Layout order (top to bottom)

1. Navigation bar
2. **Config strip:** mode selector (`time | passage`) + options
   - Time mode: `15 · 30 · 60` (seconds)
   - Passage mode: passage selector (`<select>`)
3. **Live row** (hidden until first keystroke; reappears with label *provisional*):
   - Timer countdown / elapsed
   - Live WPM (provisional)
   - Live accuracy (provisional)
4. **Passage viewport** (the typing area)
5. **Restart control** (`esc restart` hint in footer)

### Passage Viewport

- `tabindex="0"`, `aria-label="Typing area. Start typing to begin. Press Escape to restart."`
- **3 visible lines** at a time. The caret line is kept on **line 2** (scroll-follows-caret behaviour).
- Max ~62 characters per line.
- Font size: `clamp(22px, 2.1vw, 30px)`, line-height 1.75.
- Receives focus on page load and after any config control is activated.

### Character States

| State | Visual treatment |
|---|---|
| Untyped | Muted colour (`--text-muted`) |
| Correct | Normal text colour (`--text`) |
| Incorrect | Error colour (`--error`) + underline + tinted background (`--error-bg`). An incorrect space shows as a tinted block. |
| Caret | 2 px accent bar (`--accent`), blinking only when `idle`, not while `running` |

**Rule:** `--accent` is never applied to passage text characters.

### State Messages

| Situation | Message displayed |
|---|---|
| Full-length buffer with errors | "Fix the highlighted characters to finish" |
| Session too short (K < 10 or T < 3 s) | "Too short to save" |
| Save failed | Error message + Retry button + Download JSON [P1] |
| Test cancelled by focus loss | "Test cancelled. The window lost focus." |
| Test cancelled by Esc | UI returns to `idle`, no message needed |

### Footer

`esc restart` hint only. Tab is **not mentioned** (it is never blocked outside a running test).

---

## 5. Screen: Results (`/results/<id>`)

### Tier 1 — Hero numbers (large, prominent)

- **Net WPM**
- **Accuracy** (keystroke accuracy, `100·C/K`)

### Tier 2 — Supporting metrics

- Gross WPM
- Timing consistency (interval-based; shown as `—` if insufficient data)
- Corrected errors (`Ec`)
- Uncorrected errors (`U`)
- Erased, not retyped correctly (`Eu`) — shown **only when non-zero**, with tooltip
- Backspaces (deletions displayed; presses shown in tooltip)
- Active duration

### Tier 3 — Detail / timing stats

- Average dwell (ms)
- Average IKI (ms)
- Median IKI (ms)
- Pause count
- Total pause time (ms)
- Longest pause (ms)

### Additional elements

- Every label has a `?` definition tooltip.
- **Data-quality line** appears only when `zero_interval_count > 0` or other data-quality flags are set.
- **"About the measurements" note** (blueprint §5.5): timing is browser-observed, not lab-grade; suitable only for relative comparison on the same machine/browser.
- [P1] Per-second Net WPM chart with error ticks.

---

## 6. Screen: Analytics (`/analytics`)

- **Scope toggle:** `last 10 · last 30 · all` sessions
- **P0 charts (stacked pair, shared x-axis):**
  1. WPM progression (net WPM over time, with 5-session moving average)
  2. Accuracy progression (accuracy % over time, with 5-session moving average)
  - Each chart has one "what to look for" guidance line.
- **[P1]** IKI histogram (40 bins × 25 ms, over valid intervals `V` only)
- Charts are theme-aware: re-read CSS tokens and re-render on `tba:themechange`.

---

## 7. Screen: Keyboard Heatmap (`/keyboard`)

### Layout

- Full ANSI 15-unit keyboard board, rendered as `<button>` elements.
- **Mode selector:** `errors` (default) · `dwell` [P1] · `speed` [P1]
- **Legend:** text labels + glyphs (▲ weak / ■ average / ● strong / grey = no glyph, insufficient data). Colour is **never the only cue**.

### Heatmap Colour Logic

**Error mode (P0):**
- `n < 20` observations → `--heat-none` (grey), "n of 20" label
- `n ≥ 20` → classified by Wilson heuristic (see `docs/METRICS.md` §6):
  - **Weak (red):** `--heat-bad` + ▲ glyph
  - **Average (yellow):** `--heat-mid` + ■ glyph
  - **Strong (green):** `--heat-good` + ● glyph

**[P1] Dwell mode:** colour by `key_mean_dwell / overall_mean_dwell`; "long dwell" label (never red) at ratio ≥ 1.25.
**[P1] Speed mode:** colour by mean clean-transition IKI into key; `iki_count ≥ 20` required.

**Rule:** neither dwell nor speed mode ever changes the error classification.

### Click-to-pin Inspector

Clicking a key pins an inspector panel showing:
- `n` (observations), `x` (errors), error rate + Wilson CI bounds
- Dwell: count and mean (ms)
- IKI: count and mean (ms)
- Classification and reason

### Lists

- "Weakest keys" (top classified-weak keys by error rate)
- "Needs more data (n of 20)" (keys below the 20-observation threshold)

**Special keys:**
- Backspace: shows press count and dwell only (no error classification)
- Non-tracked keys (Shift, Ctrl, Tab, CapsLock, Enter): render neutral (no colour, no glyph)

---

## 8. Screen: History (`/history`)

- Plain table with columns: `date/time · mode · duration · net WPM · accuracy · consistency`
- **25 rows per page** with pagination controls.
- Clicking any row navigates to `/results/<session_id>`.
- [P1] Delete button per row.
- P2: Compare is not implemented.
- Empty state: "No sessions yet. Take a typing test to see your history here."

---

## 9. Theme Switching

1. Inline blocking `<script>` in `<head>` (before stylesheet link):
   - Reads `localStorage["tba-theme"]` in a try/catch.
   - Falls back to `prefers-color-scheme` if not set or on error.
   - Sets `data-theme` attribute on `<html>`.
   - Applies `.no-transition` class before stylesheet loads; removes it after load.
2. Toggle button saves preference to `localStorage["tba-theme"]` and sets `data-theme`.
3. Dispatches `tba:themechange` custom event.
4. Charts listen for `tba:themechange` and call `chart.update("none")` to recolour without animation.
5. `color-scheme` CSS property is set per theme for scrollbars and browser UI.
6. Print media: always uses light tokens.

---

## 10. Accessibility Requirements

- `:focus-visible` focus rings always visible on all interactive elements.
- `prefers-reduced-motion`: all transitions and animations disabled.
- `tabindex="0"` on the passage viewport; `-1` only for programmatic focus.
- Tab and Shift+Tab navigate normally through nav, config strip, and passage in a sensible order.
- Tab is **never trapped or prevented** in any state.
- Screen-reader support for the typing area is acknowledged as limited (inherent to a typing test).
- All heatmap key `<button>` elements have accessible labels.
