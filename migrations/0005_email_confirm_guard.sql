-- Comment reply-mail double opt-in, and subscribe confirm-mail cooldown.
ALTER TABLE comments ADD COLUMN email_confirm_token TEXT;
ALTER TABLE comments ADD COLUMN email_confirmed_at TEXT;

CREATE INDEX IF NOT EXISTS idx_comments_email_confirm_token ON comments(email_confirm_token);

ALTER TABLE subscribers ADD COLUMN confirm_sent_at TEXT;

UPDATE subscribers SET confirm_sent_at = created_at WHERE confirm_sent_at IS NULL;
