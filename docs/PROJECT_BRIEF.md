# PROJECT_BRIEF.md — Typing Behaviour Analyzer

> Reference: `TBA_BLUEPRINT_v3_FINAL.md` §1, §16

---

## 1. Project Purpose

The **Typing Behaviour Analyzer (TBA)** is a local, single-user web application that captures keyboard events during typing tests, computes a rich set of behavioural metrics, and presents them through charts and an interactive heatmap. It is designed as a college project demonstrating full-stack development, data engineering (event capture → server replay → metric derivation → persistence → visualisation), and an understanding of measurement honesty.

TBA is **not** a competitive typing game, an adaptive tutor, or a secure assessment platform. It is a personal *analyzer* — the goal is insight into your own typing patterns.

---

## 2. Target Users

- A single local user on **Windows 11**, using **Chrome or Edge**.
- Physical desktop keyboard assumed. US-QWERTY layout is the supported configuration.
- No authentication, no network requirement (fully offline after initial setup).

---

## 3. Core Objectives

1. Capture keyboard events at fine temporal resolution using browser event timestamps.
2. Replay those events on the server to derive authoritative metrics — no metric math in JS.
3. Persist sessions and key-level statistics in SQLite for longitudinal analysis.
4. Display results clearly: hero WPM/accuracy, timing consistency, error accounting, an interactive key heatmap, and progress charts.
5. Be honest about measurement limitations (browser-observed timing, not lab-grade).
6. Be a solid demonstration of: Flask, sqlite3, ES modules, Chart.js, pytest, layered architecture.

---

## 4. Scope

### P0 — Must work (non-negotiable for submission)

| Feature | Description |
|---|---|
| Event capture | Keyboard event capture per blueprint §5 rules |
| Python engine | Replay, classification, all metrics (§7) |
| Validation | ASCII checks, schema validation, server-side replay validation |
| SQLite persistence | All four tables; single-transaction writes |
| Typing test UI | Time mode (15/30/60 s) and passage mode |
| Results page | Full metric display with definitions |
| History list | Paginated table of past sessions |
| Light + dark themes | No flash on load; token-based |
| Interactive error heatmap | Key board with error classification, inspector, grey/no-data states |
| Progress charts | WPM and accuracy over time (Chart.js, theme-aware) |
| sessions.csv export | UTF-8 BOM, injection-safe |
| Health endpoint | `GET /api/health` |

### P1 — Important (only after all P0 is working)

- Dwell and speed heatmap modes
- IKI histogram on analytics page
- Per-second WPM chart on results
- Events CSV export
- Delete session
- Retry-save / Download JSON on failure
- Layout-mismatch banner (`navigator.keyboard.getLayoutMap()`)
- Print stylesheet for results

### P2 — Optional / future

Bigram analysis, rhythm chart, pause charts, session comparison, recalculation endpoint, dedicated report page, pause/resume on focus loss, error-cascade guard, non-QWERTY support, colour-blind palette.

**P2 items are not started in the initial three-day build.**

---

## 5. Key Design Decisions (summary)

- **Character-level WPM**, not word-level. Documented as differing from Monkeytype.
- **Caret-locked** typing: no word skipping, no cursor movement, no Ctrl/Alt+Backspace.
- **Continue-and-correct** error mode only. No stop-on-error, no confidence mode.
- **Server is authoritative** for all stored metrics. Client JS shows only provisional live stats.
- **Tab is never intercepted.** Focus leaving the viewport cancels a running test.
- **Esc cancels** a test. No other restart shortcuts.
- **Passage mode ends only on exact match.** Wrong final character → user must correct.
- Full rationale in `docs/DECISIONS.md`.

---

## 6. Non-Goals (explicitly excluded)

- Multi-user, authentication, accounts
- Cloud storage or any network API beyond localhost Flask
- Adaptive lessons or target-speed coaching
- Tamper-proof or exam-grade timing verification
- Mobile / touchscreen support
- Any browser other than Chrome/Edge (though it may work elsewhere)
