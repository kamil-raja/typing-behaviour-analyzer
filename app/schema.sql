-- Typing Behaviour Analyzer — SQLite schema (v1 scope).
-- Reference: TBA_BLUEPRINT_v3_FINAL.md §9 and docs/ARCHITECTURE.md §5.
-- During development, delete instance/typing.db if the schema changes.

CREATE TABLE IF NOT EXISTS sessions (
    id                  TEXT PRIMARY KEY,
    created_at          TEXT NOT NULL,
    mode                TEXT NOT NULL CHECK (mode IN ('time', 'passage')),
    duration_limit_ms   INTEGER,
    text_ref_json       TEXT NOT NULL,
    passage_text        TEXT NOT NULL,
    typed_text          TEXT NOT NULL,
    active_duration_ms  REAL NOT NULL,
    end_reason          TEXT NOT NULL CHECK (end_reason IN ('completed', 'time_up')),
    client_json         TEXT NOT NULL,
    layout_hint         TEXT NOT NULL
                        CHECK (layout_hint IN ('qwerty', 'non-qwerty', 'unknown')),
    schema_version      INTEGER NOT NULL,
    analysis_version    INTEGER NOT NULL,
    CHECK (
        (mode = 'time'
            AND duration_limit_ms IS NOT NULL
            AND duration_limit_ms IN (15000, 30000, 60000))
        OR (mode = 'passage' AND duration_limit_ms IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS session_metrics (
    session_id                  TEXT NOT NULL
                                REFERENCES sessions(id) ON DELETE CASCADE,
    gross_wpm                   REAL,
    net_wpm                     REAL,
    accuracy_pct                REAL,
    final_accuracy_pct          REAL,
    total_keystrokes            INTEGER NOT NULL,
    correct_keystrokes          INTEGER NOT NULL,
    incorrect_keystrokes        INTEGER NOT NULL,
    final_length                INTEGER NOT NULL,
    uncorrected_errors          INTEGER NOT NULL,
    corrected_errors            INTEGER NOT NULL,
    erased_unresolved_errors    INTEGER NOT NULL,
    backspace_count             INTEGER NOT NULL,
    backspace_presses           INTEGER NOT NULL,
    avg_dwell_ms                REAL,
    median_dwell_ms             REAL,
    dwell_count                 INTEGER NOT NULL,
    avg_iki_ms                  REAL,
    median_iki_ms               REAL,
    iki_sd_ms                   REAL,
    iki_valid_count             INTEGER NOT NULL,
    iki_cv                      REAL,
    consistency_score           REAL,
    pause_count                 INTEGER NOT NULL,
    total_pause_ms              REAL NOT NULL,
    longest_pause_ms            REAL,
    zero_interval_count         INTEGER NOT NULL,
    iki_hist_json               TEXT,
    data_quality_json           TEXT,
    PRIMARY KEY (session_id)
);

CREATE TABLE IF NOT EXISTS keystroke_events (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL CHECK (seq >= 0),
    type        TEXT NOT NULL CHECK (type IN ('down', 'up')),
    t_ms        REAL NOT NULL CHECK (t_ms >= 0),
    code        TEXT NOT NULL,
    key         TEXT,
    repeat      INTEGER NOT NULL CHECK (repeat IN (0, 1)),
    UNIQUE (session_id, seq),
    CHECK (
        (type = 'down' AND key IS NOT NULL)
        OR (type = 'up' AND key IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS session_key_stats (
    session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    key_code        TEXT NOT NULL,
    attempts        INTEGER NOT NULL,
    errors          INTEGER NOT NULL,
    dwell_count     INTEGER NOT NULL,
    dwell_sum_ms    REAL NOT NULL,
    iki_count       INTEGER NOT NULL,
    iki_sum_ms      REAL NOT NULL,
    PRIMARY KEY (session_id, key_code)
);

CREATE INDEX IF NOT EXISTS idx_sessions_created_at
    ON sessions(created_at);

CREATE INDEX IF NOT EXISTS idx_session_key_stats_key_code
    ON session_key_stats(key_code);
