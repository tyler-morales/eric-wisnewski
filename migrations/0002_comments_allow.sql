-- Comment moderation: pending (awaiting approval) vs approved (visible on site)
-- Existing rows get status 'approved'; new comments are inserted as 'pending'.
ALTER TABLE comments ADD COLUMN status TEXT DEFAULT 'approved';
