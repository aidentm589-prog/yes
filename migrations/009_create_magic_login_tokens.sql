CREATE TABLE IF NOT EXISTS magic_login_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    label TEXT,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT,
    FOREIGN KEY (user_id) REFERENCES user_accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_magic_login_tokens_user_id ON magic_login_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_magic_login_tokens_expires_at ON magic_login_tokens(expires_at);
