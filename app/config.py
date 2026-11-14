"""Application configuration constants.

This module holds the named thresholds defined in ``docs/METRICS.md`` §14 and
the request limits specified in ``docs/EVENT_SCHEMA.md`` §6–§7. It contains no
metric calculations and no validation logic.
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

# Derived-analysis identity (TBA blueprint §9, ADR-015).
ANALYSIS_VERSION = 1

# Session payload validation (docs/EVENT_SCHEMA.md §6–§7).
SUPPORTED_SCHEMA_VERSION = 1
MIN_SESSION_EVENTS = 2
MAX_SESSION_EVENTS = 10_000
MAX_SESSION_BODY_BYTES = 2 * 1024 * 1024
ALLOWED_TIME_LIMITS_MS = frozenset({15_000, 30_000, 60_000})
WORD_COUNT_MIN = 10
WORD_COUNT_MAX = 400

# Session history list (blueprint §10, docs/UI_DESIGN.md §8).
HISTORY_PAGE_SIZE = 25
SESSION_LIST_MAX_LIMIT = 100

# Progress analytics (blueprint §10, docs/UI_DESIGN.md §6).
PROGRESS_SCOPES = {"last_10": 10, "last_30": 30, "all": None}
PROGRESS_DEFAULT_SCOPE = "all"
PROGRESS_MOVING_AVERAGE_WINDOW = 5

# Word-mode text sizing (TBA blueprint §4.2). Time-mode texts are padded so early
# completion is practically unreachable while the completion rule stays defined.
WORDS_FOR_DURATION_MS = {
    15_000: 120,
    30_000: 200,
    60_000: 350,
}
