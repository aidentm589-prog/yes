CREATE TABLE IF NOT EXISTS saved_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_title TEXT NOT NULL,
    vehicle_input TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    preview_payload TEXT NOT NULL,
    snapshot_payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_saved_evaluations_updated_at ON saved_evaluations(updated_at DESC);
