-- ==============================================================================
-- Supabase PostgreSQL Migration: password_reset_tokens
-- ==============================================================================
-- This script safely and non-destructively provisions persistent single-use
-- password reset token tracking in Supabase PostgreSQL.
--
-- TARGET: Run in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/<your-project-id>/sql
-- ==============================================================================

-- 1. Create password_reset_tokens table if not exists
CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
    jti TEXT PRIMARY KEY,
    user_email TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Index for fast lookups by user email and consumed state
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_email
ON public.password_reset_tokens (LOWER(TRIM(user_email)), used_at);

-- 3. Enable Row Level Security (RLS)
ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;

-- 4. Revoke all privileges from public and authenticated roles (defense-in-depth)
REVOKE ALL ON TABLE public.password_reset_tokens FROM anon, authenticated;

-- 5. Access Security Notes:
-- -----------------------------------------------------------------------------
-- DO NOT create public ("anon") read or write policies for this table.
-- The backend FastAPI application accesses this table exclusively using the
-- private 'service_role' key, which bypasses RLS on the server.
-- Anonymous browser requests via the public anon key cannot query or tamper
-- with reset tokens (HTTP 401/403).
-- -----------------------------------------------------------------------------

-- 6. Verification Query
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'password_reset_tokens'
ORDER BY ordinal_position;
