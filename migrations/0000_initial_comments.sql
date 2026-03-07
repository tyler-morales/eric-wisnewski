-- Blog comments: thread keyed by page pathname (url)
CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL,
  author TEXT NOT NULL,
  email TEXT,
  body TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_comments_url ON comments(url);
