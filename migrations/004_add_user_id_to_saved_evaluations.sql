ALTER TABLE saved_evaluations ADD COLUMN user_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_saved_evaluations_user_id ON saved_evaluations(user_id, updated_at DESC);
