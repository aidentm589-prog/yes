CREATE TABLE IF NOT EXISTS subscription_tiers (
    tier INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    credits_granted INTEGER NOT NULL DEFAULT 0,
    monthly_price TEXT NOT NULL DEFAULT '',
    yearly_price TEXT NOT NULL DEFAULT '',
    marketing_copy TEXT NOT NULL DEFAULT '',
    has_bulk_access INTEGER NOT NULL DEFAULT 0,
    is_unlimited INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
