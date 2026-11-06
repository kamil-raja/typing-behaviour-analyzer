"""Application configuration constants.

This module holds the named thresholds defined in ``docs/METRICS.md`` §14.
It contains no metric calculations; the engine consumes these values.

Other application limits (request size, event counts, allowed durations) are
not formally enumerated in that section and are intentionally not invented
here. They will be added when the relevant validation/API tasks specify them.
"""

# Timing thresholds (milliseconds).
PAUSE_THRESHOLD_MS = 1000
DWELL_MAX_MS = 1000
IKI_MAX_MS = 1000

# Keyboard heatmap classification.
HEATMAP_MIN_N = 20
HEATMAP_BASELINE_FLOOR = 0.01
HEATMAP_WEAK_MARGIN = 0.02
HEATMAP_WEAK_MIN_X = 3
HEATMAP_Z = 1.96

# Minimum sample sizes.
CONSISTENCY_MIN_V = 30
IKI_STATS_MIN_V = 5
SESSION_MIN_K = 10
SESSION_MIN_T_MS = 3000

# IKI histogram [P1].
IKI_HIST_BINS = 40
IKI_HIST_BIN_WIDTH_MS = 25

# Dwell heatmap mode [P1].
DWELL_LONG_RATIO = 1.25
