# METRICS.md — Authoritative Metric Definitions

> **This is the single source of truth for all metric formulas.**
> Reference: `TBA_BLUEPRINT_v3_FINAL.md` §4, §7, §8, §14.1
> Do NOT reinterpret these formulas. Copy them exactly when implementing `app/engine/metrics.py`.

---

## 1. Symbols

| Symbol | Meaning |
|---|---|
| `K` | Total accepted printable keystrokes (non-repeat, while buffer is not full) |
| `C` | Correct accepted keystrokes (`typed == expected` at the moment of keystroke) |
| `E` | Incorrect accepted keystrokes: `E = K − C` |
| `N` | Length of the final buffer (`len(typed_final)`) |
| `U` | Uncorrected errors: positions `i < N` where `typed_final[i] ≠ P[i]` |
| `Ec` | Corrected errors (see §5) |
| `Eu` | Erased-unresolved errors (see §5) |
| `T` | Active duration in milliseconds (see §2) |
| `T_min` | Active duration in minutes: `T / 60000` |
| `P` | The reference passage text (ASCII 32–126) |

**Key invariants** (must be asserted on every test fixture):
- `E = U + Ec + Eu`
- `K = C + E`
- `Net WPM ≤ Gross WPM`
- `N ≤ K`

---

## 2. Active Duration `T` (§4.2)

| End reason | `T` |
|---|---|
| **Completion** (buffer == text exactly) | `t` of the completing keystroke. Must be `< duration_limit_ms` in time mode. |
| **Timer expiry** | Exactly `duration_limit_ms` |

Timer expiry wins at the exact boundary: a keystroke timestamped at `t >= duration_limit_ms` is NOT accepted even if it would complete the text. Completion is only accepted when its keystroke `t` is **strictly less than** `duration_limit_ms`.

---

## 3. Speed Metrics

### 3.1 Gross WPM

```
gross_wpm = (K / 5) / T_min
```

- Counts **every accepted printable keystroke** (`K`), including incorrect attempts and characters later deleted.
- **Backspaces are not printable and are not counted** in `K`.
- Backspace-only differences do not change Gross WPM.

### 3.2 Net WPM

```
net_wpm = max(0, ((N − U) / 5) / T_min)
```

- Counts correct characters remaining in the final buffer.
- `N − U` = characters in `typed_final` that match `P`.
- **Invariant:** `Net ≤ Gross` (because `N ≤ K`).

---

## 4. Accuracy Metrics

### 4.1 Primary Accuracy (keystroke accuracy)

```
accuracy_pct = 100 · C / K
```

Corrected mistakes still count against accuracy. Same idea as Monkeytype's "correctly pressed keys". This is the headline accuracy figure.

### 4.2 Final-Text Accuracy

```
final_accuracy_pct = null             when N = 0
final_accuracy_pct = 100 · (N − U) / N    otherwise
```

The empty final buffer has no characters whose correctness can be measured, so the value is `null` (not 0).

### 4.3 Error Rate

```
error_rate = 100 · E / K   (= 100 − accuracy_pct)
```

Per key: `x_k / n_k` where `x_k` = errors on key `k`, `n_k` = observations.

---

## 5. Error Accounting (§7.4)

Every incorrect keystroke ends in exactly one of three states:

| Metric | Symbol | Definition |
|---|---|---|
| **Uncorrected errors** | `U` | Incorrect keystrokes **still in the final buffer** (position `i < N` with `typed_final[i] ≠ P[i]`) |
| **Corrected errors** | `Ec` | Incorrect keystrokes that were **deleted AND** whose position `p` holds the **correct** character in the final buffer |
| **Erased-unresolved errors** | `Eu` | Incorrect keystrokes that were **deleted BUT** whose position is empty (`p ≥ N`) or still holds a wrong character in the final buffer |

**Invariant:** `E = U + Ec + Eu` — tested on every fixture.

Display rule: `Eu` is shown on the results page **only when non-zero**, with a tooltip "erased, not retyped correctly". `Eu` is most relevant in time mode, where the timer can expire right after a deletion.

---

## 6. Backspace Counts

| Metric | Definition |
|---|---|
| **Backspace deletions** | Total effective deletions, including held-key repeats. Each Backspace `down` (repeat or not) that removes a character counts. |
| **Backspace presses** | Non-repeat Backspace `down` events only. |

Display: show deletions prominently; show presses in a tooltip.

---

## 7. Dwell

For each non-repeat `down` paired with its `up` (using `pending: code → t_down` map):

```
dwell = t_up − t_down
```

**Validity:** `0 < dwell ≤ 1000 ms`.

Report: mean, median, count over all **printable** keys.

**Backspace is excluded** from the overall dwell figure and kept only in its per-key stats.

---

## 8. Timed Actions and Intervals

### 8.1 Timed Actions

A **timed action** is:
- An accepted printable keystroke (non-repeat, buffer not full), OR
- A non-repeat Backspace press that deleted a character (buffer was non-empty).

**Repeat downs are never timed actions.**

### 8.2 Interval List

```
I_i = t_down[i] − t_down[i−1]   for consecutive timed actions (i ≥ 1)
```

The first timed action has no preceding interval.

### 8.3 Pauses

A **pause** is an interval with `I ≥ 1000 ms` (threshold constant `PAUSE_THRESHOLD_MS = 1000`).

Reported:
- `pause_count`: number of pause-class intervals
- `total_pause_ms`: sum of all pause intervals
- `longest_pause_ms`: maximum pause interval

### 8.4 Valid Intervals `V`

```
V = { I_i : 0 < I_i < 1000 ms }
```

- Zero intervals (`I = 0`) are **excluded** and counted in `zero_interval_count` for data-quality reporting.
- Pauses (`I ≥ 1000 ms`) are **excluded** from `V`.
- **`V` is the single list behind every interval statistic** (IKI mean, median, SD, CV, histogram, consistency).

### 8.5 IKI Statistics

Computed over `V` only. All are `null` if `|V| < 5`.

| Statistic | Formula |
|---|---|
| `avg_iki_ms` | `mean(V)` |
| `median_iki_ms` | `median(V)` |
| `iki_sd_ms` | Sample standard deviation of `V` (denominator `n − 1`) |
| `iki_cv` | `SD / mean` (guarded: `null` if `mean = 0`) |

### 8.6 Timing Consistency Score

```
if |V| ≥ 30 and mean(V) > 0:
    CV = SD / mean
    consistency_score = round(100 · max(0, 1 − CV), 1)
else:
    consistency_score = null
```

- Labelled "timing consistency (interval-based)" to distinguish it from Monkeytype's word-level consistency.
- A descriptive index, not a validated measure. `CV` is always shown beside the score.
- `null` when fewer than 30 valid intervals, or when mean is zero.

---

## 9. IKI Histogram [P1]

- **40 bins × 25 ms** over `V` only (range 0–1000 ms, exclusive of endpoints).
- Pauses are excluded (they exceed 1000 ms).
- Zero intervals are excluded (they are in `zero_interval_count`).
- Stored as `iki_hist_json` in `session_metrics` (nullable).

---

## 10. Per-Key IKI

A **clean transition** is two consecutive timed actions where:
- Both are accepted printable keystrokes
- Both are correct (`typed == expected`)
- `0 < I < 1000 ms` (valid interval)

The interval `I` is added to the **later** keystroke's expected key's stats:
```
key_stats[expected_char].iki_count += 1
key_stats[expected_char].iki_sum_ms += I
```

Mean per-key IKI = `iki_sum_ms / iki_count`.

Per-key IKI is a **subset** of `V`, never a different measure.

---

## 11. Per-Second Series [P1]

For each whole second `s` (starting at `s = 1`):

```
net_wpm_cum(s) = max(0, ((correct_chars_at_s) / 5) / (s / 60))
```

Where `correct_chars_at_s` = correct characters in the buffer state at time `s` (the last replayed buffer state at or before `s` seconds; retain the last known state if no later event exists).

Also reported: `errors_in_sec(s)` = incorrect keystrokes in second `s`.

---

## 12. Keyboard Heatmap Classification (§8)

### 12.1 Observation Attribution

- **Observation `n`** for a key = accepted keystrokes whose **expected character** maps to that key through `CHAR_TO_CODE` (static US-QWERTY table covering all ASCII 32–126).
  - Capital and lowercase both map to the letter key.
  - Shifted symbols map to their base key.
- **Errors `x`** = observations that were incorrect (counted at the moment of the keystroke, even if later deleted).
- **Dwell** is attributed to the key **physically pressed** (`event.code`).

### 12.2 Error Classification: Wilson Heuristic

> **This is a conservative heuristic relative to the user's own typing history. It is NOT a hypothesis test, NOT a p-value, and NOT a claim of statistical significance. The words "significant" and "statistically" must NOT appear in any user-facing string.**

For each key with `n ≥ 20` observations:

```
e = x / n                                            # key error rate
b = max(Σx / Σn, 0.01)                              # pooled baseline, floored at 1%

# Wilson confidence interval (z = 1.96):
centre = (e + z²/(2n)) / (1 + z²/n)
half   = z · sqrt(e(1-e)/n + z²/(4n²)) / (1 + z²/n)
lo = centre − half
hi = centre + half
```

Classification:
- **Weak (red):** `lo > b` AND `e − b ≥ 0.02` AND `x ≥ 3`
- **Strong (green):** not weak AND `e ≤ b`
- **Average (yellow):** otherwise

For `n < 20`: **grey** (insufficient data), displayed as "n of 20".

API response includes: `"method": "wilson_vs_pooled_baseline_heuristic"`

**Reference test value:** Wilson(3 errors, 20 observations) ≈ [0.052, 0.360]

### 12.3 Dwell and Speed Modes [P1]

**Dwell mode:**
- Requires `dwell_count ≥ 20`.
- Colour by `key_mean_dwell / overall_mean_dwell` (overall excludes Backspace).
- "Long dwell" label (not red) at ratio ≥ 1.25.

**Speed mode:**
- Requires `iki_count ≥ 20`.
- Colour by mean clean-transition IKI into the key.

**Rule:** neither mode ever changes the error classification.

---

## 13. Golden Fixtures (§14.1) — Hand-computed Expected Values

Text `"cat"` is used for engine-level tests, bypassing the API's `K ≥ 10` and `T ≥ 3 s` minimums.

| ID | Mode | Events (t in ms) | Expected |
|---|---|---|---|
| **A** | passage | c@0, x@800, ⌫@1600, a@2400, t@6000 | completed T=6000 · K=4 C=3 E=1 N=3 U=0 **Ec=1 Eu=0** · deletions=1 · Gross=**8.0** · Net=**6.0** · accuracy=75% · intervals [800,800,800,3600] → V=[800,800,800], mean=800, SD=0, pause_count=1, total_pause=3600 |
| **B** | time, limit=6000 | c@0, x@800, t@1600 | time_up T=6000 · K=3 C=2 E=1 N=3 U=1 Ec=0 Eu=0 · Gross=**6.0** · Net=**4.0** · accuracy=66.7% |
| **C** | time, limit=6000 | c@0, x@800, ⌫@1600 | K=2 C=1 E=1 N=1 U=0 Ec=0 **Eu=1** · Gross=**4.0** · Net=**2.0** |
| **D** | passage | c@0, a@800, x@1600, ⌫@2400, t@3200 | buffer reaches full length wrong → test does NOT end until corrected; completed T=3200 · K=4 C=3 E=1 U=0 **Ec=1** · Gross=**15.0** · Net=**11.25** |
| **E** | passage | c@0, a@800, x@1600 | `INCOMPLETE_SESSION` (wrong final char, no correction) |
| **F** | time, limit=6000 | c@0, a@800, t@1600, then any event @2000 | completed T=1600, later event dropped (`dropped_after_end`=1) · K=3 · Gross=Net=**22.5** |
| **G** | time, long text | c@0, a@100, t@200, ⌫down@1000, ⌫repeat@1500, ⌫repeat@1530, ⌫up@1600 | typed text "" · deletions=**3** · presses=**1** · **one** Backspace dwell=**600** (from original down, not repeats) · timed actions: c,a,t,⌫ → intervals [100,100,800] · repeats not in interval list |

**Invariants asserted on every fixture:** `E = U + Ec + Eu` · `K = C + E` · `Net ≤ Gross` · `N ≤ K`

---

## 14. Named Constants (all in `app/config.py`)

| Constant | Value | Used for |
|---|---|---|
| `PAUSE_THRESHOLD_MS` | 1000 | Interval classified as a pause |
| `DWELL_MAX_MS` | 1000 | Maximum valid dwell |
| `IKI_MAX_MS` | 1000 | Maximum valid IKI (exclusive) |
| `HEATMAP_MIN_N` | 20 | Minimum observations for classification |
| `HEATMAP_BASELINE_FLOOR` | 0.01 | Floor for pooled baseline error rate |
| `HEATMAP_WEAK_MARGIN` | 0.02 | Minimum `e - b` for weak classification |
| `HEATMAP_WEAK_MIN_X` | 3 | Minimum errors for weak classification |
| `HEATMAP_Z` | 1.96 | Wilson CI z-value |
| `CONSISTENCY_MIN_V` | 30 | Minimum valid intervals for consistency |
| `IKI_STATS_MIN_V` | 5 | Minimum valid intervals for IKI stats |
| `SESSION_MIN_K` | 10 | Minimum keystrokes to save |
| `SESSION_MIN_T_MS` | 3000 | Minimum duration to save |
| `IKI_HIST_BINS` | 40 | Histogram bin count [P1] |
| `IKI_HIST_BIN_WIDTH_MS` | 25 | Histogram bin width in ms [P1] |
| `DWELL_LONG_RATIO` | 1.25 | Threshold for "long dwell" label [P1] |
