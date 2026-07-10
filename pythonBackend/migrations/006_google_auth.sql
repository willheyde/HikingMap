-- 006_google_auth.sql
--
-- Adds "Sign in with Google" (OAuth) alongside the existing email+password
-- login. Google login does NOT replace the JWT system — a verified Google
-- identity simply mints one of the same access tokens create_access_token()
-- already issues, so every downstream protected route is unchanged.
--
-- Run by hand / via the runner (from the pythonBackend directory):
--   python migrate.py up
-- (Existing DBs that were baselined at 005 will pick this up as pending.)

BEGIN;

-- OAuth users have no local password, so the column can no longer be NOT NULL.
-- DROP NOT NULL is a no-op if it is already nullable, so this is safe to re-run.
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- Google's stable subject identifier (the 'sub' claim in the ID token). This is
-- the thing we match on for a returning Google login — NOT the email, which a
-- user can change. UNIQUE so one Google account maps to at most one row; NULL
-- for password-only accounts. A nullable UNIQUE column permits many NULLs in
-- Postgres, so password users don't collide with each other.
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub text UNIQUE;

-- How the account was first created: 'password' (default; all existing rows) or
-- 'google'. This is descriptive, not exclusive — a password account that later
-- clicks "Sign in with Google" gets google_sub populated (account linking) while
-- keeping auth_provider = 'password'. Both login paths then work for that row.
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider text NOT NULL DEFAULT 'password';

COMMIT;
