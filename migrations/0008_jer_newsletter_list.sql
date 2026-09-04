-- Allow Jer’s Prospect Profiles. SQLite cannot ALTER a CHECK; recreate and copy.
BEGIN TRANSACTION;

CREATE TABLE subscribers_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  list TEXT NOT NULL CHECK (list IN ('posts', 'gradys-tour', 'da-breakdown-w-tad', 'jers-prospect-profiles')),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'confirmed', 'unsubscribed')),
  confirm_token TEXT NOT NULL,
  unsub_token TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  confirmed_at TEXT,
  unsubscribed_at TEXT,
  confirm_sent_at TEXT,
  UNIQUE (email, list)
);

INSERT INTO subscribers_new (
  id, email, list, status, confirm_token, unsub_token,
  created_at, confirmed_at, unsubscribed_at, confirm_sent_at
)
SELECT
  id, email, list, status, confirm_token, unsub_token,
  created_at, confirmed_at, unsubscribed_at, confirm_sent_at
FROM subscribers;

DROP TABLE subscribers;
ALTER TABLE subscribers_new RENAME TO subscribers;

CREATE INDEX IF NOT EXISTS idx_subscribers_list_status ON subscribers(list, status);
CREATE INDEX IF NOT EXISTS idx_subscribers_confirm_token ON subscribers(confirm_token);
CREATE INDEX IF NOT EXISTS idx_subscribers_unsub_token ON subscribers(unsub_token);

CREATE TABLE newsletter_sends_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  list TEXT NOT NULL CHECK (list IN ('posts', 'gradys-tour', 'da-breakdown-w-tad', 'jers-prospect-profiles')),
  post_guid TEXT NOT NULL,
  post_url TEXT NOT NULL,
  post_title TEXT NOT NULL,
  sent_at TEXT DEFAULT (datetime('now')),
  UNIQUE (list, post_guid)
);

INSERT INTO newsletter_sends_new (id, list, post_guid, post_url, post_title, sent_at)
SELECT id, list, post_guid, post_url, post_title, sent_at
FROM newsletter_sends;

DROP TABLE newsletter_sends;
ALTER TABLE newsletter_sends_new RENAME TO newsletter_sends;

CREATE INDEX IF NOT EXISTS idx_newsletter_sends_list ON newsletter_sends(list);

COMMIT;
