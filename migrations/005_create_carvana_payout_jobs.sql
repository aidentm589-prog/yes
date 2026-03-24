CREATE TABLE IF NOT EXISTS carvana_payout_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    source TEXT NOT NULL DEFAULT 'carvana',
    status TEXT NOT NULL,
    vin TEXT,
    license_plate TEXT,
    plate_state TEXT,
    mileage INTEGER NOT NULL,
    zip_code TEXT,
    condition TEXT NOT NULL,
    rebuilt_title INTEGER NOT NULL DEFAULT 0,
    exterior_color TEXT,
    interior_color TEXT,
    notes TEXT,
    submitted_payload_json TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    failed_at TEXT,
    offer_amount REAL,
    offer_currency TEXT,
    offer_text_raw TEXT,
    result_summary TEXT,
    result_json TEXT,
    screenshot_url_or_path TEXT,
    page_text_capture TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_carvana_payout_jobs_user_id ON carvana_payout_jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_carvana_payout_jobs_status ON carvana_payout_jobs(status, created_at DESC);
