-- Per-type newsletter subscribers and send ledger (same D1 as comments).
CREATE TABLE IF NOT EXISTS subscribers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  list TEXT NOT NULL CHECK (list IN ('posts', 'gradys-tour')),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'confirmed', 'unsubscribed')),
  confirm_token TEXT NOT NULL,
  unsub_token TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  confirmed_at TEXT,
  unsubscribed_at TEXT,
  UNIQUE (email, list)
);

CREATE INDEX IF NOT EXISTS idx_subscribers_list_status ON subscribers(list, status);
CREATE INDEX IF NOT EXISTS idx_subscribers_confirm_token ON subscribers(confirm_token);
CREATE INDEX IF NOT EXISTS idx_subscribers_unsub_token ON subscribers(unsub_token);

CREATE TABLE IF NOT EXISTS newsletter_sends (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  list TEXT NOT NULL CHECK (list IN ('posts', 'gradys-tour')),
  post_guid TEXT NOT NULL,
  post_url TEXT NOT NULL,
  post_title TEXT NOT NULL,
  sent_at TEXT DEFAULT (datetime('now')),
  UNIQUE (list, post_guid)
);

CREATE INDEX IF NOT EXISTS idx_newsletter_sends_list ON newsletter_sends(list);
