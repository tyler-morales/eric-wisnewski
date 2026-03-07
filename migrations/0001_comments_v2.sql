-- Comments v2: threading (parent_id) and author ownership (edit_token)
ALTER TABLE comments ADD COLUMN parent_id INTEGER REFERENCES comments(id);
ALTER TABLE comments ADD COLUMN edit_token TEXT;
CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_id);
