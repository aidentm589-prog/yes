CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_hash TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_run_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    source_listing_id TEXT,
    url TEXT,
    fetched_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    FOREIGN KEY(source_run_id) REFERENCES source_runs(id)
);

CREATE TABLE IF NOT EXISTS normalized_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_run_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    source_listing_id TEXT,
    dedupe_key TEXT NOT NULL,
    url TEXT,
    fetched_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    FOREIGN KEY(source_run_id) REFERENCES source_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_source_runs_query_hash ON source_runs(query_hash);
CREATE INDEX IF NOT EXISTS idx_raw_listings_source_run_id ON raw_listings(source_run_id);
CREATE INDEX IF NOT EXISTS idx_normalized_listings_source_run_id ON normalized_listings(source_run_id);
