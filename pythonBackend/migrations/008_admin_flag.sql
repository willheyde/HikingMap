-- 008_admin_flag.sql
--
-- Adds an admin role. Until now every route was either public or gated only to
-- "any authenticated user" — there was no notion of a privileged user. The hike
-- catalog (create/update/delete) is now admin-only so the shared trail data
-- can't be tampered with by ordinary accounts (or, previously, by anonymous
-- callers). Item writes stay open to any authenticated user (items are
-- user-customizable); this flag is only consulted by get_current_admin.
--
-- Run by hand / via the runner (from the pythonBackend directory):
--   python migrate.py up
--
-- Grant yourself admin after applying:
--   UPDATE users SET is_admin = true WHERE email = 'you@example.com';

BEGIN;

-- Default false: every existing and future account is a normal user until
-- explicitly promoted. NOT NULL so the gate check never has to handle NULL.
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin boolean NOT NULL DEFAULT false;

COMMIT;
