-- ==============================================================================
-- Supabase PostgreSQL Schema & Security Migration for NFT Trend Analyzer
-- ==============================================================================
-- Run this script in the Supabase Dashboard -> SQL Editor:
-- https://supabase.com/dashboard/project/<your-project-id>/sql
-- ==============================================================================

-- 1. Create registered_users table if not already created
CREATE TABLE IF NOT EXISTS public.registered_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'analyst',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Case-insensitive unique constraint on email
-- This prevents duplicate accounts regardless of letter casing (e.g., User@Domain vs user@domain).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'registered_users_email_key'
    ) THEN
        ALTER TABLE public.registered_users ADD CONSTRAINT registered_users_email_key UNIQUE (email);
    END IF;
END $$;

-- 3. Case-insensitive index for fast email lookups during login
CREATE UNIQUE INDEX IF NOT EXISTS idx_registered_users_lower_email
ON public.registered_users (LOWER(TRIM(email)));

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.registered_users ENABLE ROW LEVEL SECURITY;

-- 5. Security & Access Policy Notes:
-- -----------------------------------------------------------------------------
-- IMPORTANT: Do NOT create public ("anon") read policies for registered_users!
-- Public read policies would allow anyone with the public anon key to download
-- all registered user emails, names, and password hashes from the REST endpoint.
--
-- The NFT Trend Analyzer backend runs on Streamlit (a private server-side process).
-- The Streamlit server connects to Supabase using the 'service_role' key configured
-- in Streamlit Secrets ([supabase.service_role_key]).
--
-- The service_role key automatically bypasses RLS on the server, ensuring:
-- a) The server can query and register users securely.
-- b) Anonymous browser requests to /rest/v1/registered_users are rejected (HTTP 401/403).
-- c) Zero exposure of password hashes or user data to public visitors or client-side code.
-- -----------------------------------------------------------------------------

-- 6. Verification query to confirm table structure and columns
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'registered_users'
ORDER BY ordinal_position;
