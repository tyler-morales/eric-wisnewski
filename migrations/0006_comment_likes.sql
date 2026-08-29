-- One like per browser visitor_id. Counts come from COUNT(*), not a column.
CREATE TABLE IF NOT EXISTS comment_likes (
  comment_id INTEGER NOT NULL,
  visitor_id TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (comment_id, visitor_id)
);
